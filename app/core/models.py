import datetime
import hashlib
import logging
import os

import celery
import numpy as np
from allauth.account.signals import user_signed_up
from billing.models import SubscriptionHistory
from core.utils.u_similar_service import SimilarService
from core.utils.u_web_page import get_page_info
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import Count
from django.db.models import deletion
from django.db.models.signals import post_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.safestring import mark_safe

from .utils.u_amplitude import amplitude
from .utils.u_classifier import ClassifierService
from .utils.u_files import download_to_file_field
from .utils.u_request import get_exif_from_url
from .utils.u_request import get_short_domain
from .utils.u_search_engine import PhotoInstance
from .utils.u_search_engine import SearchEngine
from .utils.u_vk import get_album_id
from .utils.u_vk import get_album_owner
from .utils.u_vk import get_album_photos
from .utils.u_vk import get_album_size
from .utils.u_vk import get_album_url
from .utils.u_vk import get_vk_photo_urls
from .utils.u_vk import get_vk_user_albums
from .utils.u_vk import user_info
from .utils.u_vk import VkPhotoInstance

try:
    from django.db.models import JSONField
    postgres_only = False
except ImportError:
    from django.contrib.postgres.fields import JSONField
    postgres_only = True

logger = logging.getLogger(__name__)
classifier_service = ClassifierService()


class Base(models.Model):
    ST_DEFAULT = 'DEF'
    ST_VK = 'VK'
    SOURCE_TYPE = (
        (ST_DEFAULT, 'default'),
        (ST_VK, 'VK'),
    )
    id = models.BigAutoField(primary_key=True)
    # Источник ввода записи
    source = models.CharField(max_length=5, choices=SOURCE_TYPE, default=ST_DEFAULT, blank=True, null=True)
    # ИД в системе источнике
    src_id = models.CharField(max_length=50, default='', blank=True, null=True)
    # Дата создания записи
    create_date = models.DateTimeField(default=timezone.now)
    # Дата изменения
    update_date = models.DateTimeField(default=timezone.now)
    # Владелец/создатель записи
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='user',
        related_name='%(class)s',
    )

    class Meta:
        abstract = True


INF = 1.79e308  # large arbitrary number


def convert_np_to_float(obj):
    if obj == np.nan:
        return None
    elif obj == np.inf:
        return INF
    elif obj == -np.inf:
        return -INF
    else:
        return obj


def convert_float_to_np(f):
    if f is None:
        return np.nan
    elif f >= INF or np.isclose(f, INF):
        return np.inf
    elif f <= -INF or np.isclose(f, -INF):
        return -np.inf
    else:
        return f


class NumpyFloatField(models.FloatField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('null', True)
        super(NumpyFloatField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        value = convert_np_to_float(value)
        return super(NumpyFloatField, self).get_prep_value(value)

    def to_python(self, value):
        value = super(NumpyFloatField, self).to_python(value)
        value = convert_float_to_np(value)
        return value


class Author(Base, models.Model):
    id = models.BigAutoField(primary_key=True)
    first_name = models.CharField(max_length=100, blank=True, null=True, default='')
    last_name = models.CharField(max_length=100, blank=True, null=True, default='')
    vk_profile = models.URLField(max_length=1000, blank=True, null=True)
    followers_count = models.IntegerField(default=0)
    is_group = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)

    def link(self):
        if self.is_group:
            return mark_safe(f'<a href="https://vk.com/public{self.src_id}">{self.src_id}</a>')
        return mark_safe(f'<a href="https://vk.com/id{self.src_id}">{self.src_id}</a>')
    link.short_description = 'Link'


def user_album_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    # file will be saved to MEDIA_ROOT/albums/158184342/FeYzlje2axo.jpg
    if instance.author:
        return f'albums/{instance.author.src_id}/{instance.src_id}/{filename}'
    return f'albums/unknown_author/{instance.src_id}/{filename}'


media_storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)


