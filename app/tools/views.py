import logging

from allauth.socialaccount.models import SocialAccount
from billing.models import Confirmation
from billing.models import Invoice
from billing.models import SubscriptionHistory
from core.models import Album
from core.models import EngineCounter
from core.models import Photo
from core.models import SearchResult
from core.utils.u_tineye import get_tineye_remaining_searches
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.template import loader
from django.urls import reverse
from django.utils import dateformat
from django.utils import timezone

from .models import ChartTimeLine
from .models import get_default_group_count
from .models import get_valid_group

logger = logging.getLogger(__name__)


def stats(request):
    if not request.user.is_superuser:
        if hasattr(request.user, 'profile'):
            if not request.user.profile.founders_access:
                logger.warning(f'stats access: {request.user}')
                return HttpResponseForbidden()
        else:
            logger.warning(f'stats access: {request.user}')
            return HttpResponseForbidden()
    template = loader.get_template('tools/dashboard.html')
    context = {
        'menu': 'stats',
    }
    labels = []
    data = []
    context['labels'] = labels
    context['data'] = data
    context['version'] = settings.VERSION
    context['today'] = dateformat.format(timezone.now(), 'l, d E Y')
    context['group'] = request.GET.get('group', 'day')
    # Indicators
    indicators = []
    # Бесплатные запросы (без регистраций)
    free_search = EngineCounter.objects.filter(
        is_free=True, album__isnull=False,
    ).distinct(
        'album_id', 'search_date',
    ).values(
        'album_id', 'search_date', 'search_count',
    ).count()
    indicators.append({
        'color': 'warning',
        'text': 'Промо без регистраций',
        'value': f'{free_search}',
    })
    # Число регистраций
    indicators.append({
        'color': 'primary',
        'text': 'Число регистраций',
        'value': User.objects.count(),
    })
    # Число выставленных счетов
    inv_count = Invoice.objects.count()
    indicators.append({
        'color': 'secondary',
        'text': 'Счетов выставлено',
        'value': f'{inv_count}',
    })
    # Число подписок
    subs_count = SubscriptionHistory.objects.count()
    indicators.append({
        'color': 'secondary',
        'text': 'Подписки',
        'value': f'{subs_count}',
    })
    # Доход
    revenue = Confirmation.objects.aggregate(sum=Sum('amount'))['sum']
    if not revenue:
        revenue = 0
    indicators.append({
        'color': 'success',
        'text': 'Доход',
        'value': f'{revenue} ₽',
    })
    # Не заврешенные альбомы
    process = Album.objects.filter(status=Album.PS_WRK).count()
    if not process:
        process = 0
    indicators.append({
        'color': 'danger',
        'text': 'Альбомы в процессе',
        'value': f'{process}',
    })
    context['indicators'] = indicators
    return HttpResponse(template.render(context, request))


def stats_search(request):
    if not request.user.is_superuser:
        if hasattr(request.user, 'profile'):
            if not request.user.profile.founders_access:
                logger.warning(f'stats access: {request.user}')
                return HttpResponseForbidden()
        else:
            logger.warning(f'stats access: {request.user}')
            return HttpResponseForbidden()
    template = loader.get_template('tools/search_stats.html')
    context = {
        'menu': 'stats_search',
    }
    labels = []
    data = []
    context['labels'] = labels
    context['data'] = data
    context['version'] = settings.VERSION
    context['today'] = dateformat.format(timezone.now(), 'l, d E Y')
    context['group'] = request.GET.get('group', 'day')
    # Indicators
    indicators = []
    # Фото отслеживается
    indicators.append({
        'color': 'primary',
        'text': 'Фото отслеживается',
        'value': Photo.objects.filter(search_allowed=True).count(),
    })
    # # Альбомов отслеживается
    # indicators.append({
    #     'color': 'success',
    #     'text': 'Альбомов всего',
    #     'value': Album.objects.count(),
    # })
    # Остаток на TinEye
    indicators.append({
        'color': 'success',
        'text': 'Остаток на TinEye',
        'value': get_tineye_remaining_searches(),
    })
    # Всего результатов
    indicators.append({
        'color': 'warning',
        'text': 'Всего результатов',
        'value': SearchResult.objects.count(),
    })
    # Проверенных результатов
    indicators.append({
        'color': 'secondary',
        'text': 'Проверенных результатов',
        'value': SearchResult.objects.filter(found_image=True).count(),
    })
    context['indicators'] = indicators
    return HttpResponse(template.render(context, request))


