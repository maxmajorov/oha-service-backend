import logging
from urllib.parse import parse_qs
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from core.utils.u_web_page import get_image_url_from_vk
from django.conf import settings
from fake_useragent import UserAgent

from .u_google_cloud_vision import detect_web_uri
from .u_request import get_site
from .u_string import find_between
from .u_tineye import detect_tineye_matches
from .u_vk import search_photo


class PhotoInstance:
    SE_YANDEX_CLOUD = 10
    SE_YANDEX = 15
    SE_BING = 20
    SE_GOOGLE_CLOUD = 30
    SE_GOOGLE = 35
    SE_TINEYE = 40
    SE_TINEYE_API = 45
    SE_VK_API = 50

    page_url = ''
    image_url = ''
    domain = ''
    title = ''
    author = ''
    available = False
    page_check = False
    image_found = False
    crawl_date = ''
    se_type = 0
    similar = False
    partial = False
    labels = ''
    tags = ''
    score = 0

    def __index__(self):
        pass


class SearchEngine:
    logger = logging.getLogger(__name__)

    def __init__(self, spend_limit=0, is_free=True):
        self.engines = []
        self.engines.append({
            'name': 'tineye_engine',
            'engine': TinEyeReverseImageSearchEngine(),
            'count': 0,
        })
        self.engines.append({
            'name': 'yandex_engine',
            'engine': YandexReverseImageSearchEngine(),
            'count': 0,
        })
        self.engines.append({
            'name': 'google_cloud_engine',
            'engine': GoogleCloudEngine(),
            'count': 0,
        })
        self.engines.append({
            'name': 'google_engine',
            'engine': GoogleReverseImageSearchEngine(),
            'count': 0,
        })
        self.engines.append({
            'name': 'vk_engine',
            'engine': VkReverseImageSearchEngine(),
            'count': 0,
        })
        self.spend_limit = spend_limit
        self.total_price = 0

    def get_instances(self, url, vk_photo_id=None, vk_owner_id=None):
        result = []

        for i, engine in enumerate(self.engines):
            engine_request_price = engine['engine'].get_request_price()

            if self.spend_limit == 0 or self.total_price + engine_request_price < self.spend_limit:
                try:
                    engine_result = engine['engine'].get_instances(url, vk_photo_id, vk_owner_id)
                    logging.info(f'search_photo: Photo {url} {engine["name"]} results:{len(engine_result)}')
                    result += engine_result
                    self.total_price = self.total_price + engine_request_price
                    self.engines[i]['count'] = engine['count'] + 1
                except Exception as see:
                    logging.error(
                        f'get_instances {type(see)}',
                        exc_info=True,
                        extra={
                            'engine': engine['name'], 'spend_limit': self.spend_limit, 'total_price': self.total_price,
                        },
                    )
        # TODO: Если есть результаты в других поисковых системах, тогда применять самую дорогую
        return result

    def get_engine_counts(self):
        result = []
        for engine in self.engines:
            result.append({
                'name': engine['name'],
                'count': engine['count'],
            })
        return result

    def check_image_availability(self, url: str) -> bool:
        """Check if image is still available

        Args:
            url (:obj:`str`): Url to image to check
        Returns:
            :obj:`bool`: True if image is available, False if not
        """
        try:
            return requests.head(url) == 200
        except Exception:  # noqa: E722
            return False