class Album(Base, models.Model):
    # Статусы обработки
    PS_NEW = 'NEW'
    PS_WRK = 'WORK'
    PS_UPD = 'UPD'
    PS_DON = 'DONE'
    PROCESSING_STATUS = (
        (PS_NEW, 'Новый'),
        (PS_WRK, 'В работе'),
        (PS_UPD, 'Обновляется'),
        (PS_DON, 'Готово'),
    )
    id = models.BigAutoField(primary_key=True)
    url = models.URLField(max_length=1000, blank=False, null=False)
    author = models.ForeignKey(
        Author,
        on_delete=models.SET_NULL,
        blank=False,
        null=True,
        related_name='albums',
    )
    count = models.IntegerField(default=0)
    cover = models.ImageField(upload_to=user_album_path, storage=media_storage, blank=True, null=True)
    last_update_photos = models.DateTimeField(default=None, blank=True, null=True)
    last_search_photos = models.DateTimeField(default=None, blank=True, null=True)
    status = models.CharField(
        verbose_name='Статус обработки',
        max_length=4,
        choices=PROCESSING_STATUS,
        default=PS_NEW,
    )
    title = models.CharField(max_length=500, blank=True, null=True, default='')
    is_private = models.BooleanField(default=False)

    @staticmethod
    def get_by_vk_id(vk_album_id, user_id):
        if not isinstance(vk_album_id, int):
            try:
                vk_album_id = int(str(vk_album_id))
            except ValueError:
                logger.error(
                    f'Album.get_by_vk_id type error',
                    extra={'vk_album_id': vk_album_id},
                )
                return None
        q_albums = Album.objects.filter(src_id=vk_album_id, user_id=user_id)
        q_count = q_albums.count()
        if q_count != 1:
            logger.error(
                f'Album.get_by_vk_id q_albums.count [{q_count}]',
                extra={
                    'vk_album_id': vk_album_id,
                    'user': user_id,
                },
            )
            return None
        return q_albums.first()

    def get_album_stats(self):
        search_done = False
        if self.status == self.PS_DON and self.last_search_photos:
            search_done = True
        site_count = SearchResult.objects.filter(photo__album=self, found_image=True).values(
            'domain__domain',
        ).annotate(total=Count('domain__domain')).count()
        found_count = SearchResult.objects.filter(photo__album=self, found_image=True).values(
            'photo_id',
        ).annotate(total=Count('photo_id')).count()
        mention_count = SearchResult.objects.filter(photo__album=self, found_image=True, mention_exact_match=True).values(
            'domain__domain',
        ).annotate(total=Count('domain__domain')).count()
        result = {
            'vk_album_id': str(self.src_id),
            'search_done': search_done,
            'site_count': site_count,
            'found_count': found_count,
            'mention_count': mention_count,
        }
        return result

    def update_photos(self, is_free=None, update_limit=0):
        if self.source != self.ST_VK:
            raise NotImplementedError(f'update_photos for {self.source} not implemented.')
        owner_id = get_album_owner(self.url)
        album_id = get_album_id(self.url)
        count, result = get_album_photos(owner_id=owner_id, album_id=album_id, limit=update_limit)
        self.count = count
        self.update_date = timezone.now()
        item: VkPhotoInstance
        for item in result:
            photo, created = Photo.objects.get_or_create(
                source=Photo.ST_VK,
                source_id=item.id,
                src_id=item.id,
                mini_url=item.mini_photo_url,
                maxi_url=item.maxi_photo_url,
                source_album=item.album_id,
                source_owner=item.owner_id,
                user=self.user,
                album=self,
            )
            if not created:
                photo.update_date = timezone.now()
            photo.search_allowed = True
            photo.save()
        self.last_update_photos = timezone.now()
        self.save()

    def full_check_results(self):
        if self.status in {self.PS_DON, self.PS_NEW}:
            celery.current_app.send_task(
                'core.tasks.run_full_check_results', (self.id,), queue='high_priority', routing_key='high_priority',
            )
        return

    def full_check_similarity(self):
        if self.status in {self.PS_DON, self.PS_NEW}:
            celery.current_app.send_task(
                'core.tasks.run_full_check_similarity',
                (self.id,),
                queue='high_priority',
                routing_key='high_priority',
                countdown=3,
            )
        return

    def get_best_result(self):
        # Photo.objects.filter(album=self, duplicates=).annotate(
        #     num_interesting_books=Count('pk')).aggregate(max=Max('num_interesting_books')))
        return

    def reset_status(self):
        self.status = self.PS_NEW
        self.save()


