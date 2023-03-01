from django.urls import path

from . import views

app_name = 'billing'
urlpatterns = [
    path('ym/notify/', views.yandex_money_callback, name='ym_notify'),
]
