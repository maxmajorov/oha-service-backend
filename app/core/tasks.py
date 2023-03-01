import logging

from celery import chain
from celery import group
from celery import shared_task
from django.conf import settings
from django.db import transaction

from .models import album_get_work
from .models import album_preparation
from .models import album_processing
from .models import album_search_done
from .models import check_photo_similarity
from .models import check_search_results
from .models import free_photo_processing
from .models import get_album_photo_ids
from .models import get_search_results_ids
from .models import run_active_subscriptions
from .models import start_subscription_search
from .models import update_subscribed_albums


logger = logging.getLogger(__name__)


@shared_task
@transaction.atomic
def run_finish_album_process(group_results, db_album_id, *args, **kwargs):
    logging.info(f'run_finish_album_process: db_album_id - {db_album_id}')
    album_search_done(db_album_id, *args, **kwargs)
    return


@shared_task
@transaction.atomic
def run_check_search_results(db_result_id, *args, **kwargs):
    # SearchResult level - 3, step 1
    return check_search_results(db_result_id, *args, **kwargs)


@shared_task
@transaction.atomic
def run_check_results_process(db_result_id, *args, **kwargs):
    # ! obsolete
    # SearchResult level - 3
    # chain(run_check_search_results.s(db_result_id), run_check_similarity.s(db_result_id))()
    return


@shared_task
@transaction.atomic
def run_check_photo_similarity(chain_results, db_photo_id, *args, **kwargs):
    check_photo_similarity(db_photo_id)
    return


@shared_task
@transaction.atomic
def run_check_photo_search(chain_results, db_photo_id, *args, **kwargs):
    # Photo level - 2, step 2
    result_ids = get_search_results_ids(db_photo_id, *args, **kwargs)
    if len(result_ids) == 0:
        return
    task_group = group(run_check_search_results.s(db_result_id) for db_result_id in result_ids)
    chain(task_group, run_check_photo_similarity.s(None, db_photo_id))()
    return


@shared_task
def run_free_photo_search(db_photo_id, *args, **kwargs):
    # Photo level - 2, step 1
    free_photo_processing(db_photo_id, *args, **kwargs)
    return


@shared_task
@transaction.atomic
def run_free_photo_search_group(db_album_id, *args, **kwargs):
    photo_ids = get_album_photo_ids(db_album_id, *args, **kwargs)
    search_group = group(run_free_photo_search.s(photo_id) for photo_id in photo_ids)
    search_group.apply_async()
    return


@shared_task
@transaction.atomic
def run_full_check_similarity(db_album_id, *args, **kwargs):
    photo_ids = get_album_photo_ids(db_album_id, *args, **kwargs)
    search_group = group(run_check_photo_similarity.s(None, photo_id) for photo_id in photo_ids)
    search_group.apply_async()
    return


@shared_task
def run_free_photo_process(photo_id, *args, **kwargs):
    # Photo level - 2
    chain(run_free_photo_search.s(photo_id), run_check_photo_search.s(photo_id))()
    return


@shared_task
@transaction.atomic
def run_full_check_results(db_album_id, *args, **kwargs):
    album_get_work(db_album_id)
    photo_ids = get_album_photo_ids(db_album_id, *args, **kwargs)
    check_group = group(run_check_photo_search.s(None, photo_id) for photo_id in photo_ids)
    chain(check_group, run_finish_album_process.s(db_album_id))()
    return


@shared_task()
@transaction.atomic
def run_free_album_process(db_album_id, *args, **kwargs):
    # Album level - 1
    album_processing(db_album_id, *args, **kwargs)
    photo_ids = get_album_photo_ids(db_album_id, *args, **kwargs)
    if len(photo_ids) == 0:
        return f'0 photos'
    # search_group = group(run_free_photo_search.s(photo_id) for photo_id in photo_ids)
    # search_group.apply_async()
    # check_group = group(run_check_photo_search.s(photo_id) for photo_id in photo_ids)
    # chain(check_group, run_finish_album_process.s(db_album_id))()
    search_group = group(run_free_photo_process.s(photo_id) for photo_id in photo_ids)
    chain(search_group, run_finish_album_process.s(db_album_id))()
    return f'run process for {len(photo_ids)} photos'


@shared_task()
@transaction.atomic
def run_free_album_search(url, *args, **kwargs):
    # Url level - 0
    db_album_id, skip, is_private = album_preparation(url, *args, **kwargs)
    if not db_album_id:
        logging.error(
            f'run_free_album_search: db_album_id is None',
            extra={'url': url, },
        )
        return 'Error: db_album_id is None'
    if skip:
        status = album_search_done(db_album_id, *args, **kwargs)
        return f'Info: skip db_album_id ({status})'
    if is_private:
        # Профиль или альбом не доступны из-за настроек приватности
        return f'Info: skip db_album_id - for reasons of privacy'
    run_free_album_process.apply_async(
        kwargs={
            'db_album_id': db_album_id,
            'search_limit': settings.FREE_SEARCH_LIMIT,
            'spend_limit': settings.FREE_SPEND_LIMIT,
            'is_free': True,
        },
        queue='high_priority',
        countdown=1,
    )
    return f'run free album process'


@shared_task()
@transaction.atomic
def run_update_subscribed_albums(user_id, album_id, *args, **kwargs):
    return update_subscribed_albums(user_id, album_id, *args, **kwargs)


@shared_task()
@transaction.atomic
def run_subscription_process(subs_hist_id, *args, **kwargs):
    # Фоновый запуск обновления информации по альбомам и запуск Платного поиска
    return start_subscription_search(subs_hist_id)


@shared_task()
@transaction.atomic
def run_paid_album_process(db_album_id, *args, **kwargs):
    # Album level - 1
    album_get_work(db_album_id)
    photo_ids = get_album_photo_ids(db_album_id, *args, **kwargs)
    if len(photo_ids) == 0:
        logging.error(
            f'run_paid_album_process: not found allowed photos',
            extra={'db_album_id': db_album_id, },
        )
        return f'Skip: not found allowed photos'
    # search_group = group(run_free_photo_search.s(photo_id) for photo_id in photo_ids)
    # search_group.apply_async()
    # check_group = group(run_check_photo_search.s(photo_id) for photo_id in photo_ids)
    # chain(check_group, run_finish_album_process.s(db_album_id))()
    search_group = group(run_free_photo_process.s(photo_id, *args, **kwargs) for photo_id in photo_ids)
    chain(search_group, run_finish_album_process.s(db_album_id))()
    return f'Processed {len(photo_ids)} photos in album'


@shared_task()
@transaction.atomic
def run_all_subscriptions(*args, **kwargs):
    # Фоновый запуск обновления информации по альбомам и запуск Платного поиска
    return run_active_subscriptions()
