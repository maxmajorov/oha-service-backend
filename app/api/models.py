import logging

from allauth.socialaccount.models import SocialAccount
from billing.models import Invoice
from billing.models import Subscription
from billing.models import SubscriptionHistory
from core.models import Album
from core.models import DomainData
from core.models import Photo
from core.models import SearchResult
from core.models import user_album_updates
from core.utils.u_rest_framework import CustomPagination
from core.utils.u_rest_framework import get_db_album
from core.utils.u_rest_framework import PhotoInfoSerializer
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import When
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)


class AppValidationError(APIException):
    status_code = status.HTTP_200_OK
    default_detail = _('Invalid input.')
    default_code = '1000'


def get_album_results(url):
    result = {}
    album = get_db_album(url)
    if album.status == Album.PS_DON:
        q_duplicates = Photo.objects.filter(
            album=album,
            duplicates__isnull=False,
            duplicates__found_image=True,
        ).values('pk').annotate(
            duplicate_count=Count('pk'),
        ).order_by('-duplicate_count')

        q_duplicates_all = Photo.objects.filter(
            album=album,
            duplicates__isnull=False,
        ).values('pk').annotate(duplicate_count=Count('pk')).order_by('-duplicate_count')
        photo_with_duplicate = q_duplicates_all.count()
        if photo_with_duplicate > 0:
            most_copied = q_duplicates.first()
            duplicate_count = most_copied['duplicate_count']
            most_copied_photo_id = most_copied['pk']
            most_copied_photo = Photo.objects.get(pk=most_copied_photo_id)
            q_domains = DomainData.objects.filter(
                searchresult__photo=most_copied_photo_id,
                searchresult__similar_images=False,
            ).distinct().values(
                'id', 'domain',
            ).annotate(count=Count('pk')).order_by('-count')
            sites = []
            for site in q_domains:
                if 'youtube.com' in site['domain']:
                    continue
                q_results = SearchResult.objects.filter(
                    photo_id=most_copied_photo_id,
                    domain_id=site['id'],
                    found_image=True,
                    similar_images=False,
                )
                if q_results.count() > 0:
                    for s_result in q_results:
                        sites.append({
                            'page_url': s_result.page_url,
                            'title': s_result.title,
                            'mention': s_result.mention_exact_match,
                            'domain': site['domain'],
                        })
            result['results'] = {
                'sites': sites,
                'most_copied_photo': most_copied_photo.maxi_url,
                'duplicate_count': duplicate_count,
                'photo_with_duplicate': photo_with_duplicate,
            }
        else:
            result['results'] = {
                'sites': [],
                'most_copied_photo': '',
                'duplicate_count': 0,
                'photo_with_duplicate': photo_with_duplicate,
            }
    else:
        q_duplicates = Photo.objects.filter(album=album, duplicates__isnull=False).values('pk').annotate(
            duplicate_count=Count('pk'),
        ).order_by('-duplicate_count')
        photo_with_duplicate = q_duplicates.count()
        domains_count = DomainData.objects.filter(searchresult__photo__album=album).distinct().count()
        duplicates_count = SearchResult.objects.filter(photo__album=album).count()
        checked_duplicates_count = SearchResult.objects.filter(
            photo__album=album,
            found_image=True,
            similar_images=False,
        ).count()
        # Progress
        result['progress'] = {
            'album_photo_count': album.count,
            'photo_with_duplicate': photo_with_duplicate,
            'domains_with_duplicate': domains_count,
            'duplicates_count': duplicates_count,
            'checked_duplicates_count': checked_duplicates_count,
        }
    return result


def get_user_tariffs(user):
    result = {}
    # TODO: придумать механизм получения последнего тарифа (для удобного переключения на новые тарифы)
    q_subs = Subscription.objects.filter(active=True)
    cnt_subs = q_subs.count()
    if cnt_subs != 3:
        logging.error(
            f'get_user_tariffs error: -Subscription- not found (count {cnt_subs}) for {user}',
        )
        raise AppValidationError(detail={'message': f'Subscriptions not found', 'code': '3001'}, code='3001')
    result['tariffs'] = []
    for item in q_subs:
        result['tariffs'].append({
            'name': item.name,
            'code': item.sys_code,
            'price': item.price,
            'parameter': item.parameter,
        })
    return result


def get_request_parameter(request_data, name):
    if name not in request_data:
        raise AppValidationError(detail={'message': f'{name} not in data', 'code': '1001'}, code='1001')
    return request_data[name]


