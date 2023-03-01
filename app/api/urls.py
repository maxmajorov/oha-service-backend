from django.conf import settings
from django.urls import include
from django.urls import path
from django.urls import re_path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from django.contrib import admin

from .views import AlbumPhotosView
from .views import AlbumProcessingView
from .views import AlbumResultView
from .views import InvoiceStatusView
from .views import InvoiceView
from .views import PhotoStatsView
from .views import SubscriptionExpandView
from .views import TariffView
from .views import UserInfoView

schema_view = get_schema_view(
    openapi.Info(
        title='Project API',
        default_version='v1',
    ),
    url=f'https://{settings.DEFAULT_DOMAIN}/api/v1/',
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Free
    path('album_results/', AlbumResultView.as_view(), name='album_results'),
    path('album_processing/', AlbumProcessingView.as_view(), name='album_processing'),
    # Accounts
    path('accounts/', include('allauth.urls')),
    # Full
    path('album/photos/', AlbumPhotosView.as_view(), name='album_photos'),
    path('album/photo_stats/', PhotoStatsView.as_view(), name='photo_stats'),
    path('user/info/', UserInfoView.as_view(), name='user_info'),
    # billing
    path('billing/tariffs/', TariffView.as_view(), name='tariffs'),
    path('billing/create_invoice/', InvoiceView.as_view(), name='create_invoice_old'),
    path('billing/invoice/', InvoiceStatusView.as_view(), name='invoice'),
    path('billing/invoice/create', InvoiceView.as_view(), name='create_invoice'),
    path('billing/subscription/expand', SubscriptionExpandView.as_view(), name='subscription_expand'),
    # docs
    re_path('^docs/swagger(?P<format>.json|.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('docs/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('docs/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