class Photo(Base, models.Model):
    id = models.BigAutoField(primary_key=True)
    album = models.ForeignKey(Album, on_delete=deletion.CASCADE)
    mini_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    maxi_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    source_id = models.CharField(max_length=100, blank=True, null=True, default='')
    source_album = models.CharField(max_length=100, blank=True, null=True, default='')
    source_owner = models.CharField(max_length=100, blank=True, null=True, default='')
    # Дата последнего поиска
    search_date = models.DateTimeField(default=None, blank=True, null=True)
    # Число выполненных поисков
    search_count = models.IntegerField(default=0)
    # Число ошибок при поиске
    error_count = models.IntegerField(default=0)
    # Разрешение на поиск по фото (может быть не включен, если фото не входит в тарифный лимит)
    search_allowed = models.BooleanField(default=False)
    labels = models.CharField(max_length=1000, blank=True, null=True, default='')
    tags = models.CharField(max_length=1000, blank=True, null=True, default='')
    similar_data = models.BinaryField(default=None, blank=True, null=True)

    def image_tag(self):
        return mark_safe(f'<img src="{self.mini_url}" width="100" height="100" />')

    image_tag.short_description = 'Image'

    @staticmethod
    def get_by_vk_id(vk_photo_id, user_id):
        if not isinstance(vk_photo_id, str):
            try:
                vk_photo_id = str(vk_photo_id)
            except ValueError:
                logger.error(
                    f'Photo.get_by_vk_id type error',
                    extra={'vk_album_id': vk_photo_id},
                )
                return None
        q_photo = Photo.objects.filter(src_id=vk_photo_id, user_id=user_id)
        q_count = q_photo.count()
        if q_count != 1:
            logger.error(
                f'Photo.get_by_vk_id q_albums.count [{q_count}]',
                extra={
                    'vk_photo_id': vk_photo_id,
                    'user': user_id,
                },
            )
            return None
        return q_photo.first()

    def get_exif(self):
        metadata = get_exif_from_url(self.maxi_url)
        print(f'metadata: {metadata}')

    def search_photo(self, spend_limit=0, is_free=True):
        # Выполнение поиска по всем подключенным движкам
        results = []
        successful = True
        new_engine_results = {}
        if not self.maxi_url:
            logging.error(
                f'search_photo: url is empty',
                extra={
                    'vk_photo_id': self.source_id,
                    'db_photo_id': self.id,
                    'maxi_url': self.maxi_url,
                },
            )
            self.error_count += 1
            self.search_date = timezone.now()
            self.search_count += 1
            self.save()
            return 0
        se = SearchEngine(spend_limit, is_free)
        try:
            results = se.get_instances(self.maxi_url, vk_photo_id=self.source_id, vk_owner_id=self.source_owner)
        except Exception as e:
            successful = False
            logging.error(
                f'search_photo: {type(e)}',
                exc_info=True,
                extra={
                    'vk_photo_id': self.source_id,
                    'vk_owner_id': self.source_owner,
                    'db_photo_id': self.id,
                },
            )
            self.error_count += 1
            self.search_date = timezone.now()
            self.search_count += 1
            self.save()
        else:
            # Сохранение результатов
            item: PhotoInstance
            for item in results:
                domain_name = get_short_domain(item.domain)
                domain = None
                try:
                    domain, created = DomainData.objects.get_or_create(
                        domain=domain_name,
                        user=None,
                    )
                except DomainData.MultipleObjectsReturned:
                    domain = DomainData.objects.get(domain=domain_name)[0]
                finally:
                    if isinstance(item.crawl_date, datetime.datetime):
                        crawl_date = item.crawl_date
                    else:
                        crawl_date = None
                    duplicate, created = SearchResult.objects.get_or_create(
                        user=self.user,
                        photo=self,
                        engine=item.se_type,
                        domain=domain,
                        page_url=item.page_url,
                        image_url=item.image_url,
                        partial_matching=item.partial,
                        similar_images=item.similar,
                        crawl_date=crawl_date,
                        score=item.score,
                    )
                    if created:
                        duplicate.title = item.title
                        if item.se_type in new_engine_results:
                            new_engine_results[item.se_type] += 1
                        else:
                            new_engine_results[item.se_type] = 1
                    else:
                        duplicate.update_date = timezone.now()
                    duplicate.save()
            self.search_date = timezone.now()
            self.search_count += 1
            self.save()
        finally:
            try:
                # Фиксируем статистику по запросам в поисковики
                engine_counts = se.get_engine_counts()
                today = timezone.now().date()
                for engine_count in engine_counts:
                    counter, created = EngineCounter.objects.get_or_create(
                        engine=EngineCounter.SE_IMAGE,
                        name=engine_count['name'],
                        search_date=today,
                        album=self.album,
                        photo=self,
                        is_free=is_free,
                        successful=successful,
                    )
                    counter.search_count = counter.search_count + engine_count['count']
                    if engine_count['name'] in new_engine_results:
                        counter.result_count = counter.result_count + new_engine_results[engine_count['name']]
                    counter.save()
            except Exception as spe:
                logging.error(
                    f'Photo.search_photo engine counters error: {type(spe)}',
                    exc_info=True,
                )
        return len(results)

    def check_similarity(self):
        if not classifier_service.ready():
            classifier_file = Classifier.get_classifier_file()
        else:
            classifier_file = None
        base_image_data = None
        if 'BlockMeanHash' in self.similar_data and \
                'RadialVarianceHash' in self.similar_data and \
                'AverageHash' in self.similar_data and \
                'MarrHildrethHash' in self.similar_data and \
                'PHash' in self.similar_data and \
                'delta_color' in self.similar_data and \
                'base_dominant_color_r' in self.similar_data and \
                'base_dominant_color_g' in self.similar_data and \
                'base_dominant_color_b' in self.similar_data:
            base_image_data = self.similar_data
        similar_service = SimilarService(self.maxi_url, base_image_data)
        if not base_image_data:
            self.similar_data = similar_service.get_base_image_data()
            self.save()
        q_search_results = SearchResult.objects.filter(photo=self, found_image=True)
        for item in q_search_results:
            item: SearchResult
            if 'BlockMeanHash' not in item.similar_data or \
                    'RadialVarianceHash' not in item.similar_data or \
                    'AverageHash' not in item.similar_data or \
                    'MarrHildrethHash' not in item.similar_data or \
                    'PHash' not in item.similar_data or \
                    'delta_color' not in item.similar_data or \
                    'base_dominant_color_r' not in item.similar_data or \
                    'base_dominant_color_g' not in item.similar_data or \
                    'base_dominant_color_b' not in item.similar_data:
                item.similar_data = similar_service.compare_with(item.image_url)
                item.save()
            if item.similar_data and 'BlockMeanHash' in item.similar_data:
                item.predict_similar = classifier_service.predict(
                    {
                        'id': item.id,
                        'mention_similar': item.mention_similar,
                        'partial_matching': item.mention_similar,
                        'similar_data__BlockMeanHash': item.similar_data['BlockMeanHash'],
                        'similar_data__RadialVarianceHash': item.similar_data['RadialVarianceHash'],
                        'similar_data__AverageHash': item.similar_data['AverageHash'],
                        'similar_data__MarrHildrethHash': item.similar_data['MarrHildrethHash'],
                        'similar_data__PHash': item.similar_data['PHash'],
                        'similar_data__delta_color': item.similar_data['delta_color'],
                        'similar_data__base_dominant_color_r': item.similar_data['base_dominant_color_r'],
                        'similar_data__base_dominant_color_g': item.similar_data['base_dominant_color_g'],
                        'similar_data__base_dominant_color_b': item.similar_data['base_dominant_color_b'],
                        'verified_similarity': item.verified_similarity,
                    },
                    classifier_file,
                )
                item.save()
        return f'similar_data for: {q_search_results.count()}'


class DomainData(Base, models.Model):
    id = models.BigAutoField(primary_key=True)
    search_date = models.DateTimeField(default=None, blank=True, null=True)
    domain = models.URLField(max_length=1000, blank=False, null=False, default='')

    def __str__(self):
        return f'DomainData({self.id}) - {self.domain}'


class DomainContacts(Base, models.Model):
    SE_HUNTER = 10
    SE_LUSHA = 15
    SE_HIRETOOL = 20
    SE_FIND_THAT_EMAIL = 30
    SE_GOOGLE = 35
    SE_YANDEX = 40

    SEARCH_ENGINE = (
        (SE_HUNTER, 'Hunter'),
        (SE_LUSHA, 'Lusha'),
        (SE_HIRETOOL, 'Hiretool'),
        (SE_FIND_THAT_EMAIL, 'Find That Email'),
        (SE_GOOGLE, 'Google'),
        (SE_YANDEX, 'Yandex'),
    )
    id = models.BigAutoField(primary_key=True)
    search_date = models.DateTimeField(default=None, blank=True, null=True)
    domain = models.ForeignKey(DomainData, on_delete=models.SET_NULL, null=True)
    engine = models.IntegerField(choices=SEARCH_ENGINE, default=SE_HUNTER)


