from core.models import Album
from core.models import Author
from core.models import Base
from core.models import EngineCounter
from core.models import Photo
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ..models import ChartTimeLine


class ChartTimeLineTest(TestCase):
    """ Test module for Album model """
    def setUp(self):
        self.maxDiff = None
        self.email = 'user@example.com'
        self.user, created = User.objects.get_or_create(
            username='user',
            is_active=True,
            email=self.email,
            password='p@$$w0rd',
        )
        self.vk_user_id = '97596650'
        self.vk_album_id = '271565395'
        self.url = f'https://vk.com/album{self.vk_user_id}_{self.vk_album_id}'
        self.vk_photo_ids = ['457239388', '457239387', '457239386', '457239385', '457239384', '457239382']
        self.domains = ['one.com', 'two.ru', 'three.com', 'four.ru', 'five.com', 'six.ru']
        self.results = {
            '457239388': ['one.com', ],
            '457239387': [],
            '457239386': ['one.com', 'two.ru'],
            '457239385': ['two.ru', 'three.com', 'four.ru', 'five.com', ],
            '457239384': ['four.ru', 'five.com', 'six.ru', ],
            '457239382': ['one.com', 'two.ru', 'three.com', 'four.ru', 'five.com', 'six.ru', ],
        }
        # Author
        author, created = Author.objects.get_or_create(src_id=self.vk_user_id, source=Base.ST_VK, )
        # Album
        album, created = Album.objects.get_or_create(
            src_id=self.vk_album_id,
            source=Base.ST_VK,
            url=self.url,
            author=author,
            user=self.user,
            status=Album.PS_DON,
            last_search_photos=timezone.now(),
        )
        self.second_search_date = timezone.now().date()
        self.first_search_date = self.second_search_date - timezone.timedelta(days=1)
        self.zero_search_date = self.first_search_date - timezone.timedelta(days=1)
        # Photo
        for vk_photo_id in self.vk_photo_ids:
            photo, created = Photo.objects.get_or_create(
                source=Photo.ST_VK,
                source_id=vk_photo_id,
                src_id=vk_photo_id,
                mini_url=f'https://sun9-28.userapi.com/{vk_photo_id}/image.jpg',
                maxi_url=f'https://sun9-13.userapi.com/{vk_photo_id}/image.jpg',
                source_album=self.vk_album_id,
                source_owner=self.vk_user_id,
                user=self.user,
                album=album,
            )
            # first_search_date
            EngineCounter.objects.get_or_create(
                user=self.user,
                album=album,
                photo=photo,
                engine=EngineCounter.SE_IMAGE,
                search_date=self.first_search_date,
                name='Yandex',
                search_count=11,
                result_count=1,
            )
            EngineCounter.objects.get_or_create(
                user=self.user,
                album=album,
                photo=photo,
                engine=EngineCounter.SE_IMAGE,
                search_date=self.first_search_date,
                name='Google',
                search_count=12,
                result_count=2,
            )
            # second_search_date
            EngineCounter.objects.get_or_create(
                user=self.user,
                album=album,
                photo=photo,
                engine=EngineCounter.SE_IMAGE,
                search_date=self.second_search_date,
                name='Yandex',
                search_count=23,
                result_count=2,
            )
            EngineCounter.objects.get_or_create(
                user=self.user,
                album=album,
                photo=photo,
                engine=EngineCounter.SE_IMAGE,
                search_date=self.second_search_date,
                name='Google',
                search_count=22,
                result_count=3,
            )

    def test_engine_timeline(self):
        chart = ChartTimeLine(group='day', group_count=2, title='')
        chart.append_by_queryset(
            queryset=EngineCounter.objects.all(),
            time_field='search_date',
            label='Число запросов по поисковым системам',
            split_field='name',
            sum_field='search_count',
        )
        data = chart.get_chart_data()
        valid_data = dict(
            type='bar', data={
                'labels': [
                    self.zero_search_date.strftime('%d.%m.%y'),
                    self.first_search_date.strftime('%d.%m.%y'),
                    self.second_search_date.strftime('%d.%m.%y'),
                ], 'datasets': [
                    {
                        'label': 'Google', 'data': [0, 72, 132], 'backgroundColor': 'rgba(92, 186, 230, 0.2)',
                        'borderColor': 'rgba(92, 186, 230, 1)', 'borderWidth': 2,
                    },
                    {
                        'label': 'Yandex', 'data': [0, 66, 138], 'backgroundColor': 'rgba(182, 217, 87, 0.2)',
                        'borderColor': 'rgba(182, 217, 87, 1)', 'borderWidth': 2,
                    },
                ],
            },
                              options={
                                  'responsive': True, 'legend': {'position': 'top'},
                                  'title': {'display': False, 'text': ''},
                                  'scales': {'yAxes': [{'ticks': {'suggestedMin': 0, 'stepSize': 20}}]},
                              },
        )
        self.assertEqual(data, valid_data,)
