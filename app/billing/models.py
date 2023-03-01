import datetime
import logging
import uuid

import celery
import dateutil.parser
from billing.forms import NotificationForm
from core.utils.u_chart import add_months
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import deletion
from django.utils import timezone
from django.utils.translation import gettext_lazy as _ #ugettext???

try:
    from django.db.models import JSONField
    postgres_only = False
except ImportError:
    from django.contrib.postgres.fields import JSONField
    postgres_only = True

logger = logging.getLogger(__name__)

_TIME_UNIT_CHOICES = (
    (None, _('No recurrence')),
    ('0', _('No trial')),  # unused
    ('D', _('Day')),  # unused
    ('W', _('Week')),  # unused
    ('M', _('Month')),
    ('Y', _('Year')),  # unused
)

_HIST_ACT = 'active'
_HIST_DEF = 'default_active'
_HIST_EXP = 'expired'
_HIST_WTN = 'waiting'
_HIST_STATUSES = (
    (_HIST_ACT, _('Active')),
    (_HIST_DEF, _('Default active')),
    (_HIST_EXP, _('Expired')),
    (_HIST_WTN, _('Waiting')),
)


# Invoice - Счета для оплаты

class Invoice(models.Model):
    ST_NEW = 'N'
    ST_UND = 'U'
    ST_WAI = 'W'
    ST_PRT = 'P'
    ST_WDW = 'E'
    ST_VRF = 'V'
    STATUSES = (
        (ST_NEW, 'Выставлен'),
        (ST_UND, 'Отменен'),
        (ST_WAI, 'Подтвержден'),  # Ожидает зачисления, счет переполнен!
        (ST_PRT, 'Не принят (код протекции)'),
        (ST_WDW, 'Не принят (не верная сумма)'),
        (ST_VRF, 'Оплачен'),
    )
    id = models.BigAutoField(primary_key=True)
    create_date = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(on_delete=deletion.SET_NULL, related_name='invoices', to=User, null=True, blank=True, )
    # ИД Счёта/оплаты для идентификации во внешних системах
    ext_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Элементы подписки
    items = JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    subscription = models.ForeignKey('Subscription', on_delete=deletion.SET_NULL, null=True, blank=True, editable=False)
    # Статус
    status = models.CharField(
        max_length=1,
        choices=STATUSES,
        default=ST_NEW,
    )
    sid = models.CharField(
        max_length=100,
        editable=False,
        null=True,
        blank=True,
    )
    event = models.CharField(max_length=100, editable=False, )
    check_amount = models.BooleanField(default=True)
    amount = models.DecimalField(
        max_digits=64,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
    )
    comment = models.TextField(blank=True, default='', )

    def get_status(self):
        return dict(Invoice.STATUSES)[self.status]

    def is_approved(self):
        return self.status == self.ST_VRF

    def accept_transaction(self):
        Confirmation.objects.create(
            invoice=self,
            index=1,
            withdraw_amount=0,
            amount=0,
            fact_payment_date=datetime.datetime.now(),
            notification_type='hand-work',
            label='-',
            unaccepted=False,
            code_pro=False,
            sender='',
            operation_id=None,
            currency='643',
            user=self.user,
        )
        self.status = Invoice.ST_WAI
        self.save()

    def __str__(self):
        return '{}: {} - {} ({})'.format(
            self.timestamp.replace(microsecond=0), self.user, self.subscription,
            self.amount,
        )


# Confirmation - данные о подтверждении оплаты