class SearchResult(Base, models.Model):
    SEARCH_ENGINE = (
        (PhotoInstance.SE_YANDEX_CLOUD, 'Yandex cloud'),
        (PhotoInstance.SE_YANDEX, 'Yandex'),
        (PhotoInstance.SE_GOOGLE_CLOUD, 'Google cloud'),
        (PhotoInstance.SE_GOOGLE, 'Google'),
        (PhotoInstance.SE_BING, 'Bing'),
        (PhotoInstance.SE_TINEYE, 'TinEye'),
        (PhotoInstance.SE_VK_API, 'Vk api'),
    )
    id = models.BigAutoField(primary_key=True)
    photo = models.ForeignKey(Photo, on_delete=deletion.CASCADE, verbose_name='photo', related_name='duplicates')
    engine = models.IntegerField(choices=SEARCH_ENGINE, default=PhotoInstance.SE_YANDEX)
    domain = models.ForeignKey(DomainData, on_delete=models.SET_NULL, null=True)
    page_url = models.URLField(max_length=1000, blank=False, null=False)
    title = models.CharField(max_length=1000, blank=True, null=True, default='')
    image_url = models.URLField(max_length=1000, blank=False, null=False)
    favicon_url = models.URLField(max_length=1000, default='', blank=True, null=True)
    # Дата обхода поисковым движком
    crawl_date = models.DateTimeField(default=None, blank=True, null=True)
    score = models.FloatField(default=None, blank=True, null=True)
    # Дата последней проверки доступности фото на странице
    last_seen = models.DateTimeField(default=timezone.now)
    last_checked = models.DateTimeField(default=None, blank=True, null=True)
    last_modified = models.DateTimeField(default=None, blank=True, null=True)
    partial_matching = models.BooleanField(default=False)
    similar_images = models.BooleanField(default=False)
    # Число просмотров страницы
    views_number = models.IntegerField(default=0)
    views_checked = models.DateTimeField(default=timezone.now)
    found_image = models.BooleanField(default=False)
    # Упоминание
    mention_exact_match = models.BooleanField(default=False)
    mention_similar = models.BooleanField(default=False)
    # Авто проверка похожести
    similar_data = JSONField(default=dict)
    predict_similar = models.BooleanField(default=None, blank=True, null=True)
    # Ручная проверка похожести и данные для модели ml
    verified_similarity = models.BooleanField(default=None, blank=True, null=True)
    verified_skip = models.BooleanField(default=False)
    verified_date = models.DateTimeField(default=None, blank=True, null=True)

    def image_tag(self):
        return mark_safe(f'<img src="{self.image_url}" width="100" height="100" />')

    image_tag.short_description = 'Image'

    def check_result(self):
        first_name = None
        last_name = None
        if self.photo and self.photo.album and self.photo.album.author:
            author = self.photo.album.author
            first_name = author.first_name
            last_name = author.last_name
        info = get_page_info(self.page_url, self.image_url, first_name, last_name)
        if not info:
            return
        if 'page_title' in info and info['page_title']:
            self.title = info['page_title']
        if 'favicon_url' in info and info['favicon_url']:
            self.favicon_url = info['favicon_url']
        if 'page_view' in info and info['page_view']:
            self.views_number = info['page_view']
        if 'found_image' in info:
            self.found_image = info['found_image']
        if 'last_modified' in info and info['last_modified']:
            self.last_modified = info['last_modified']
        if 'mention_exact_match' in info:
            self.mention_exact_match = info['mention_exact_match']
        self.last_checked = timezone.now()
        self.update_date = timezone.now()
        self.save()
        return f'found: {self.found_image}, mention: {self.mention_exact_match}'


class EngineCounter(models.Model):
    SE_IMAGE = 'IMAGE'
    SE_VIEWS = 'VIEWS'
    SE_EMAIL = 'EMAIL'

    ENGINE_TYPE = (
        (SE_IMAGE, 'Image search engine'),
        (SE_VIEWS, 'Views counter'),
        (SE_EMAIL, 'Email finding'),
    )
    id = models.BigAutoField(primary_key=True)
    search_date = models.DateField(default=None, blank=True, null=True)
    # Тип движка (поиск, просмотры, адреса)
    engine = models.CharField(choices=ENGINE_TYPE, default=SE_IMAGE, max_length=10)
    # Название поискового движка
    name = models.CharField(default='None', blank=False, null=False, max_length=100)
    # Число запросов
    search_count = models.IntegerField(default=0)
    # Число уникальных результатов поиска (нахождение повторно не увеличивает счётчик)
    result_count = models.IntegerField(default=0)
    # Выгодоприобретатель
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        default=None,
        related_name='%(class)s',
    )
    # Альбом
    album = models.ForeignKey(
        Album,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        default=None,
    )
    # Альбом
    photo = models.ForeignKey(
        Photo,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        default=None,
    )
    # Тип поиска (платный/бесплатный)
    is_free = models.BooleanField(default=True)
    # Признак успешности завершения
    successful = models.BooleanField(default=True)


