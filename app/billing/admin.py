from core.models import start_subscription_search
from django.contrib import admin

from .models import Confirmation
from .models import Invoice
from .models import PromoCode
from .models import Subscription
from .models import SubscriptionHistory


def accept_transaction(modeladmin, request, queryset):
    for item in queryset:
        item.accept_transaction()


def paid_subscription_search(modeladmin, request, queryset):
    for item in queryset:
        start_subscription_search(item.id)


accept_transaction.short_description = 'Принять счёт'  # type: ignore
paid_subscription_search.short_description = 'Выполнить платный поиск'  # type: ignore


class InvoiceAdmin(admin.ModelAdmin):
    search_fields = ('ext_id',)
    list_filter = ('subscription',)
    list_display = ('user', 'subscription', 'timestamp', 'ext_id', 'status')
    actions = [accept_transaction, ]


class SubscriptionAdmin(admin.ModelAdmin):
    search_fields = ('name', 'sys_code',)
    list_filter = ('active', 'recurrence_unit',)
    list_display = ('id', 'name', 'price', 'parameter', 'sys_code', 'active', 'available_from', )


class SubscriptionHistoryAdmin(admin.ModelAdmin):
    search_fields = ('user', 'subscription',)
    list_filter = ('active', 'subscription',)
    list_display = ('id', 'user', 'subscription', 'invoice', 'active', 'activate_date', 'expires_date')
    actions = [paid_subscription_search, ]


class ConfirmationAdmin(admin.ModelAdmin):
    search_fields = ('label', 'invoice',)
    list_filter = ('notification_type', 'unaccepted', 'code_pro')
    list_display = ('user', 'invoice', 'index', 'withdraw_amount', 'amount', 'fact_payment_date', 'notification_type', 'label')


class PromoCodeAdmin(admin.ModelAdmin):
    search_fields = ('gr_code', 'addressee')
    list_filter = ('subscription', )
    list_display = ('subscription', 'code', 'amount', 'discount', 'available_from', 'available_until', 'addressee')


# Register your models here.
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Confirmation, ConfirmationAdmin)
admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(SubscriptionHistory, SubscriptionHistoryAdmin)
admin.site.register(PromoCode, PromoCodeAdmin)
