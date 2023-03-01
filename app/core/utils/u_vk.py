import logging
import math
import re

import vk_api

vk_session = vk_api.VkApi(token='51e1929151e1929151e1929121518d3f00551e151e192910c8ff584e0433e1a758493a4')
THUMBNAILS_SIZE = 400

logger = logging.getLogger(__name__)


class VkPhotoInstance:
    id = ''
    album_id = '',
    owner_id = '',
    text = '',
    mini_photo_url = '',
    maxi_photo_url = '',

    def __index__(self):
        pass


def is_valid_vk_album(url):
    # VK albums list https://vk.com/albums158184342
    # VK album https://vk.com/album158184342_242810703
    # VK photo https://vk.com/photo158184342_379329760
    x = re.search(r'.*vk\.com.*album.*_.*', url)
    if x:
        return True
    return False


def get_album_url(vk_user_id, vk_album_id):
    return f'https://vk.com/album{vk_user_id}_{vk_album_id}'


def get_album_owner(url):
    try:
        vk_user_id = url.split('.com/album')[1].split('_')[0]
    except IndexError as ex:
        logger.error(
            f'get_album_owner [{ex}]',
            exc_info=True,
            extra={'url': url, },
        )
        return None
    except Exception as ex:
        logger.error(
            f'get_album_owner [{ex}]',
            exc_info=True,
            extra={'url': url, },
        )
        return None
    return vk_user_id


def user_info(vk_user_id):
    info = None
    error = 0
    try:
        if vk_user_id.startswith('-'):
            response = vk_session.method(
                'groups.getById',
                {
                    'group_ids': vk_user_id,
                    'fields': 'members_count, counters',
                },
            )
        else:
            response = vk_session.method(
                'users.get',
                {
                    'user_ids': vk_user_id,
                    'fields': 'bdate, followers_count, counters',
                    'name_case': 'nom',
                },
            )
        if len(response) == 0:
            return info, error
        info = response[0]
    except vk_api.exceptions.ApiError as ae:
        logging.error(
            f'VK user_info, Api Error: [{ae.code}] {ae.error["error_msg"]}',
            exc_info=True,
            extra={'vk_user_id': vk_user_id, },
        )
        error = ae.code
    except Exception as ex:
        logging.error(
            f'VK user_info error {type(ex)}',
            exc_info=True,
            extra={'vk_user_id': vk_user_id, },
        )
        error = 1
    return info, error


def get_album_id(url):
    try:
        vk_album_id = url.split('album')[1].split('_')[1]
    except IndexError as ex:
        logger.error(
            f'get_album_id [{ex}]',
            exc_info=True,
            extra={'url': url, },
        )
        return None
    except Exception as ex:
        logger.error(
            f'get_album_id [{ex}]',
            exc_info=True,
            extra={'url': url, },
        )
        return None
    #
    # if vk_album_id == '00':
    #     vk_album_id = 'wall'
    # elif vk_album_id == '000':
    #     vk_album_id = 'saved'
    # elif vk_album_id == '0':
    #     vk_album_id = 'profile'
    return vk_album_id


def get_album_size(owner_id, album_id):
    count = 0
    error = 0
    try:
        response = vk_session.method(
            'photos.get',
            {
                'owner_id': owner_id,
                'album_id': album_id,
                'rev': 0,
                'extended': 0,
                'feed_type': 'photo',
                'photo_sizes': 0,
                'count': 1,
            },
        )
        count = response['count']
    except vk_api.exceptions.ApiError as ae:
        logging.error(
            f'get_album_size, VK Api Error: [{ae.code}] {ae.error["error_msg"]}',
            exc_info=True,
            extra={
                'owner_id': owner_id,
                'album_id': album_id,
            },
        )
        error = ae.code
    except Exception as ex:
        logging.error(
            f'get_album_size: {type(ex)}',
            exc_info=True,
            extra={
                'owner_id': owner_id,
                'album_id': album_id,
            },
        )
        error = 1
    return count, error


def _get_thumbnails_photo_urls(photo_sizes):
    mini_photo = {'width': 0, }
    maxi_photo = {'width': 0, }
    for size_data in photo_sizes:
        height = size_data['height']
        width = size_data['width']
        url = size_data['url']
        i_type = size_data['type']
        if width > 0:
            if THUMBNAILS_SIZE >= width > mini_photo['width']:
                mini_photo['url'] = url
                mini_photo['width'] = width
                mini_photo['height'] = height
            if width > THUMBNAILS_SIZE and width > maxi_photo['width']:
                maxi_photo['url'] = url
                maxi_photo['width'] = width
                maxi_photo['height'] = height
        else:
            if i_type == 's' or i_type == 'm':
                mini_photo['url'] = url
                mini_photo['width'] = width
                mini_photo['height'] = height
            elif i_type == 'y' or i_type == 'z' or i_type == 'w':
                maxi_photo['url'] = url
                maxi_photo['width'] = width
                maxi_photo['height'] = height
    if 'url' in mini_photo and 'url' in maxi_photo:
        if not maxi_photo['url']:
            logging.error(
                f'_get_thumbnails_photo_urls: empty maxi_photo url',
                extra={
                    'photo_sizes': photo_sizes,
                    'maxi_photo': maxi_photo,
                    'mini_photo': mini_photo,
                },
            )
        return mini_photo['url'], maxi_photo['url']
    return '', ''