class ReverseImageSearchEngine:
    """The base class for reverse image search engines to inherit from.

    Attributes:
        url_base (:obj:`str`): The base url of the image search engine eg. `https://www.google.com`
        url_path (:obj:`str`): The url path to the actual reverse image search function. The google url would look like
            this: `/searchbyimage?&image_url={image_url}`
        name (:obj:`str`): Name of thi search engine
        search_html (:obj:`str`): The html of the last searched image
        search_url (:obj:`str`): The image url of the last searched image

    Args:
        url_base (:obj:`str`): The base url of the image search engine eg. `https://www.google.com`
        url_path (:obj:`str`): The url path to the actual reverse image search function. It must contain `{image_url}`,
            in which the url to the image will be placed. The google url would look like this:
            `/searchbyimage?&image_url={image_url}`
        name (:obj:`str`, optional): Give the Search engine a name if you want
    """
    name = 'Base Reverse Image Search Engine'
    logger = logging.getLogger(__name__)

    search_html = None
    search_url = None
    se_type = None

    session = requests.Session()

    def __init__(self, url_base, url_path, se_type, name=None):
        self.url_base = url_base
        self.url_path = url_path
        self.se_type = se_type
        self.name = name
        self.ua = UserAgent()

    def get_search_link_by_url(self, url) -> str:
        """Get the reverse image search link for the given url

        Args:
            url (:obj:`str`): Link to the image

        Returns:
            :obj:`str`: Generated reverse image search engine for the given image
        """
        self.search_url = url
        self.search_html = ''
        return self.url_base + self.url_path.format(image_url=quote_plus(url))

    def get_html(self, url=None) -> str:
        """Get the HTML of the image search site.

        Args:
            url (:obj:`str`, optional): Link to the image, if no url is given it takes the last searched image url

        Returns:
            :obj:`str`: HTML of the image search site

        Raises:
            ValueError: If no url is defined and no last_searched_url is available
        """
        if not url:
            if not self.search_url:
                raise ValueError('No url defined and no last_searched_url available!')
            url = self.search_url
        if url == self.search_url and self.search_html:
            return self.search_html

        get_url = self.get_search_link_by_url(url)
        request = self.session.get(get_url, headers={'User-Agent': str(self.ua.firefox)})
        self.search_html = request.text
        return self.search_html

    def get_page_html(self, url_qs):
        get_url = self.url_base + url_qs
        request = self.session.get(get_url, headers={'User-Agent': str(self.ua.firefox)})
        self.search_html = request.text
        return self.search_html

    def get_instances(self, url, vk_photo_id=None, vk_owner_id=None):
        """Get info about the best matching image found

                Notes:
                    This function must be individually made for every new search engine. This is because every search engine
                    gives other data. Normally the return value should look something like this:
                    ```
                    {
                        'thumbnail': str 'LINK_TO_THUMBNAIL',
                        'website': str 'LINK_TO_FOUND_IMAGE',
                        'website_name': str 'NAME_OF_WEBSITE_IMAGE_FOUND_ON',
                        'size': {
                            'width': int 'IMAGE_WIDTH',
                            'height': int 'IMAGE_HEIGHT'
                        },
                        'similarity': float 'SIMILARITY_IN_%_TO_ORIGINAL'
                    }
                    ```

                Returns:
                    :obj:`dict`: Dictionary of the found image

                Raises:
                    ValueError: If not image was given to this class yet
                """
        return None


class TinEyeReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for tineye.com
    """

    def __init__(self):
        super(TinEyeReverseImageSearchEngine, self).__init__(
            url_base='https://tineye.com',
            url_path='/search',
            se_type=PhotoInstance.SE_TINEYE_API,
            name='TinEye',
        )

    def get_request_price(self):
        # https://cloud.google.com/vision/pricing
        bundle_size = 5000
        price_per_bundle_usd = 200
        usd_rub_exchange_rate = 65
        return (price_per_bundle_usd * usd_rub_exchange_rate) / bundle_size

    def get_instances(self, url, vk_photo_id=None, vk_owner_id=None):
        result = []
        if not vk_photo_id or not vk_owner_id:
            return result

        matches = detect_tineye_matches(url)
        match_rows = matches['matches']
        for row in match_rows:
            sites = row['sites']
            for site in sites:
                item = PhotoInstance()
                item.page_url = site['page_url']
                item.image_url = site['image_url']
                item.similar = False
                item.se_type = PhotoInstance.SE_TINEYE_API
                item.crawl_date = site['crawl_date']
                item.score = row['score']
                result.append(item)
        return result


class YandexReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for yandex.com
    """

    def __init__(self):
        super(YandexReverseImageSearchEngine, self).__init__(
            url_base='https://yandex.com',
            url_path='/images/search?url={image_url}&rpt=imageview',
            se_type=PhotoInstance.SE_YANDEX,
            name='Yandex',
        )

    def get_request_price(self):
        return 0

    def get_instances(self, url, vk_photo_id=None, vk_owner_id=None):
        results = []
        self.get_html(url)
        soup = BeautifulSoup(self.search_html, 'html.parser')
        match_rows = soup.find_all('li', {'class': 'other-sites__item'})
        if not match_rows:
            return results

        for row in match_rows:
            match_image = row.find('a', {'class', 'other-sites__preview-link'})
            if not match_image:
                continue
            image_url = match_image.get('href')

            match = row.find('div', {'class', 'other-sites__snippet'})
            if not match:
                continue
            # match_image_size = row.find('div', {'class', 'other-sites__outer-link'})
            match_site_url = row.find('a', {'class', 'other-sites__outer-link'})
            if not match_site_url:
                continue
            site_url = match_site_url.get('href')
            if 'jsredir' in site_url:
                resp = self.session.get(site_url)
                redirect_soup = BeautifulSoup(resp.content, 'html.parser')
                meta_tags = redirect_soup.find_all('meta')
                if meta_tags:
                    for meta_tag in meta_tags:
                        if hasattr(meta_tag, 'content') and 'http-equiv' in meta_tag.attrs:
                            content = meta_tag.get('content')
                            n_site_url = find_between(content, '\'', '\'')
                            if n_site_url:
                                site_url = n_site_url
                                break

            site_domain = get_site(site_url)
            item = PhotoInstance()
            item.page_url = site_url
            item.image_url = image_url
            item.similar = False
            item.partial = False
            item.domain = site_domain
            item.se_type = PhotoInstance.SE_YANDEX
            results.append(item)
        return results


class GoogleReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for google.com"""

    def __init__(self):
        super(GoogleReverseImageSearchEngine, self).__init__(
            url_base='https://www.google.com',
            url_path='/searchbyimage?image_url={image_url}&btnG=&encoded_image=&image_content=&filename=&hl=ru',
            se_type=PhotoInstance.SE_GOOGLE,
            name='Google',
        )

    def get_request_price(self):
        return 0

    def get_page_results(self, soup, first=False):
        results = []
        split_element = soup.find('div', {'class', 'normal-header'})
        if not split_element and first:
            return results
        if first:
            match_list_root = split_element.find_next_sibling('div')
            match_rows = match_list_root.find_all(lambda tag: tag.name == 'div' and 'data-hveid' in tag.attrs)
        else:
            match_rows = soup.find_all(lambda tag: tag.name == 'div' and 'data-hveid' in tag.attrs)
        for row in match_rows:
            match_page = row.find('a')
            if not match_page:
                continue
            site_url = match_page.get('href')
            match_els = row.find_all('a')
            image_url = None
            for match_el in match_els:
                url_string = match_el.get('href')
                if '/imgres?imgurl=' in url_string:
                    params = parse_qs(url_string)
                    if '/imgres?imgurl' in params and len(params['/imgres?imgurl']) == 1:
                        image_url = params['/imgres?imgurl'][0]
            if image_url:
                site_domain = get_site(site_url)
                item = PhotoInstance()
                item.page_url = site_url
                item.image_url = image_url
                item.similar = False
                item.partial = False
                item.domain = site_domain
                item.se_type = PhotoInstance.SE_GOOGLE
                results.append(item)
        return results

    def get_instances(self, url, vk_photo_id=None, vk_owner_id=None):
        results = []
        self.get_html(url)
        soup = BeautifulSoup(self.search_html, 'html.parser')
        results += self.get_page_results(soup, first=True)

        match_next_page = soup.find('table')
        if not match_next_page:
            return results
        next_pages = []
        next_page_links = match_next_page.find_all('a')
        for next_page_item in next_page_links:
            next_page_link = next_page_item.get('href')
            if next_page_link in next_pages:
                continue
            if '/search' in next_page_link:
                next_pages.append(next_page_link)
        for item in next_pages:
            self.get_page_html(item)
            soup = BeautifulSoup(self.search_html, 'html.parser')
            results += self.get_page_results(soup)
        return results


class GoogleCloudEngine:

    def __init__(self):
        pass

    def get_request_price(self):
        # https://cloud.google.com/vision/pricing
        bundle_size = 1000
        price_per_bundle_usd = 1.5
        usd_rub_exchange_rate = settings.USD_RUB_EXCHANGE_RATE
        return (price_per_bundle_usd * usd_rub_exchange_rate) / bundle_size

    def get_instances(self, url, vk_photo_id=None, vk_owner_id=None):
        web_detection = detect_web_uri(url)

        result = []
        labels = ''
        if web_detection.best_guess_labels:
            lbls = []
            for label in web_detection.best_guess_labels:
                lbls.append(label.label)
            labels = ', '.join(lbls)

        tgs = []
        if web_detection.web_entities:
            # print('\n{} Web entities found: '.format(len(web_detection.web_entities)))

            for entity in web_detection.web_entities:
                if entity.score > 0.5:
                    tgs.append(f'#{entity.description}'.replace(' ', '_'))
        tags = ' '.join(tgs)

        if web_detection.pages_with_matching_images:
            # print('\n{} Pages with matching images found:'.format(len(web_detection.pages_with_matching_images)))

            for page in web_detection.pages_with_matching_images:
                domain = get_site(page.url)

                if page.full_matching_images:
                    # print('\t{} Full Matches found: '.format(len(page.full_matching_images)))

                    for image in page.full_matching_images:
                        item = PhotoInstance()
                        item.se_type = PhotoInstance.SE_GOOGLE_CLOUD
                        item.page_url = page.url
                        item.image_url = image.url
                        item.domain = domain
                        item.title = page.page_title
                        item.labels = labels
                        item.tags = tags
                        item.partial = False
                        item.similar = False
                        result.append(item)

                if page.partial_matching_images:
                    # print('\t{} Partial Matches found: '.format(len(page.partial_matching_images)))

                    for image in page.partial_matching_images:
                        item = PhotoInstance()
                        item.se_type = PhotoInstance.SE_GOOGLE_CLOUD
                        item.page_url = page.url
                        item.image_url = image.url
                        item.domain = domain
                        item.title = page.page_title
                        item.partial = True
                        item.labels = labels
                        item.tags = tags
                        result.append(item)

        if web_detection.visually_similar_images:
            # print('\n{} visually similar images found:\n'.format(len(web_detection.visually_similar_images)))

            for image in web_detection.visually_similar_images:
                domain = get_site(image.url)
                item = PhotoInstance()
                item.se_type = PhotoInstance.SE_GOOGLE_CLOUD
                item.page_url = ''
                item.image_url = image.url
                item.domain = domain
                item.title = ''
                item.partial = True
                item.similar = True
                item.labels = labels
                item.tags = tags
                # result.append(item) # Пока никакой ценности в этих фото
        return result


class VkReverseImageSearchEngine:

    def __init__(self):
        self.se_type = PhotoInstance.SE_VK_API
        self.name = 'VK'

    def get_request_price(self):
        return 0

    def _get_image_url_from_page(self, url):
        return get_image_url_from_vk(url)

    def get_instances(self, url, vk_photo_id=None, vk_owner_id=None):
        domain = 'vk.com'
        result = []
        if not vk_photo_id or not vk_owner_id:
            return result
        url_list = search_photo(vk_owner_id, vk_photo_id)
        for result_url in url_list:
            item = PhotoInstance()
            item.se_type = self.se_type
            item.page_url = result_url
            item.image_url = self._get_image_url_from_page(result_url)
            item.domain = domain
            item.title = ''
            item.labels = ''
            item.tags = ''
            item.similar = False
            item.partial = False
            result.append(item)
        return result