def get_user_invoice(user, sys_code, items):
    result = {}
    q_subs = Subscription.objects.filter(sys_code=sys_code, active=True)
    if q_subs.count() != 1:
        raise AppValidationError(detail={'message': f'Subscription not found', 'code': '3001'}, code='3001')
    subscription = q_subs.first()
    q_inv = Invoice.objects.filter(user=user, status=Invoice.ST_NEW, subscription=subscription)
    if q_inv.count() == 0:
        invoice = Invoice.objects.create(
            user=user,
            status=Invoice.ST_NEW,
            subscription=subscription,
            amount=subscription.price,
            items=items,
        )
    else:
        invoice = q_inv.first()
        invoice.amount = subscription.price
        invoice.items = items
        invoice.save()
    if not invoice.ext_id:
        logging.error(
            f'VK get_user_invoice: empty label',
            exc_info=True,
            extra={'ext_id': invoice.ext_id, 'invoice_id': invoice.id},
        )
    result['label'] = invoice.ext_id
    result['receiver'] = settings.YM_WALLET
    return result


def get_invoice_status(user, label):
    q_inv = Invoice.objects.filter(user=user, ext_id=label)
    if q_inv.count() != 1:
        raise AppValidationError(detail={'message': f'Invoice not found', 'code': '3003'}, code='3003')
    invoice = q_inv.first()
    result = {'status': invoice.get_status(), 'code': invoice.status}
    return result


def get_subscription(user):
    result = {}
    q_subs = SubscriptionHistory.objects.filter(user=user, active=True, cancelled=False).order_by('-create_date', 'id')
    if q_subs.count() == 0:
        return result
    subscription = q_subs.first()
    if subscription.subscription:
        sys_code = subscription.subscription.sys_code
        parameter = subscription.subscription.parameter
    else:
        logging.error(
            f'get_subscription error: subscription.subscription not found',
            extra={'user': user, },
        )
        raise AppValidationError(detail={'message': f'Subscription terms not found', 'code': '3002'}, code='3002')
    result['expires_date'] = subscription.expires_date
    result['activate_date'] = subscription.activate_date
    result['sys_code'] = sys_code
    result['parameter'] = parameter
    result['items'] = subscription.items
    return result


def get_user_info(user: User):
    result = {
        'user_name' : user.username,
        'first_name' : user.first_name,
        'user_albums': [],
        'subscription': {},
    }
    if user.is_anonymous:
        return result
    acc_q = SocialAccount.objects.filter(user=user)
    if acc_q.count() == 0:
        result['user_albums'] = []
        logging.error(
            'get_user_info: There is no information about the albums yet',
            extra={'user_id': user.id, },
        )
    else:
        acc = acc_q.first()
        vk_user_id = acc.uid
        # Альбомы
        result['user_albums'] = user_album_updates(user, vk_user_id)
        # Имя и фото
        if acc.extra_data and 'first_name' in acc.extra_data:
            result['first_name'] = acc.extra_data['first_name']
        if acc.extra_data and 'last_name' in acc.extra_data:
            result['last_name'] = acc.extra_data['last_name']
        if acc.extra_data and 'photo_medium' in acc.extra_data:
            result['photo'] = acc.extra_data['photo_medium']
    # Подписка
    result['subscription'] = get_subscription(user)
    return result


def get_album_page(request, vk_album_id, user):
    album = Album.get_by_vk_id(vk_album_id, user.id)
    if not album:
        return {}
    # photos = Photo.objects.filter(album_id=album.id).order_by('src_id')
    photos = Photo.objects.filter(album_id=album.id).annotate(
        results_count=Count(Case(When(duplicates__found_image=True, then=1), output_field=IntegerField(), )),
    ).order_by('-results_count', 'src_id')
    paginator = CustomPagination()
    result_page = paginator.paginate_queryset(photos, request)
    serializer = PhotoInfoSerializer(result_page, many=True, context={'request': request})
    return serializer.data