def _photos_get_parse(items):
    result = []
    for photo_data in items:
        album_id = photo_data['album_id']
        photo_id = photo_data['id']
        owner_id = photo_data['owner_id']
        text = photo_data['text']
        sizes = photo_data['sizes']
        mini_photo_url, maxi_photo_url = _get_thumbnails_photo_urls(sizes)
        item = VkPhotoInstance()
        item.album_id = album_id
        item.id = photo_id
        item.owner_id = owner_id
        item.text = text
        item.maxi_photo_url = maxi_photo_url
        item.mini_photo_url = mini_photo_url
        result.append(item)
    return result


def get_vk_photo_urls(vk_owner_id, vk_photo_id, access_key=None):
    #
    sizes = []
    photos = f'{vk_owner_id}_{vk_photo_id}'
    if access_key:
        photos += f'_{access_key}'
    try:
        response = vk_session.method(
            'photos.getById',
            {
                'photos': photos,
            },
        )
        if not response or len(response) == 0:
            return '', ''
        photo_data = response[0]
        sizes = photo_data['sizes']
    except Exception as ex:
        logging.error(
            f'get_vk_photo_urls: {type(ex)}',
            exc_info=True,
            extra={
                'vk_owner_id': vk_owner_id,
                'vk_photo_id': vk_photo_id,
                'access_key': access_key,
            },
        )
    return _get_thumbnails_photo_urls(sizes)


def get_album_photos(owner_id, album_id, limit=0, skip_error=False):
    batch_size = 1000
    result = []
    count = 0
    if 0 < limit < batch_size:
        batch_size = limit
    try:
        response = vk_session.method(
            'photos.get',
            {
                'owner_id': owner_id,
                'album_id': album_id,
                'rev': 0,
                'extended': 0,
                'feed_type': 'photo',
                'photo_sizes': 0,
                'offset': 0,
                'count': batch_size,
            },
        )
        count = response['count']
        items = response['items']
        result = _photos_get_parse(items)
        for j in range(1, max(1, math.floor(count / batch_size))):
            offset = j * batch_size
            if len(result) + batch_size > limit:
                batch_size = limit - len(result)
            response = vk_session.method(
                'photos.get',
                {
                    'owner_id': owner_id,
                    'album_id': album_id,
                    'rev': 0,
                    'extended': 0,
                    'feed_type': 'photo',
                    'photo_sizes': 0,
                    'offset': offset,
                    'count': batch_size,
                },
            )
            items = response['items']
            result.extend(_photos_get_parse(items))
    except Exception as ex:
        if not skip_error:
            logging.error(
                f'get_album_photos: {type(ex)}',
                exc_info=True,
                extra={
                    'owner_id': owner_id,
                    'album_id': album_id,
                    'limit': limit,
                },
            )
    return count, result


def _photos_search_parse(items):
    results = []
    for item in items:
        if 'owner_id' in item and 'post_id' in item and 'user_id' in item:
            results.append(f'https://vk.com/wall{item["owner_id"]}_{item["post_id"]}')
        elif 'owner_id' in item and 'id' in item:
            results.append(f'https://vk.com/photo{item["owner_id"]}_{item["id"]}')
    return results


def search_photo(owner_id, photo_id):
    batch_size = 100
    results = []
    try:
        response = vk_session.method(
            'photos.search',
            {
                'q': f'copy:photo{owner_id}_{photo_id}',
                'count': batch_size,
                'offset': 0,
            },
        )
        count = response['count']
        results = _photos_search_parse(response['items'])
        for j in range(1, max(1, math.floor(count / batch_size))):
            response = vk_session.method(
                'photos.search',
                {
                    'q': f'copy:photo{owner_id}_{photo_id}',
                    'count': batch_size,
                    'offset': j * batch_size,
                },
            )
            results.extend(_photos_search_parse(response['items']))
    except Exception as ex:
        logging.error(
            f'search_photo: {type(ex)}',
            exc_info=True,
            extra={
                'owner_id': owner_id,
                'photo_id': photo_id,
            },
        )
    return results


def get_vk_user_albums(vk_user_id):
    info = None
    try:
        response = vk_session.method(
            'photos.getAlbums',
            {
                'owner_id': vk_user_id,
                'need_covers': 1,
                'need_system': 0,
            },
        )
        info = response
    except Exception as ex:
        logging.error(
            f'VK get_subscription_albums error {type(ex)}',
            exc_info=True,
            extra={'vk_user_id': vk_user_id, },
        )
    return info