class Classifier(models.Model):
    id = models.BigAutoField(primary_key=True)
    create_date = models.DateTimeField(default=timezone.now)
    file_name = models.CharField(default='', blank=True, null=False, max_length=1000)
    version = models.CharField(default='v0.1', blank=True, null=False, max_length=10)
    score = NumpyFloatField(blank=True)
    confusion_matrix = models.CharField(default='', blank=True, null=False, max_length=100)
    active = models.BooleanField(default=False)

    def set_active(self):
        if not self.file_name:
            logging.warning(f'Classifier.set_active warning: file_path is empty')
            return
        q_other = Classifier.objects.exclude(id=self.id)
        q_other.update(active=False)
        self.active = True
        classifier_service.load_model(self.file_name)
        self.save()

    @classmethod
    def get_classifier_file(cls):
        q_c = Classifier.objects.filter(active=True)
        if q_c.count() == 1:
            item = q_c.first()
            return item.file_name
        return None


def user_profile_path(instance, filename):
    # file will be saved to MEDIA_ROOT/avatars/<session_key>/FeYzlje2axo.jpg
    return f'avatars/{instance.anonym_session_key}/{filename}'


class UserProfile(models.Model):
    SHOW_STATE_SLEEP = 10
    SHOW_STATE_WAIT = 11
    SHOW_STATE_TRIGGER = 12
    SHOW_STATE_FIRE = 13
    SHOW_STATE_DONE = 14
    SHOW_CHOICES = (
        (SHOW_STATE_SLEEP, 'Sleep'),
        (SHOW_STATE_WAIT, 'Wait'),
        (SHOW_STATE_TRIGGER, 'Trigger'),
        (SHOW_STATE_FIRE, 'Fire'),
        (SHOW_STATE_DONE, 'Done'),
    )

    user = models.OneToOneField(
        User, on_delete=deletion.CASCADE, primary_key=True, verbose_name='user', related_name='profile',
    )
  
    photo = models.ImageField(upload_to=user_profile_path, storage=media_storage)
    birthday = models.CharField(max_length=50, blank=True, null=True, default='')
    hometown = models.CharField(max_length=150, blank=True, null=True, default='')
    join_date = models.DateTimeField('join date', default=timezone.now, )
    join_location = models.CharField(max_length=100, blank=True, null=True, default='')
    anonym_session_key = models.CharField(max_length=100, blank=True, null=True, default='')

    total_photos = models.IntegerField(default=0)

    user_agent = models.CharField(max_length=200, default=None, blank=True, null=True)
    utm_source = models.CharField(max_length=100, blank=True, null=True)
    utm_medium = models.CharField(max_length=100, blank=True, null=True)
    utm_campaign = models.CharField(max_length=100, blank=True, null=True)
    utm_term = models.CharField(max_length=100, blank=True, null=True)
    utm_content = models.CharField(max_length=200, blank=True, null=True)
    utm_referrer = models.CharField(max_length=100, blank=True, null=True)

    show_nps = models.IntegerField(choices=SHOW_CHOICES, default=SHOW_STATE_SLEEP)
    show_welcome = models.IntegerField(choices=SHOW_CHOICES, default=SHOW_STATE_SLEEP)

    last_visit = models.DateTimeField(default=None, blank=True, null=True)
    founders_access = models.BooleanField(default=False)


class UserNps(models.Model):
    user = models.ForeignKey(
        on_delete=deletion.SET_NULL, related_name='user_nps', to=User, null=True,
    )
    id = models.BigAutoField(primary_key=True)
    nps = models.IntegerField(default=0)
    answer_date = models.DateTimeField(default=timezone.now)
    message = models.CharField(max_length=10000, blank=True, default='')


