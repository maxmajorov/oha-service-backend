import logging

from billing.models import SubscriptionHistory
from core.models import Album
from core.models import Author
from core.models import Base
from core.models import update_album
from core.models import update_author
from core.utils.u_request import is_support_sites
from core.utils.u_request import is_valid_url
from core.utils.u_request import url_ok
from core.utils.u_vk import get_album_id
from core.utils.u_vk import get_album_owner
from core.utils.u_vk import get_album_photos
from core.utils.u_vk import is_valid_vk_album
from core.utils.u_vk import user_info
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import pagination
from rest_framework import serializers
from rest_framework import status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)


class AppNotFound(APIException):
    status_code = status.HTTP_200_OK
    default_detail = _('Not found.')
    default_code = '1004'


class AppAccessError(APIException):
    status_code = status.HTTP_200_OK
    default_detail = _('Not enough rights.')
    default_code = '1005'


class AppValidationError(APIException):
    status_code = status.HTTP_200_OK
    default_detail = _('Invalid input.')
    default_code = '1002'


class OtherAlbumFound(APIException):
    status_code = status.HTTP_200_OK
    default_detail = 'Found another already processed user album.'
    default_code = '1100'


class PhotoInfoSerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    src_id = serializers.CharField(read_only=True)


class CustomPagination(pagination.LimitOffsetPagination):
    default_limit = 10
    default_offset = 0
    max_limit = 100

    def get_limit(self, request):
        if self.limit_query_param:
            if self.limit_query_param in request.data:
                try:
                    return pagination._positive_int(
                        request.data[self.limit_query_param],
                        strict=True,
                        cutoff=self.max_limit,
                    )
                except (KeyError, ValueError):
                    pass
            elif self.limit_query_param in request.query_params:
                try:
                    return pagination._positive_int(
                        request.query_params[self.limit_query_param],
                        strict=True,
                        cutoff=self.max_limit,
                    )
                except (KeyError, ValueError):
                    pass
        return self.default_limit

    def get_offset(self, request):
        if self.offset_query_param:
            if self.offset_query_param in request.data:
                try:
                    return pagination._positive_int(
                        request.data[self.offset_query_param],
                    )
                except (KeyError, ValueError):
                    pass
            elif self.offset_query_param in request.query_params:
                try:
                    return pagination._positive_int(
                        request.query_params[self.offset_query_param],
                    )
                except (KeyError, ValueError):
                    pass
        return self.default_offset


def get_valid_url(request_data):
    if 'url' not in request_data:
        raise AppValidationError(detail={'message': 'Url not in data', 'code': '1001'}, code='1001')
    url = request_data['url']
    if not is_valid_url(url):
        raise AppValidationError(detail={'message': 'Invalid url', 'code': '1002'}, code='1002')

    if not is_support_sites(url):
        raise AppValidationError(detail={'message': 'Support only vk.com', 'code': '1003'}, code='1003')

    if not is_valid_vk_album(url):
        raise AppValidationError(detail={'message': 'Requires a specific album', 'code': '2002'}, code='2002')

    if not url_ok(url):
        raise AppValidationError(detail={'message': 'Album not available', 'code': '2001'}, code='2001')
    return url


def test_access_vk_url(url):
    owner_id = get_album_owner(url)
    album_id = get_album_id(url)
    count, result = get_album_photos(owner_id=owner_id, album_id=album_id, limit=1, skip_error=True)
    if not result:
        raise AppValidationError(detail={'message': 'Albums not found', 'code': '2004'}, code='2004')
    return


def get_db_album(url):
    # Для извлечения результатов бесплатного поиска
    vk_user_id = get_album_owner(url)
    vk_album_id = get_album_id(url)
    q_author = Author.objects.filter(src_id=vk_user_id, source=Base.ST_VK)
    if not q_author.exists():
        # error 1: передан url в котором указан не изместный автор
        logging.error(
            f'get_db_album error VK user was not found',
            extra={'url': url},
        )
        raise AppNotFound(detail={'message': 'VK user was not found', 'code': '2003'}, code='2003')
    author = q_author.first()
    if author.is_private:
        vk_user_info, error = user_info(vk_user_id)
        if not vk_user_info or error > 0:
            # error 2: у автора альбома закрытый профиль, и остаётся закрытым
            raise AppAccessError(detail={'message': 'Profile is private', 'code': '2005'}, code='2005')
        # Ok: профиль стал публичным
        author = update_author(None, author, vk_user_info)
        # создаём альбом
        album, created = update_album(vk_user_id, vk_album_id, author)
        if album.is_private:
            # error 3: альбом является закрытым
            raise AppAccessError(detail={'message': 'Album is private', 'code': '2006'}, code='2006')
    q_album = Album.objects.filter(source=Base.ST_VK, author=author)
    if not q_album.exists():
        raise AppNotFound(detail={'message': 'Albums not found', 'code': '2004'}, code='2004')
    q_same_album = q_album.filter(src_id=vk_album_id)
    q_other_album = q_album.exclude(src_id=vk_album_id).order_by('-create_date')
    if q_same_album.count() > 1:
        # TODO: Учесть ситуацию когда несколько альбомов пользователя уже в платном поиске,
        #  а кто-то ищет его альбом бесплатно
        return q_same_album.first()
    if q_same_album.exists():
        return q_same_album.first()
    if q_other_album.exists():
        other_album: Album
        other_album = q_other_album.first()
        raise OtherAlbumFound(
            detail={
                'message': 'Another album has already been processed',
                'url': other_album.url,
                'code': '1100',
            }, code='1100',
        )
    logger.error('get_db_album - unexpected behavior')
    raise AppNotFound(detail={'message': 'Albums not found', 'code': '2004'}, code='2004')


def get_subscription_albums(user) -> QuerySet:
    q_subs = SubscriptionHistory.objects.filter(user=user, active=True, cancelled=False).order_by('-create_date', 'id')
    if q_subs.count() == 0:
        logger.error(
            'get_subscription_albums - active subscription not found',
            extra={'user': user, },
        )
        raise AppNotFound(detail={'message': 'Subscription not found', 'code': '2004'}, code='2004')
    subscription = q_subs.first()
    result = []
    for vk_album_id in subscription.items:
        album = Album.get_by_vk_id(vk_album_id, user.id)
        if album:
            result.append(album)
    return result