class Confirmation(models.Model):
    id = models.BigAutoField(primary_key=True)
    create_date = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(
        on_delete=deletion.SET_NULL, related_name='confirmations', to=User, null=True, blank=True,
    )
    # Счёт
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='confirmations')
    # Порядковый номер подтверждения оплаты
    index = models.DecimalField(
        max_digits=2,
        decimal_places=0,
        null=True,
        blank=True,
        editable=False,
    )
    # Сумма, которая списана со счета отправителя
    withdraw_amount = models.DecimalField(
        max_digits=64,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
    )
    # Сумма, которая зачислена на счет получателя
    amount = models.DecimalField(
        max_digits=64,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
    )
    # Фактическая дата подтверждения оплаты
    fact_payment_date = models.DateTimeField(
        verbose_name='Дата подтверждения оплаты',
        blank=True,
        null=True, )
    # Тип оплаты (p2p-incoming - из кошелька, card-incoming - с произвольной карты)
    notification_type = models.CharField(
        max_length=100,
        null=True,
        blank=True, )
    # Метка счета
    label = models.CharField(
        max_length=100,
        null=True,
        blank=True, )
    # Перевод еще не зачислен. Получателю нужно освободить место в кошельке или использовать код протекции
    unaccepted = models.BooleanField(
        default=False,
        null=True,
        blank=True, )
    # Перевод еще не зачислен. Получателю нужно освободить место в кошельке или использовать код протекции
    code_pro = models.BooleanField(
        default=False,
        null=True,
        blank=True, )
    # номер счета отправителя, для кошелька или пусто для карты
    sender = models.CharField(
        max_length=100,
        null=True,
        blank=True, )
    # Идентификатор операции в истории счета получателя
    operation_id = models.CharField(
        max_length=100,
        null=True,
        blank=True, )
    # Код валюты — всегда 643
    currency = models.CharField(
        max_length=100,
        null=True,
        blank=True, )
    # Сообщение от пользователя
    comment = models.CharField(
        max_length=1000,
        default='',
        null=True,
        blank=True, )

    def __str__(self):
        return '{}: {} - {} ({})'.format(self.invoice, self.index, self.amount, self.fact_payment_date)


# Subscription - Подписки / Тарифы

class Subscription(models.Model):
    id = models.BigAutoField(primary_key=True)
    # Название
    name = models.CharField(max_length=100, null=False)
    # Уникальный код подписки (для отличия версий одной подписки)
    sys_code = models.CharField(
        max_length=20,
        unique=True,
        default='default_code',
        null=False,
    )
    # Описание
    description = models.TextField(blank=True)
    # Базовая цена, к которой будут добавлены стоимости доп. Условий
    price = models.DecimalField(max_digits=64, decimal_places=2)
    # Базовый параметр
    parameter = models.PositiveIntegerField(null=True, blank=True)
    # Бесплатный (триальный) период
    trial_period = models.PositiveIntegerField(null=True, blank=True)
    trial_unit = models.CharField(max_length=1, null=True, choices=_TIME_UNIT_CHOICES, default='M')
    # Период - количество
    recurrence_period = models.PositiveIntegerField(null=True, blank=True)
    # Период - единицы
    recurrence_unit = models.CharField(max_length=1, null=True, choices=_TIME_UNIT_CHOICES, default='M')
    # Дата ДО которой доступна подписка
    available_until = models.DateField(null=True, default=datetime.date.max)
    # Дата С которой доступна подписка
    available_from = models.DateField(null=True, default=datetime.date.today)
    # Признак доступности для оплаты
    active = models.BooleanField(default=True)
    # Используемая по умолчанию
    default = models.BooleanField(default=False)

    def __str__(self):
        return '{}: {}/ ({})'.format(self.name, self.sys_code, self.price)


# SubscriptionHistory - История конкретных подписок Пользователя

class SubscriptionHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    create_date = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(on_delete=deletion.SET_NULL, related_name='subs_history', to=User, null=True, blank=True, )
    subscription = models.ForeignKey(
        'Subscription',
        on_delete=models.SET_NULL,
        default=None,
        blank=True,
        null=True,
        related_name='subs_history',
    )
    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.SET_NULL,
        default=None,
        blank=True,
        null=True,
        related_name='subs_history',
    )
    # Элементы подписки
    items = JSONField(default=dict)
    # Дата окончания действия (заполняется в момент начала использования)
    expires_date = models.DateField(null=True, default=None, blank=True, )
    # Дата начала действия (заполняется в момент начала использования)
    activate_date = models.DateField(null=True, default=None, blank=True, )
    # Признак использования (После окончания срока действия остаётся установлен)
    active = models.BooleanField(default=True)
    # Признак отмены
    cancelled = models.BooleanField(default=False)
    # Количество оплаченных периодов
    period_count = models.PositiveIntegerField(null=True, blank=True, default=1, )
    # Единицы периодов (оплаченных)
    period_unit = models.CharField(max_length=1, null=True, choices=_TIME_UNIT_CHOICES, default='M', )
    # Фиксация параметра тарифа на момент оплаты
    fix_parameter = models.PositiveIntegerField(null=True, blank=True)
    # Число выполненных поисков в подписке (используется для лимита)
    search_count = models.IntegerField(default=0)

    def __str__(self):
        return '{}: {} - {} ({})'.format(self.user, self.subscription, self.activate_date, self.active)

    def is_album_connected(self, vk_album_id):
        for item in self.items:
            if str(item) == str(vk_album_id):
                return True
        return False


# PromoCode - Промо код на доступ к скидке или спец. цене