def delete_model_file(sender, instance, **kwargs):
    try:
        file_path = os.path.join(classifier_service.models_folder, instance.file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:  # pylint: disable=broad-except
        pass


def create_classifier(sender, instance, **kwargs):
    if instance.file_name.strip(' '):
        return
    values = SearchResult.objects.filter(
        found_image=True, similar_data__BlockMeanHash__gte=-100,
        similar_data__RadialVarianceHash__gte=-100,
        similar_data__AverageHash__gte=-100,
        similar_data__MarrHildrethHash__gte=-100, similar_data__PHash__gte=-100,
        similar_data__delta_color__gte=-100,
    ).exclude(
        verified_date=None,
        mention_similar=None,
        partial_matching=None,
    ).values(
        'id', 'mention_similar', 'partial_matching', 'similar_data__BlockMeanHash',
        'similar_data__RadialVarianceHash', 'similar_data__AverageHash', 'similar_data__MarrHildrethHash',
        'similar_data__PHash', 'similar_data__delta_color', 'similar_data__base_dominant_color_r',
        'similar_data__base_dominant_color_g', 'similar_data__base_dominant_color_b', 'verified_similarity',
    )
    file_name, estimate = classifier_service.create_new_model(values)
    if file_name:
        instance.file_name = file_name
    if estimate and 'accuracy_score' in estimate and 'confusion_matrix' in estimate:
        instance.score = estimate['accuracy_score']
        instance.confusion_matrix = estimate['confusion_matrix']


post_delete.connect(delete_model_file, sender=Classifier)
pre_save.connect(create_classifier, sender=Classifier)


@receiver(user_signed_up)
def on_signed_up(sender, request, user, **kwargs):
    sociallogin = kwargs['sociallogin']

    print(f'   Signal user_signed_up! {user.email}')
    preferred_avatar_size_pixels = 128

    picture_url = 'http://www.gravatar.com/avatar/{}?s={}'.format(
        hashlib.md5(user.email.encode('UTF-8')).hexdigest(),
        preferred_avatar_size_pixels,
    )

    registration_type = 'Unknown'
    # Add UserProfile and extra info
    try:
        # Get info from social account
        if sociallogin:
            birthday = ''

            if sociallogin.account.provider == 'facebook':
                registration_type = 'facebook'
                f_name = sociallogin.account.extra_data['first_name']
                l_name = sociallogin.account.extra_data['last_name']

                if f_name:
                    user.first_name = f_name
                if l_name:
                    user.last_name = l_name

                picture_url = 'http://graph.facebook.com/{0}/picture?width={1}&height={1}'.format(
                    sociallogin.account.uid, preferred_avatar_size_pixels,
                )

                if 'birthday' in sociallogin.account.extra_data:
                    birthday = sociallogin.account.extra_data['birthday']
            elif sociallogin.account.provider == 'vk':
                registration_type = 'vk'
                f_name = sociallogin.account.extra_data['first_name']
                l_name = sociallogin.account.extra_data['last_name']
                if f_name:
                    user.first_name = f_name
                if l_name:
                    user.last_name = l_name

                picture_url = sociallogin.account.extra_data['photo_medium']

                if 'bdate' in sociallogin.account.extra_data:
                    birthday = sociallogin.account.extra_data['bdate']
            else:
                logging.error(f'Unknown sociallogin.account.provider: {sociallogin.account.provider}')

            user.save()

            profile = UserProfile(user=user)
            profile.birthday = birthday
            profile.anonym_session_key = request.session.session_key

            if picture_url:
                file_name = f'{registration_type}_{sociallogin.account.uid}.jpg'
                download_to_file_field(picture_url, profile.photo, file_name=file_name)

            if hasattr(request, 'geo_city') and hasattr(request, 'geo_country_code'):
                profile.join_location = f'{request.geo_country_code}, {request.geo_city}'

            profile.save()
    except Exception as ex:
        error_text = 'user_signed_up create UserProfile Exception [{}]'.format([ex, ])
        print(error_text)
        logger.error(error_text, exc_info=True)

    join_date = '-'
    search_profile = UserProfile.objects.filter(user=user)
    if search_profile.count() > 0:
        profile = search_profile.first()
        profile.anonym_session_key = request.session.session_key
        profile.save()
        join_date = profile.join_date.strftime('%d.%m.%Y')

    event = amplitude.create_event(
        request, 'Registration', {'registration_type': registration_type, 'join_date': join_date},
    )
    amplitude.log_event(event)


def update_author(user, author, vk_user_info):
    followers_count = 0
    if 'followers_count' in vk_user_info:
        followers_count = vk_user_info['followers_count']
    if 'members_count' in vk_user_info:
        followers_count = vk_user_info['members_count']
    if 'first_name' in vk_user_info:
        author.first_name = vk_user_info['first_name']
    if 'last_name' in vk_user_info:
        author.last_name = vk_user_info['last_name']
    author.followers_count = followers_count
    if user:
        author.user = user
    author.save()
    return author


def update_album_detail(vk_user_id, vk_album_id, author, user, details):
    photo_count = details['size']
    title = details['title']
    thumb_src = details['thumb_src']
    cover_id = details['thumb_id']
    url = get_album_url(vk_user_id, vk_album_id)
    album, created = Album.objects.get_or_create(
        src_id=vk_album_id,
        source=Base.ST_VK,
        url=url,
        author=author,
        user=user,
    )
    album.count = photo_count
    album.title = title
    file_name = f'cover_{cover_id}.jpg'
    download_to_file_field(thumb_src, album.cover, file_name=file_name)
    album.update_date = timezone.now()
    album.save()
    return album, created


def update_album(vk_user_id, vk_album_id, author):
    photo_count, error = get_album_size(vk_user_id, vk_album_id)
    is_private = False
    if error == 7:
        # ApiError: [7] Permission to perform this action is denied
        is_private = True
    url = get_album_url(vk_user_id, vk_album_id)
    album, created = Album.objects.get_or_create(
        src_id=vk_album_id,
        source=Base.ST_VK,
        url=url,
        author=author,
        is_private=is_private,
    )
    album.count = photo_count
    album.update_date = timezone.now()
    album.save()
    return album, created


def user_album_updates(user, vk_user_id, *args, **kwargs):
    result = []
    # VK API: Update Author
    author, created = Author.objects.get_or_create(src_id=vk_user_id, source=Base.ST_VK, )
    skip_vk_api = settings.TESTING
    if not skip_vk_api:
        vk_user_info, error = user_info(vk_user_id)
        if vk_user_info and error == 0:
            author = update_author(user, author, vk_user_info)
        else:
            err_text = f'user_album_updates error vk_user_info is None'
            logging.error(
                err_text,
                extra={'vk_user_id': vk_user_id, },
            )
            return result

    # VK API: Список альбомов
    if skip_vk_api:
        albums_info = None
    else:
        albums_info = get_vk_user_albums(vk_user_id)
    if not albums_info:
        # При проблемах с API VK отдаём результат из БД
        q_albums = Album.objects.all()
        q_albums = Album.objects.filter(source=Base.ST_VK, author=author, )
        for item in q_albums:
            try:
                if item.cover:
                    thumb_src = item.cover.url
                else:
                    thumb_src = ''
                result.append(
                    {
                        'id': str(item.src_id),
                        'size': item.count,
                        'title': item.title,
                        'thumb_src': thumb_src,
                        'stats': item.get_album_stats(),
                    },
                )
                # Проверка и обновление списка фоток для оплаченного альбома (проверка внутри)
                celery.current_app.send_task(
                    'core.tasks.run_update_subscribed_albums',
                    kwargs={
                        'user_id': user.id,
                        'album_id': str(item.src_id),
                        # 'is_free': False,
                    },
                    queue='high_priority',
                    retry=True,
                    retry_policy={
                        'max_retries': 1,
                        'interval_start': 0.2,
                        'interval_step': 0.3,
                        'interval_max': 0.3,
                    },
                )
            except Exception as e:
                logging.error(
                    f'user_album_updates: from db, process album item {type(e)}',
                    exc_info=True,
                    extra={'vk_user_id': vk_user_id, },
                )
        return result

    if 'items' not in albums_info:
        err_text = f'user_album_updates error: -items- not found in albums_info'
        logging.error(
            err_text,
            extra={'vk_user_id': vk_user_id, },
        )
        return result

    for item in albums_info['items']:
        try:
            vk_album_id = str(item['id'])
            # Взять url большего формата для фото обложки
            thumb_id = item['thumb_id']
            try:
                mini_photo_url, _ = get_vk_photo_urls(vk_user_id, thumb_id)
                if mini_photo_url:
                    item['thumb_src'] = mini_photo_url
            except Exception as e:
                logging.warning(
                    f'get_vk_photo_urls: {type(e)}',
                    exc_info=True,
                    extra={'vk_album_id': vk_album_id},
                )
            album, created = update_album_detail(vk_user_id, vk_album_id, author, user, item)
            if 'localhost' in settings.DEFAULT_DOMAIN:
                domain = settings.DEFAULT_DOMAIN
            else:
                domain = 'ohaoha.ru'
            full_cover_url = f'https://{domain}/{album.cover.url}'

            result.append(
                {
                    'id': str(album.src_id),
                    'size': album.count,
                    'title': album.title,
                    'thumb_src': full_cover_url,
                    'stats': album.get_album_stats(),
                },
            )
            # Проверка и обновление списка фоток для оплаченного альбома
            celery.current_app.send_task(
                'core.tasks.run_update_subscribed_albums',
                kwargs={
                    'user_id': user.id,
                    'album_id': album.src_id,
                },
                queue='high_priority',
                retry=True,
                retry_policy={
                    'max_retries': 1,
                    'interval_start': 0.2,
                    'interval_step': 0.3,
                    'interval_max': 0.3,
                },
            )
        except Exception as e:
            logging.error(
                f'user_album_updates: process album item {type(e)}',
                exc_info=True,
                extra={'vk_user_id': vk_user_id, },
            )
    return result


def album_preparation(url, *args, **kwargs):
    # Подготовка альбома перед бесплатным поиском
    skip = False
    vk_user_id = get_album_owner(url)
    vk_album_id = get_album_id(url)
    vk_user_info, user_error = user_info(vk_user_id)
    is_private = False
    if user_error == 30:
        # https://vk.com/dev/errors
        is_private = True
    if vk_user_id.startswith('-'):
        vk_user_id = str(vk_user_id).replace('-', '')
        author, created = Author.objects.get_or_create(
            src_id=vk_user_id, source=Base.ST_VK, is_group=True, is_private=is_private,
        )
    else:
        author, created = Author.objects.get_or_create(
            src_id=vk_user_id, source=Base.ST_VK, is_group=False, is_private=is_private,
        )
    if vk_user_info:
        update_author(None, author, vk_user_info)
    else:
        logging.error(
            f'album_preparation error vk_user_info is None',
            extra={
                'vk_user_id': vk_user_id,
                'url': url,
            },
        )
        skip = True
        return None, skip, is_private

    # Смотрим какие есть альбомы у автора
    old_albums = Album.objects.filter(source=Base.ST_VK, author=author, ).order_by('-create_date')
    old_albums_count = old_albums.count()
    if old_albums_count == 0:
        album, created = update_album(vk_user_id, vk_album_id, author)
    else:
        all_private = True
        best_album = None
        for album in old_albums:
            if not album.is_private:
                all_private = False
                best_album = album
                break
        if all_private:
            # Если все предыдущие альбомы были приватными, создаём ещё один
            album, created = update_album(vk_user_id, vk_album_id, author)
        else:
            # Если был ранее не приватный альбом, пропускаем поиск
            album = best_album
            album.update_date = timezone.now()
            album.save()
            skip = True
    if album.is_private:
        is_private = True
    logging.info(f'album_preparation: album {album.id} done, skip {skip}')
    return album.id, skip, is_private


def album_processing(db_album_id, *args, **kwargs):
    if 'search_limit' in kwargs:
        search_limit = kwargs['search_limit']
    else:
        search_limit = 0
    if 'is_free' in kwargs:
        is_free = kwargs['is_free']
    else:
        is_free = True
    album = album_get_work(db_album_id)
    album.update_photos(is_free, search_limit)
    return


def album_get_work(db_album_id):
    album = Album.objects.get(id=db_album_id)
    album.status = Album.PS_WRK
    album.last_search_photos = timezone.now()
    album.save()
    return album


def album_search_done(db_album_id, *args, **kwargs):
    album = Album.objects.get(id=db_album_id)
    album.last_search_photos = timezone.now()
    album.status = Album.PS_DON
    album.save()
    return album.status


def get_album_photo_ids(db_album_id, *args, **kwargs):
    photos = Photo.objects.filter(album_id=db_album_id, search_allowed=True)
    result = []
    for item in photos:
        result.append(item.id)
    return result


def get_search_results_ids(db_photo_id, *args, **kwargs):
    results = SearchResult.objects.filter(photo_id=db_photo_id).values('id')
    result = []
    for item in results:
        result.append(item['id'])
    return result


def free_photo_processing(db_photo_id, *args, **kwargs):
    if 'spend_limit' in kwargs:
        spend_limit = kwargs['spend_limit']
    else:
        spend_limit = 0
    if 'is_free' in kwargs:
        is_free = kwargs['is_free']
    else:
        is_free = True
    photo = Photo.objects.get(id=db_photo_id)
    return photo.search_photo(spend_limit=spend_limit, is_free=is_free)


def check_search_results(db_result_id, *args, **kwargs):
    s_result = SearchResult.objects.get(id=db_result_id)
    return s_result.check_result()


def check_photo_similarity(db_photo_id, *args, **kwargs):
    try:
        photo = Photo.objects.get(id=db_photo_id)
        result = photo.check_similarity()
    except Exception as e:
        result = f'check_photo_similarity: {type(e)} {e}'
        logger.exception(result, exc_info=True, )
    return result


def update_subscribed_albums(user_id, vk_album_id, *args, **kwargs):
    # Найти подписки пользователя, если нет пропускаем обновление
    q_subs = SubscriptionHistory.objects.filter(user_id=user_id, active=True, cancelled=False).order_by('-create_date', 'id')
    if q_subs.count() == 0:
        return 'skip: active subscription not found'
    subscription = q_subs.first()
    if not subscription.expires_date or subscription.expires_date < timezone.now().date():
        return 'skip: active subscription expired'
    if not subscription.is_album_connected(vk_album_id):
        return 'skip: album was not selected in the subscription'
    album: Album
    album = Album.get_by_vk_id(vk_album_id, user_id)
    if not album:
        return f'error: albums not found'
    album.update_photos(is_free=False)
    return f'Success. {album.count} photos'


def start_subscription_search(subs_hist_id):
    subs_hist = SubscriptionHistory.objects.get(id=subs_hist_id)
    # Проверка истекшей подписки
    today = timezone.now().date()
    if today > subs_hist.expires_date:
        logging.error(
            f'running search for expired subscription',
            extra={
                'subs_hist_id': subs_hist_id,
                'expires_date': subs_hist.expires_date,
            },
        )
        return f'Subscription expired'
    max_photos = subs_hist.fix_parameter
    use_photo = 0
    albums_ready = 0
    albums = []
    last_search = timezone.datetime.min.date()
    for vk_album_id in subs_hist.items:
        album: Album
        album = Album.get_by_vk_id(vk_album_id, subs_hist.user.id)
        if not album:
            logging.error(f'start_subscription_search: album not found ({vk_album_id})')
            continue
        albums.append(album)
        if album.status in {Album.PS_DON, Album.PS_NEW}:
            albums_ready += 1
        if album.last_search_photos and album.last_search_photos.date() > last_search:
            last_search = album.last_search_photos.date()
    if len(subs_hist.items) != len(albums):
        logging.error(
            f'not all subscription albums were found',
            extra={
                'subs_hist_id': subs_hist_id,
                'subs_hist.items': subs_hist.items,
                'found_albums': len(albums),
            },
        )
    albums_count = len(albums)
    # Защита от параллельного поиска по подписке
    if albums_count != albums_ready:
        incomplete = albums_count - albums_ready
        return f'there are {incomplete} incomplete works'
    # Защита от перерасхода по подписке (проверка предыдущих запусков)
    # период - месяц
    max_run_in_period = settings.MAX_RUN_IN_PERIOD
    if subs_hist.period_unit != 'M':
        logging.error(f'start_subscription_search: error in period_unit')
        period_count = 1
    else:
        period_count = subs_hist.period_count
    if subs_hist.search_count >= period_count * max_run_in_period:
        logging.info(f'maximum number of launches in the period has been reached')
        return f'maximum number of launches in the period has been reached'
    # Запуск раз в X дней. X = 28 / max_run_in_period
    current_wait_days = timezone.now().date() - last_search
    service_wait_days = (28 / max_run_in_period)
    if current_wait_days.days < service_wait_days:
        return f'skip running: wait {current_wait_days.days} from {service_wait_days}'
    # Запуск поиска
    for album in albums:
        # Обновить информацию по фотографиям (+сбросить разрешение на поиск по фоткам)
        album.update_photos(False)
        # TODO Отметить фото, которые пропали из альбома (для отключения платного поиска по ним)
        # Отметить фото в альбоме по которым можно искать (входят в лимит поиска)
        #  и расставить лимиты по альбомам, чтобы укладываться в тариф и не искать больше
        if use_photo + album.count <= max_photos:
            Photo.objects.filter(album=album).update(search_allowed=True)
            use_photo += album.count
        else:
            remains = use_photo + album.count - max_photos
            use_photo += remains
            Photo.objects.filter(album=album).update(search_allowed=False)
            nested_q = Photo.objects.filter(album=album).order_by('create_date')[:remains]
            Photo.objects.filter(pk__in=nested_q).update(search_allowed=True)
            logging.warning(
                f'start_subscription_search: Some of the photos were not allowed',
                extra={
                    'vk_album_id': album.src_id,
                    'album.count': album.count,
                    'max_photos': max_photos,
                },
            )
        # Запустить платный в фоне поиск
        celery.current_app.send_task(
            'core.tasks.run_paid_album_process',
            kwargs={
                'db_album_id': album.id,
                'is_free': False,
                'spend_limit': settings.PAID_SPEND_LIMIT,
            },
            queue='high_priority',
            routing_key='high_priority',
            countdown=2,
        )
    # Отметка о запуске
    subs_hist.search_count += 1
    subs_hist.save()
    return f'Run search for {albums_count} albums'


def run_active_subscriptions():
    today = timezone.now().date()
    q_subs = SubscriptionHistory.objects.filter(
        active=True, expires_date__gte=today, cancelled=False,
    ).order_by('-create_date', 'id')
    for subs_hist in q_subs:
        celery.current_app.send_task(
            'core.tasks.run_subscription_process',
            kwargs={
                'subs_hist_id': subs_hist.id,
                'is_free': False,
            },
            queue='high_priority',
            routing_key='high_priority',
            countdown=1,
        )
    return f'run {q_subs.count()} subscriptions'
