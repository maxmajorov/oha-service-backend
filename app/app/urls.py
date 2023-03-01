"""app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path

ADMIN_URL = os.environ.get('ADMIN_URL', 'tjo1r-3hye0sbtl')

urlpatterns = [
    path(f'back-manager/admin-{ADMIN_URL}/', admin.site.urls),
    path(f'back-manager/tools-{ADMIN_URL}/', include('tools.urls')),
    path('api/v1/', include('api.urls')),
    path('api/accounts/', include('allauth.urls')),
    path('billing/', include('billing.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
