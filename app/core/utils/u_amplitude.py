import json
import logging
import time

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
from requests.exceptions import Timeout

from .u_request import RequestInfo

logger = logging.getLogger(__name__)

# Documentation of AmplitudeHTTP API:
#   https://amplitude.zendesk.com/hc/en-us/articles/204771828
#
# Convert Curl queries - such as below to - python:
#   https://curl.trillworks.com/
#
# Example HTTP Curl Query for Amplitude:
#   curl --data 'api_key=SOMEIDOFAKIND'
#        --data 'event=[{
#           "user_id":"john_doe@gmail.com",
#           "event_type":"watch_tutorial",
#           "user_properties":{"Cohort":"Test A"},
#           "country":"United States",
#           "ip":"127.0.0.1",
#           "time":1396381378123}]'
#        https://api.amplitude.com/httpapi


class AmplitudeLogger:

    def __init__(self, api_key, api_uri='https://api.amplitude.com/httpapi'):
        self.api_key = api_key
        self.api_uri = api_uri
        self.is_logging = False  # TODO: Add cred and enable
        self.amplitude_adapter = HTTPAdapter(max_retries=2)
        self.session = requests.Session()
        self.session.mount(api_uri, self.amplitude_adapter)

    def turn_on_logging(self):
        self.is_logging = True

    def turn_off_logging(self):
        self.is_logging = False

    @staticmethod
    def _is_none_or_not_str(value):
        if value is None or type(value) is not str:
            return True

    #  def create_event(self, **kwargs):
    def create_event(self, request, event_type, event_properties):
        event = {}
        request_info = RequestInfo(request)

        user_id = request_info.user_session_key

        if self._is_none_or_not_str(user_id):
            return None

        event['user_id'] = user_id

        if self._is_none_or_not_str(event_type):
            return None

        event['event_type'] = event_type

        # integer epoch time in milliseconds
        event['time'] = int(time.time() * 1000)

        event['app_version'] = settings.VERSION
        event['platform'] = 'Web'
        event['os_name'] = request_info.user_agent.browser.family
        event['os_version'] = request_info.user_agent.browser.version_string
        event['device_brand'] = request_info.user_agent.device.brand
        event['device_manufacturer'] = request_info.user_agent.device.family
        event['device_model'] = request_info.user_agent.device.model

        user_properties = {
            'auth': request_info.is_auth,
        }
        if request_info.utm_source:
            user_properties['utm_source'] = request_info.utm_source
        if request_info.utm_medium:
            user_properties['utm_medium'] = request_info.utm_medium
        if request_info.utm_campaign:
            user_properties['utm_campaign'] = request_info.utm_campaign
        if request_info.utm_term:
            user_properties['utm_term'] = request_info.utm_term
        if request_info.utm_content:
            user_properties['utm_content'] = request_info.utm_content
        if request_info.utm_referrer:
            user_properties['utm_referrer'] = request_info.utm_referrer
        if len(user_properties) > 0:
            # TODO Можно не слать user_properties если они не менялись
            event['user_properties'] = user_properties

        if event_properties is not None and type(event_properties) == dict:
            # custom properties
            event['event_properties'] = event_properties

        event_package = [
            ('api_key', self.api_key),
            ('event', json.dumps([event])),
        ]

        # print(event_package)

        # ++ many other properties
        # details: https://amplitude.zendesk.com/hc/en-us/articles/204771828-HTTP-API
        return event_package

    #  data = [
    #  ('api_key', 'SOMETHINGSOMETHING'),
    #  ('event', '[{
    #       "device_id":"foo@bar",
    #       "event_type":"testing_tutorial",
    #       "user_properties":{"Cohort":"Test A"},
    #       "country":"United States",
    #       "ip":"127.0.0.1",
    #       "time":1396381378123}]'),
    # ]

    def log_event(self, event):
        if self.is_logging and event is not None and type(event) == list:
            try:
                response = requests.post(self.api_uri, data=event, timeout=(1, 2))
                if response.status_code == 400:
                    logger.error(f'Amplitude: 400 Your request is malformed. {response.text}')
                elif response.status_code == 413:
                    logger.error(f'Amplitude: 413 You had too many events in your request. {response.text}')
                elif response.status_code == 429:
                    logger.error(f'Amplitude: 429 Too many requests for a device. {response.text}')
                elif response.status_code == 500 or response.status_code == 502 or response.status_code == 504:
                    logger.error(f'Amplitude: {response.status_code} Error while handling the request. {response.text}')
                elif response.status_code == 503:
                    logger.error(f'Amplitude: 503 Server error. {response.text}')
                elif response.status_code != 200:
                    logger.error(f'Amplitude: {response.status_code} Unknown error. {response.text}')
            except Timeout as te:
                e_text = f'Amplitude: log_event {te}'
                logger.exception(e_text, exc_info=True, )
            except ConnectionError as ce:
                e_text = f'Amplitude: log_event {ce}'
                logger.exception(e_text, exc_info=True, )
            except Exception as e:
                e_text = f'Amplitude: log_event {e}'
                logger.exception(e_text, exc_info=True, )
            else:
                return response


amplitude = AmplitudeLogger(api_key=settings.AMPLITUDE_API_KEY)
