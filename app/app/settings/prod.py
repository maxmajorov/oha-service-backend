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

logger = logging.getLogger(__name__)

print(f'Using PRODUCTION settings file. Version: {VERSION}')
logger.info('Using PRODUCTION local settings file')

DEBUG = False

SITE_DOMAIN = 'https://ohaoha.ru'