def ajax_chart_data(request, chart_id=None, group='day'):
    group = get_valid_group(group)
    group_count = get_default_group_count(group)
    data = {}
    if not chart_id or chart_id == 1:
        chart = ChartTimeLine(group=group, group_count=group_count)
        chart.append_by_queryset(
            queryset=EngineCounter.objects.all(),
            time_field='search_date',
            label='Всего запросов',
        )
        data = chart.get_chart_data()
    elif chart_id == 2:
        chart = ChartTimeLine(group=group, group_count=group_count)
        chart.append_by_queryset(
            queryset=SocialAccount.objects.all(),
            time_field='user__profile__join_date',
            label='Регистрации',
        )
        data = chart.get_chart_data()
    elif chart_id == 3:
        chart = ChartTimeLine(group=group, group_count=group_count, title='')
        chart.append_by_queryset(
            queryset=EngineCounter.objects.all(),
            time_field='search_date',
            label='Число запросов по поисковым системам',
            split_field='name',
            sum_field='search_count',
        )
        # chart.append_by_sql(
        #     sql="SELECT to_char(date_trunc('day', p.join_date), 'DD.MM.YY') AS label, "
        #         "COUNT(sa.id) AS value "
        #         "FROM socialaccount_socialaccount as sa, core_userprofile as p "
        #         "WHERE sa.user_id = p.user_id AND p.join_date > %s "
        #         "GROUP BY to_char(date_trunc('day', p.join_date), 'DD.MM.YY') ",
        #     label='Регистраций',
        # )
        data = chart.get_chart_data()
    return JsonResponse(data)


def train(request, result_id=None, back_id=None):
    template = loader.get_template('tools/superviser.html')
    context = {}
    q_base = SearchResult.objects.filter(found_image=True, similar_data__BlockMeanHash__gte=0)
    q_sr = q_base.filter(verified_skip=False, verified_similarity=None)
    context['count'] = q_sr.count()
    context['all_count'] = SearchResult.objects.count()
    context['ok_count'] = SearchResult.objects.filter(found_image=True, verified_skip=False, verified_similarity=True).count()
    context['err_count'] = SearchResult.objects.filter(found_image=True, verified_skip=False, verified_similarity=False).count()
    context['skip_count'] = SearchResult.objects.filter(found_image=True, verified_skip=True).count()
    context['nf_count'] = SearchResult.objects.filter(found_image=False).count()
    if result_id:
        sr: SearchResult
        sr = SearchResult.objects.get(id=result_id)
        context['search'] = sr
        context['photo'] = sr.photo
        context['album'] = sr.photo.album
    elif q_sr.count() > 0:
        sr: SearchResult
        sr = q_sr.first()
        context['search'] = sr
        context['photo'] = sr.photo
        context['album'] = sr.photo.album
    if back_id:
        context['back_url'] = reverse('train_set', kwargs={'result_id': back_id})
    context['post_url'] = reverse('train_callback')
    return HttpResponse(template.render(context, request))


def train_callback(request):
    if request.method == 'POST':
        if 'result_id' not in request.POST:
            HttpResponseRedirect(str(reverse('train')))
        if 'set-skip' not in request.POST and 'set-error' not in request.POST and 'set-ok' not in request.POST:
            HttpResponseRedirect(str(reverse('train')))
        result_id = request.POST['result_id']
        if not result_id:
            return HttpResponseRedirect(str(reverse('train')))
        sr: SearchResult
        sr = SearchResult.objects.get(id=result_id)
        if 'set-skip' in request.POST:
            sr.verified_skip = True
        elif 'set-error' in request.POST:
            sr.verified_skip = False
            sr.verified_similarity = False
        elif 'set-ok' in request.POST:
            sr.verified_skip = False
            sr.verified_similarity = True
        sr.verified_date = timezone.now()
        sr.save()
        return HttpResponseRedirect(str(reverse('train_back', kwargs={'back_id': result_id})))
    return HttpResponseRedirect(str(reverse('train')))
