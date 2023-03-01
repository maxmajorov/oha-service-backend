import hashlib

from django import forms


# noinspection SpellCheckingInspection
class PayYandexForm(forms.Form):
    # Счёт получателя
    receiver = forms.CharField(
        required=True,
        widget=forms.HiddenInput(),
    )
    targets = forms.CharField(widget=forms.HiddenInput())
    sum = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        required=True,
        widget=forms.HiddenInput(),
    )
    # noinspection SpellCheckingInspection
    formcomment = forms.CharField(widget=forms.HiddenInput())
    label = forms.CharField(widget=forms.HiddenInput())
    successURL = forms.CharField(widget=forms.HiddenInput())
    comment = forms.CharField(widget=forms.HiddenInput())
    paymentType = forms.CharField(
        widget=forms.HiddenInput(),
        initial='PC',
    )

    def __init__(self, *args, **kwargs):
        super(PayYandexForm, self).__init__(*args, **kwargs)
        # Динамическое создание полей с не типизированными Именами
        self.fields['short-dest'] = forms.CharField(widget=forms.HiddenInput())
        self.fields['quickpay-form'] = forms.CharField(
            widget=forms.HiddenInput(),
            initial='shop',
        )

# Форма для получения данных от Яндекса о платже


class NotificationForm(forms.Form):
    # Параметры уведомлений
    # https://money.yandex.ru/doc.xml?id=526991
    """
    POST [<QueryDict:
    {	u'withdraw_amount': [u'2.00'],
        u'datetime': [u'2017-05-22T05:01:26Z'],
        u'currency': [u'643'],
        u'street': [u''],
        u'unaccepted': [u'false'],
        u'notification_type': [u'p2p-incoming'],
        u'city': [u''],
        u'zip': [u''],
        u'label': [u'6abe0a5f-9658-4e17-b63a-0f0c5e3c42fa'],
        u'operation_label': [u'20b48461-0009-5000-8000-0000216eba2a'],
        u'suite': [u''],
        u'email': [u''],
        u'codepro': [u'false'],
        u'flat': [u''],
        u'firstname': [u''],
        u'lastname': [u''],
        u'phone': [u''],
        u'building': [u''],
        u'sender': [u'41001903390867'],
        u'fathersname': [u''],
        u'sha1_hash': [u'ddc30581824c80937cf3079b96375f61164a366e'],
        u'amount': [u'1.99'],
        u'operation_id': [u'1097488972730016025']
    }>]
    """
    # Для переводов из кошелька — p2p-incoming. Для переводов с произвольной карты — card-incoming
    notification_type = forms.CharField(required=True)
    # Идентификатор операции в истории счета получателя
    operation_id = forms.CharField()
    # Сумма, которая зачислена на счет получателя
    amount = forms.DecimalField(min_value=0, decimal_places=2, required=True)
    # Сумма, которая списана со счета отправителя
    withdraw_amount = forms.DecimalField(
        min_value=0, decimal_places=2, required=False,
    )
    # Код валюты — всегда 643 (рубль РФ согласно ISO 4217)
    currency = forms.CharField()
    # Дата и время совершения перевода
    datetime = forms.CharField()
    # Для переводов из кошелька — номер счета отправителя.
    # Для переводов с произвольной карты — параметр содержит пустую строку.
    # !!! нет у платежей с карточки банка
    sender = forms.CharField(required=False)
    #
    comment = forms.CharField(required=False)
    # Для переводов из кошелька — перевод защищен кодом протекции.
    # Для переводов с произвольной карты — всегда false.
    # !!! В реальных платежах, есть
    code_pro = forms.BooleanField(required=False)
    # Метка платежа. Если ее нет, параметр содержит пустую строку.
    label = forms.CharField(required=False)  # !!! В реальных платежах, есть
    # SHA-1 hash параметров уведомления
    sha1_hash = forms.CharField(required=True)
    # Перевод еще не зачислен.
    #  Получателю нужно освободить место в кошельке или использовать код протекции (если codepro=true)
    # !!! В реальных платежах, есть
    unaccepted = forms.BooleanField(required=False)
    # noinspection SpellCheckingInspection
    lastname = forms.CharField(required=False)
    # noinspection SpellCheckingInspection
    firstname = forms.CharField(required=False)
    # noinspection SpellCheckingInspection
    fathersname = forms.CharField(required=False)
    email = forms.CharField(required=False)
    phone = forms.CharField(required=False)
    city = forms.CharField(required=False)
    street = forms.CharField(required=False)
    building = forms.CharField(required=False)
    suite = forms.CharField(required=False)
    flat = forms.CharField(required=False)
    zip = forms.CharField(required=False)

    def check_hash(self, notification_secret):
        text = '{}&{}&{}&{}&{}&{}&{}&{}&{}'.format(
            self.data['notification_type'],
            self.data['operation_id'],
            self.data['amount'],
            self.data['currency'],
            self.data['datetime'],
            self.data['sender'],
            self.data['codepro'],
            notification_secret,
            self.data['label'],
        )
        # print(u'check_hash. [{}]'.format(text))
        sha_1 = hashlib.sha1()
        sha_1.update(text.encode())
        output_hash = sha_1.hexdigest()
        return output_hash == self.data['sha1_hash']