class PromoCode(models.Model):
    id = models.BigAutoField(primary_key=True)
    subscription = models.ForeignKey(
        'Subscription',
        null=True,
        blank=True,
        editable=False,
        on_delete=deletion.CASCADE,
    )
    # Новая цена
    amount = models.DecimalField(
        max_digits=64,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # Скидка (проценты от 0 до 100)
    discount = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # Получатель промо кода (email)
    addressee = models.EmailField(
        'addressee',
        null=True,
        blank=True,
    )
    # Промокод
    code = models.CharField(
        max_length=30,
        null=False,
        blank=False,
    )
    # Дата С которой доступен Промокод
    available_from = models.DateTimeField(
        null=False,
        blank=False,
        default=datetime.datetime.now,
    )
    # Дата ДО которой доступен Промокод
    available_until = models.DateTimeField(
        null=False,
        blank=False,
        default=datetime.datetime.max,
    )

    def __str__(self):
        return '{}: {} ({})'.format(self.subscription, self.code, self.available_until)


def get_expires_date(dt):
    min_date = add_months(dt, 1)
    if min_date.day < dt.day:
        # При оплате 31 числа и последнем 30 числе в следующем месяце, переводим на учёт с 1 числа
        return min_date + datetime.timedelta(days=1)
    return min_date


def process_renewal_subscription(invoice: Invoice):
    """
    Обработка пролученного подтверждения об оплате Счета

    :param invoice: Счет (Invoice)
    :return:
    """
    # Create SubscriptionHistory
    sh, created = SubscriptionHistory.objects.get_or_create(
        user=invoice.user,
        subscription=invoice.subscription,
        invoice=invoice,
    )
    if created:
        sh.items = invoice.items
        sh.active = True
        sh.activate_date = timezone.now()
        sh.expires_date = get_expires_date(sh.activate_date)
        sh.fix_parameter = invoice.subscription.parameter
        sh.save()
    else:
        logger.error(
            f'process_renewal_subscription SubscriptionHistory has already been created',
            extra={
                'invoice': invoice.id,
                'sh': sh.id,
            },
        )
    celery.current_app.send_task(
        'core.tasks.run_subscription_process', (sh.id,), queue='high_priority', routing_key='high_priority',
    )
    return


def _payment_processing(payment_data):
    label = payment_data['label']
    if label and len(label) > 5:
        invoice = Invoice.objects.filter(ext_id=label)
        if invoice and invoice.count() == 1:
            # print('Transaction found!')
            invoice = Invoice.objects.get(ext_id=label)
            # Data to save
            fact_payment_date = None
            if 'datetime' in payment_data and len(payment_data['datetime']) > 5:
                fact_payment_date = dateutil.parser.parse(payment_data['datetime'], )
            comment = ''
            if 'comment' in payment_data and payment_data['comment']:
                comment = payment_data['comment']
            unaccepted = None
            if 'unaccepted' in payment_data and payment_data['unaccepted']:
                unaccepted = payment_data['unaccepted'] in ['true', '1', 't', 'y', 'True']
            code_pro = None
            if 'codepro' in payment_data and payment_data['code_pro']:
                code_pro = payment_data['code_pro'] in ['true', '1', 't', 'y', 'True']
            amount = None
            if 'amount' in payment_data and payment_data['amount']:
                amount = float(payment_data['amount'])
            withdraw_amount = None
            if 'withdraw_amount' in payment_data and payment_data['withdraw_amount']:
                withdraw_amount = float(payment_data['withdraw_amount'])

            conf_count = Confirmation.objects.filter(invoice_id=invoice.id).count()
            if conf_count > 3:
                logger.error('notify Confirmation count > 3!', extra={'payment_data': payment_data, })

            Confirmation.objects.create(
                invoice=invoice,
                index=conf_count + 1,
                withdraw_amount=withdraw_amount,
                amount=amount,
                fact_payment_date=fact_payment_date,
                notification_type=payment_data['notification_type'],
                label=payment_data['label'],
                unaccepted=unaccepted,
                code_pro=code_pro,
                sender=payment_data['sender'],
                operation_id=payment_data['operation_id'],
                currency=payment_data['currency'],
                user=invoice.user,
                comment=comment,
            )
            # SECURITY: Проверка withdraw_amount и суммы счета
            if invoice.check_amount and invoice.amount != withdraw_amount:
                try:
                    invoice.status = Invoice.ST_WDW
                    invoice.save()
                except Exception as e:
                    logger.error(
                        f'Billing check withdraw amount exception: {e}',
                        exc_info=True,
                        extra={'payment_data': payment_data, },
                    )
            # Change transaction status
            elif code_pro:
                invoice.status = Invoice.ST_PRT
                invoice.save()
            elif not unaccepted:
                invoice.status = Invoice.ST_VRF
                invoice.save()
            else:
                invoice.status = Invoice.ST_WAI
                invoice.save()
            # process update subscription
            process_renewal_subscription(invoice)
            return 200
        else:
            logger.error('yandex_money_callback Transaction not found!', extra={'payment_data': payment_data, })
    else:
        logger.error('yandex_money_callback label not found!', extra={'payment_data': payment_data, 'label': label}, )
    return 500


def payment_callback(request):
    if_debug = settings.DEBUG
    try:
        form = NotificationForm(request.POST)
        if form.is_valid():
            verify = form.check_hash(settings.YM_SECRET)
            if if_debug:
                verify = form.check_hash(settings.YM_SECRET)
            if verify:
                # Сообщение верное
                return _payment_processing(form.cleaned_data)
            else:
                logger.error(
                    f'yandex_money_callback check sum verification error (debug: {if_debug})',
                    extra={'request': request, },
                )
        else:
            str_form = str(list(form.errors.items()))
            logger.error(
                'yandex_money_callback NotificationForm invalid',
                extra={'request': request, 'form': form, 'form_errors': str_form},
            )
    except Exception as e:
        e_text = 'notify {}: [{}]'.format(type(e), e)
        logger.error(
            e_text,
            exc_info=True,
            extra={'request': request, },
        )
    return 500


def init_subscription():
    subs_count = Subscription.objects.count()
    if subs_count == 0:
        # 100
        Subscription.objects.create(
            name='Старт',
            sys_code='04012020_100',
            description='до 100 фотографий',
            price=1500,
            parameter=100,
            recurrence_period=1,
            recurrence_unit='M',
            active=True,
        )
        # 500
        Subscription.objects.create(
            name='Медиум',
            sys_code='04012020_500',
            description='до 100 фотографий',
            price=6000,
            parameter=500,
            recurrence_period=1,
            recurrence_unit='M',
            active=True,
        )
        # 1000
        Subscription.objects.create(
            name='Бизнес',
            sys_code='04012020_1000',
            description='до 100 фотографий',
            price=10000,
            parameter=1000,
            recurrence_period=1,
            recurrence_unit='M',
            active=True,
        )
