import io
import logging

import cv2
import numpy as np
import requests
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000
from colormath.color_objects import LabColor
from colormath.color_objects import sRGBColor
from colorthief import ColorThief
from django.conf import settings
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class SimilarService:
    is_working = False
    session = requests.Session()

    def __init__(self, base_image_url, base_image_data=None):
        self.endpoint = settings.SIMILARITY_API_ENDPOINT
        self.ua = UserAgent()
        self.base_image_url = base_image_url
        self.algorithms = {
            'BlockMeanHash': cv2.img_hash.BlockMeanHash_create(),
            'RadialVarianceHash': cv2.img_hash.RadialVarianceHash_create(),
            'AverageHash': cv2.img_hash.AverageHash_create(),
            'MarrHildrethHash': cv2.img_hash.MarrHildrethHash_create(),
            'PHash': cv2.img_hash.PHash_create(),
        }
        if not base_image_data:
            self.base_image_data = self._compute(self.base_image_url)
        else:
            ndarray_data = {}
            for key, value in base_image_data.items():
                if key in self.algorithms:
                    ndarray_data[key] = np.fromstring(value, dtype=np.uint8)
                else:
                    ndarray_data[key] = value
            self.base_image_data = ndarray_data
        self.session.headers = {'User-Agent': str(self.ua.firefox)}
        return

    def get_base_image_data(self):
        jsonify_data = {}
        for key, value in self.base_image_data.items():
            if isinstance(value, np.ndarray):
                value: np.ndarray
                jsonify_data[key] = value.tostring()
            else:
                jsonify_data[key] = value
        return jsonify_data

    def _url_to_image(self, url):
        # download the image, convert it to a NumPy array, and then read
        # it into OpenCV format
        resp = self.session.get(url)
        image_stream = io.BytesIO(resp.content)
        numpy_image = np.asarray(bytearray(resp.content), dtype='uint8')
        numpy_image = cv2.imdecode(numpy_image, cv2.IMREAD_COLOR)
        # return the image
        return numpy_image, image_stream

    def _compute(self, url):
        result = {}
        try:
            img, img_stream = self._url_to_image(url)
            color_thief = ColorThief(img_stream)
            dominant_color = color_thief.get_color(quality=1)
            result['img_dominant_color_r'] = dominant_color[0]
            result['img_dominant_color_g'] = dominant_color[1]
            result['img_dominant_color_b'] = dominant_color[2]

            for key, algorithm in self.algorithms.items():
                result[key] = algorithm.compute(img)
        except Exception as e:
            logging.error(
                f'SimilarService _compute error: {type(e)}',
                exc_info=True,
            )
            return result
        return result

    def compare_with(self, case_url):
        result = {}
        case_image_data = self._compute(case_url)
        if not case_url or not case_image_data or not self.base_image_data:
            return result

        # Color compare
        color_base_rgb = sRGBColor(
            self.base_image_data['img_dominant_color_r'],
            self.base_image_data['img_dominant_color_g'],
            self.base_image_data['img_dominant_color_b'],
        )
        color_case_rgb = sRGBColor(
            case_image_data['img_dominant_color_r'],
            case_image_data['img_dominant_color_g'],
            case_image_data['img_dominant_color_b'],
        )
        color_base_lab = convert_color(color_base_rgb, LabColor)
        color_case_lab = convert_color(color_case_rgb, LabColor)
        delta_color = delta_e_cie2000(color_base_lab, color_case_lab)
        result['base_dominant_color_r'] = self.base_image_data['img_dominant_color_r']
        result['base_dominant_color_g'] = self.base_image_data['img_dominant_color_g']
        result['base_dominant_color_b'] = self.base_image_data['img_dominant_color_b']
        result['delta_color'] = delta_color

        # OpenCV compare
        for key, algorithm in self.algorithms.items():
            result[key] = algorithm.compare(self.base_image_data[key], case_image_data[key])
        return result
