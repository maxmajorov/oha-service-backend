import ipaddress
import json
import os
import random
import string

import idna
import requests
import tldextract
from django.conf import settings
from django.core.validators import URLValidator
from user_agents import parse as ua_parse

from .u_exiftool import ExifTool

PRIVATE_IPS_PREFIX = ('10.', '172.', '192.', '127.')


def random_string(string_length=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(string_length))


def get_exif_from_url(url):
    metadata = None
    path = download_file(url)
    with ExifTool() as et:
        metadata = et.get_metadata(path)
    os.remove(path)
    return metadata


def download_file(url):
    r = requests.get(url)
    file_name = url.split('/')[-1]
    path = f'{settings.TEMP_DIR}/{file_name}'
    print(f'download path: {path}')
    suffix = ''
    while os.path.exists(f'{path}{suffix}'):
        suffix = random_string(5)
    with open(path, 'wb') as f:
        f.write(r.content)
    return path


def is_valid_ip(ip_address):
    """ Check Validity of an IP address """
    try:
        ipaddress.ip_address('' + ip_address)
        return True
    except ValueError as e:  # noqa: F841
        return False


def is_local_ip(ip_address):
    """ Check if IP is local """
    try:
        ip = ipaddress.ip_address('' + ip_address)
        return ip.is_loopback
    except ValueError as e:  # noqa: F841
        return None


def get_site(url):
    ext = tldextract.extract(url)
    site = '.'.join([ext.subdomain, ext.domain, ext.suffix]).lstrip('.').rstrip('.')
    if 'xn--' in url:
        return idna.decode(site)
    return site


def is_valid_url(url):
    try:
        validate = URLValidator(schemes=['http', 'https'])
        validate(url)
    except:  # noqa: E722
        return False
    return True


def is_support_sites(url):
    # Instagram post https://www.instagram.com/p/B2cA9WMB3qC/
    # Instagram profile https://www.instagram.com/oleg_chegodaev/
    # VK album https://vk.com/album158184342_242810703
    # VK album list https://vk.com/albums158184342
    # VK photo https://vk.com/photo158184342_379329760
    site = get_site(url)
    if site.lower() == 'vk.com':
        return True
    return False


def url_ok(url):
    try:
        r = requests.get(url, timeout=(2, 2))
        # if r.history and len(r.history) > 1:
        #    # redirected!
        #    return False
    except:  # noqa: E722
        return False
    return r.status_code == 200 or r.status_code == 418


def get_short_domain(domain: str):
    domain = domain.lower()
    if domain.startswith('www.'):
        return domain.lstrip('www.')
    return domain


class RequestInfo:

    def __init__(self, request):
        self.request = request
        self.is_auth = False
        self.cookies = self.get_utm_cookies()
        self.utm_source = self.get_cookie('utm_source')
        self.utm_medium = self.get_cookie('utm_medium')
        self.utm_campaign = self.get_cookie('utm_campaign')
        self.utm_term = self.get_cookie('utm_term')
        self.utm_content = self.get_cookie('utm_content')
        self.utm_referrer = self.get_cookie('utm_referrer')
        self.ip_address = self.get_ip_address_from_request()
        self.ua_string = self.request.META.get('HTTP_USER_AGENT', '')
        self.user_agent = ua_parse(self.ua_string)
        self.user_session_key = self.get_unique_user_key()

    def get_cookie_json_by_name(self, name):
        json_obj = None
        if name not in self.request.COOKIES:
            return json_obj
        val = self.request.COOKIES.get(name).replace('%2C', ',').replace('%22', '\"')
        # noinspection PyBroadException
        try:
            if val:
                json_obj = json.loads(val)
        except:  # noqa: E722
            return json_obj
        return json_obj

    def get_utm_cookies(self):
        mapping = {
            'st_src': 'utm_source',
            'st_mdm': 'utm_medium',
            'st_cmp': 'utm_campaign',
            'st_trm': 'utm_term',
            'st_cnt': 'utm_content',
            'st_rfr': 'utm_referrer',
        }
        result = {}
        for key, value in mapping.items():
            cookie = self.get_cookie_json_by_name(key)
            if cookie:
                result[value] = cookie
        return result

    def get_cookie(self, key):
        if key in self.cookies and 'val1' in self.cookies[key]:
            return self.cookies['utm_source']['val1'][:100]
        return None

    def get_ip_address_from_request(self):
        """ Makes the best attempt to get the client's real IP or return the loopback """

        ip_address = ''
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR', '')
        if x_forwarded_for and ',' not in x_forwarded_for:
            if not x_forwarded_for.startswith(PRIVATE_IPS_PREFIX) and is_valid_ip(x_forwarded_for):
                ip_address = x_forwarded_for.strip()
        else:
            ips = [ip.strip() for ip in x_forwarded_for.split(',')]
            for ip in ips:
                if ip.startswith(PRIVATE_IPS_PREFIX) or not is_valid_ip(ip):
                    continue
                else:
                    ip_address = ip
                    break
        if not ip_address:
            x_real_ip = self.request.META.get('HTTP_X_REAL_IP', '')
            if x_real_ip and not x_real_ip.startswith(PRIVATE_IPS_PREFIX) and is_valid_ip(x_real_ip):
                ip_address = x_real_ip.strip()
        if not ip_address:
            remote_addr = self.request.META.get('REMOTE_ADDR', '')
            if remote_addr and not remote_addr.startswith(PRIVATE_IPS_PREFIX) and is_valid_ip(remote_addr):
                ip_address = remote_addr.strip()
        if not ip_address:
            ip_address = '127.0.0.1'
        return ip_address

    def get_unique_user_key(self):
        if self.request.user.is_authenticated:
            self.is_auth = True
        else:
            self.is_auth = False
        return self.request.session.session_key
