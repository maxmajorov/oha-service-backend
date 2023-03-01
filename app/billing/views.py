import logging

from billing.models import payment_callback
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
# Django

logger = logging.getLogger(__name__)


@sensitive_variables()
@csrf_exempt
def yandex_money_callback(request):
    """
    Цель: получение, проверка и подтверждение оплаты от Яндекс.Деньги
    https://tech.yandex.ru/money/doc/dg/reference/notification-p2p-incoming-docpage/

    :param request:
    :return:
    """
    if request.method != 'POST':
        logger.error(
            'notify request.method - GET (POST expected)',
            extra={'request': request, },
        )
        return HttpResponse(status=403)
    else:
        logger.info('notify Yandex Money', extra={'request': request, }, )
    status = payment_callback(request)
    return HttpResponse(status=status)
