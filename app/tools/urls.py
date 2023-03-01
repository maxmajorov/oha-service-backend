from django.urls import path

from .views import ajax_chart_data
from .views import stats
from .views import stats_search
from .views import train
from .views import train_callback

urlpatterns = [
    # train
    path('train/', train, name='train'),
    path('train/<int:result_id>/', train, name='train_set'),
    path('train/back-<int:back_id>/', train, name='train_back'),
    path('train/callback', train_callback, name='train_callback'),
    # stats
    path('stats/', stats, name='stats'),
    path('stats/search', stats_search, name='stats_search'),
    path('stats/<int:chart_id>/<str:group>/', ajax_chart_data, name='ajax_chart_data'),
]
