# https://simpleisbetterthancomplex.com/tutorial/2016/07/18/how-to-create-a-custom-django-middleware.html
import logging
import os

import pygeoip
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from .utils.u_request import is_local_ip
from .utils.u_request import is_valid_ip
from .utils.u_request import RequestInfo
logger = logging.getLogger(__name__)


# Цель отметить время последнего визита пользователя
class SetLastVisitMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = User.objects.get(pk=request.user.pk)
                if hasattr(user, 'profile') and user.profile:
                    profile = user.profile
                    t_now = timezone.now()
                    if profile.last_visit:
                        diff_hours = (t_now - profile.last_visit).seconds // 3600
                        if diff_hours > settings.LAST_VISIT_ACCURACY:
                            profile.last_visit = t_now
                            profile.save()
                    else:
                        profile.last_visit = t_now
                        profile.save()
        except Exception as ex:
            # TODO Log error
            e_text = 'SetLastVisitMiddleware Exception [{}]'.format(ex)
            logger.error(
                e_text,
                exc_info=True,
                extra={'request': request, },
            )
        return response


db_loaded = False
db = None


def load_db_settings():
    geoip_database = getattr(settings, 'GEOIP_DATABASE', 'GeoLiteCity.dat')

    if not geoip_database:
        raise ImproperlyConfigured('GEOIP_DATABASE setting has not been properly defined.')
    if not os.path.exists(geoip_database):
        raise ImproperlyConfigured('GEOIP_DATABASE setting is defined, but file does not exist.')

    return geoip_database


try:
    load_db_settings()
except Exception as e:
    logger.info('load_db_settings Exception [{}]'.format(e), exc_info=True)


def load_db():
    try:
        geoip_database = load_db_settings()
        global db
        db = pygeoip.GeoIP(geoip_database, pygeoip.MEMORY_CACHE)
        global db_loaded
        db_loaded = True
    except Exception as le:
        logger.error('load_db Exception [{}]'.format(le), exc_info=True)
        return


# Цель - изменить timezone в соответствии с местонахождением пользователя (место по IP)
# https://github.com/Miserlou/django-easy-timezones
class EasyTimezoneMiddleware(MiddlewareMixin):

    def process_request(self, request):
        """
        If we can get a valid IP from the request,
        look up that address in the database to get the appropriate timezone
        and activate it.
        Else, use the default.
        """

        if not request:
            return

        if not db_loaded:
            load_db()
        if not db_loaded:
            # TODO Log error geoip database does not exist
            logger.error('geoip database does not exist', exc_info=True)
            return

        ri = RequestInfo(request)
        tz = request.session.get('service_timezone')
        client_ip = ri.get_ip_address_from_request()
        request.client_ip = client_ip

        if not tz:
            # use the default timezone (settings.TIME_ZONE) for localhost
            tz = timezone.get_default_timezone()

            ip_addrs = client_ip.split(',')
            for ip in ip_addrs:
                if is_valid_ip(ip) and not is_local_ip(ip):
                    tz = db.time_zone_by_addr(ip)

        if tz:
            timezone.activate(tz)
            request.session['service_timezone'] = str(tz)
        else:
            timezone.deactivate()

        # collect Geo info
        geo_city = request.session.get('city')
        geo_country_code = request.session.get('country_code')
        geo_latitude = request.session.get('lt')
        geo_longitude = request.session.get('lg')

        if not geo_city or not geo_country_code or not geo_latitude or not geo_longitude:
            ip_addrs = client_ip.split(',')
            for ip in ip_addrs:
                if is_valid_ip(ip) and not is_local_ip(ip):
                    tz = db.time_zone_by_addr(ip)
                    geo = db.record_by_addr(ip)
                    if geo:
                        request.session['city'] = geo['city']
                        request.session['country_code'] = geo['country_code']
                        request.session['lt'] = geo['latitude']
                        request.session['lg'] = geo['longitude']

                        geo_city = geo['city']
                        geo_country_code = geo['country_code']
                        geo_latitude = geo['latitude']
                        geo_longitude = geo['longitude']
                    break
        request.geo_city = geo_city
        request.geo_country_code = geo_country_code
        request.geo_latitude = geo_latitude
        request.geo_longitude = geo_longitude
