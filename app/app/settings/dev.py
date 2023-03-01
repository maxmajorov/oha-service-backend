import logging

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *

sentry_sdk.init(
    dsn='https://69e06777f3dd434fad99747b28f2d207@log.balanceit.ru/7',
    integrations=[DjangoIntegration()],
    environment=ENVIRONMENT,
    release=VERSION,
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

logger = logging.getLogger(__name__)

print(f'Using DEV local settings file. Version: {VERSION}')
logger.info('Using dev local settings file')

SITE_DOMAIN = 'https://localhost:8000'