def _get_photo_results(vk_album_id, vk_photo_id, user_id):
    result = {}
    photo = Photo.get_by_vk_id(vk_photo_id, user_id)
    if not photo:
        logging.error(
            f'get_photo_results: photo not found',
            extra={'vk_album_id': vk_album_id, 'vk_photo_id': vk_photo_id},
        )
        return result
    q_domains = DomainData.objects.filter(
        searchresult__photo=photo,
        searchresult__similar_images=False,
    ).distinct().values('id', 'domain').annotate(count=Count('pk')).order_by('-count')
    sites = []
    duplicate_count = 0
    for site in q_domains:
        if 'youtube.com' in site['domain']:
            continue
        q_results = SearchResult.objects.filter(
            photo=photo,
            domain_id=site['id'],
            found_image=True,
            similar_images=False,
        )
        duplicate_count += q_results.count()
        if q_results.count() > 0:
            for s_result in q_results:
                sites.append({
                    'page_url': s_result.page_url,
                    'title': s_result.title,
                    'mention': s_result.mention_exact_match,
                    'domain': site['domain'],
                })
    photo_result = {
        'album_id': vk_album_id,
        'photo_id': vk_photo_id,
        'sites': sites,
        'mini_url': photo.mini_url,
        'maxi_url': photo.maxi_url,
        'duplicate_count': duplicate_count,
        'in_progress': photo.search_date is None,
    }
    return photo_result


def get_album_page_stats(vk_album_id, photos, user_id):
    album = Album.get_by_vk_id(vk_album_id, user_id)
    album_search_done = album.status == Album.PS_DON
    result = {
        'album_search_done': album_search_done,
        'photos': [],
    }
    for s_photo in photos:
        vk_photo_id = s_photo['src_id']
        photo_result = _get_photo_results(vk_album_id, vk_photo_id, user_id)
        result['photos'].append(photo_result)
    return result


def get_photo_results(vk_album_id, vk_photo_id, user_id):
    photo_result = _get_photo_results(vk_album_id, vk_photo_id, user_id)
    return photo_result


def expand_subscription(user, items):
    if len(items) == 0:
        raise AppValidationError(detail={'message': f'Empty items', 'code': '1001'}, code='1001')
    q_subs = SubscriptionHistory.objects.filter(user=user, active=True, cancelled=False).order_by('-create_date', 'id')
    if q_subs.count() == 0:
        logging.error(
            f'expand_subscription: active subscription not found',
            extra={'user': user, 'items': items},
        )
        raise AppValidationError(detail={'message': f'Subscription not found', 'code': '3001'}, code='3001')
    subscription: SubscriptionHistory
    subscription = q_subs.first()
    today = timezone.now().date()
    if not subscription.expires_date or subscription.expires_date < today:
        logging.error(
            f'expand_subscription: active subscription expired',
            extra={'user': user, 'items': items, 'expires_date': subscription.expires_date},
        )
        raise AppValidationError(detail={'message': f'Subscription not found', 'code': '3001'}, code='3001')
    old_albums = []
    new_albums = []
    for vk_album_id in items:
        if subscription.is_album_connected(vk_album_id):
            old_albums.append(vk_album_id)
        else:
            new_albums.append(vk_album_id)
    if len(new_albums) == 0:
        logging.error(
            f'expand_subscription: Subscription is already enabled for albums',
            extra={'user': user, 'items': items},
        )
        raise AppValidationError(
            detail={'message': f'Subscription is already enabled for albums', 'code': '3004'},
            code='3004',
        )
    # Проверка лимита подписка
    paid_limit = subscription.fix_parameter
    expand_count = 0
    album: Album
    for vk_album_id in subscription.items:
        album = Album.get_by_vk_id(vk_album_id, user.id)
        album.update_photos(is_free=False)
        expand_count += album.count
    for vk_album_id in new_albums:
        album = Album.get_by_vk_id(vk_album_id, user.id)
        album.update_photos(is_free=False)
        expand_count += album.count
    if expand_count > paid_limit:
        logging.error(
            f'expand_subscription: Number of photos in Albums exceeds the paid limit',
            extra={'user': user, 'items': items, 'paid_limit': paid_limit, 'expand_count': expand_count, },
        )
        raise AppValidationError(
            detail={'message': f'The number of photos in Albums exceeds the paid limit', 'code': '3005'},
            code='3005',
        )
    # Замена подписки на новую - расширенную
    expand_items = []
    expand_items.extend(subscription.items)
    expand_items.extend(new_albums)
    # отмена старой подписки
    subscription.cancelled = True
    subscription.save()
    # создание новой подписки
    SubscriptionHistory.objects.create(
        user=user,
        subscription=subscription.subscription,
        invoice=subscription.invoice,
        items=expand_items,
        active=True,
        cancelled=False,
        activate_date=subscription.activate_date,
        expires_date=subscription.expires_date,
        fix_parameter=subscription.fix_parameter,
        period_unit=subscription.period_unit,
        period_count=subscription.period_count,
    )
    return {'detail': 'OK'}
