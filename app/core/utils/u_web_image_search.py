import json
import logging
import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


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
    session = requests.Session()

    def __init__(self, url_base, url_path, name=None):
        self.url_base = url_base
        self.url_path = url_path
        self.name = name
        self.search_link = None

    def get_search_link_by_url(self, url):
        """Get the reverse image search link for the given url

        Args:
            url (:obj:`str`): Link to the image

        Returns:
            :obj:`str`: Generated reverse image search engine for the given image
        """
        self.search_url = url
        self.search_html = ''
        return self.url_base + self.url_path.format(image_url=quote_plus(url))

    def get_html(self, url=None):
        """Get the HTML of the image search site.

        Args:
            url (:obj:`str`): Link to the image, if no url is given it takes the last searched image url

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
        request = self.session.get(self.get_search_link_by_url(url))
        self.search_html = request.text
        return self.search_html

    def uses_list(self):
        return None

    @property
    def best_match(self):
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


class GoogleReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for google.com"""

    def __init__(self):
        super(GoogleReverseImageSearchEngine, self).__init__(
            url_base='https://www.google.com',
            url_path='/searchbyimage?&image_url={image_url}',
            name='Google',
        )


class IQDBReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for iqdb.org"""

    def __init__(self):
        super(IQDBReverseImageSearchEngine, self).__init__(
            url_base='http://iqdb.org',
            url_path='?url={image_url}',
            name='iqdb',
        )

    @property
    def best_match(self):
        if not self.search_html:
            if not self.search_url:
                raise ValueError('No image given yet!')
            self.get_html(self.search_url)
        soup = BeautifulSoup(self.search_html, 'html.parser')
        best_match = soup.find('th', text='Best match')

        if not best_match:
            return
        table = best_match.find_parent('table')
        size_match = re.match(r'\d*×\d*', table.find('td', text=re.compile('×')).text)
        size = size_match[0]
        safe = size_match.string.replace(size, '').strip(' []')

        website = table.select('td.image a')[0].attrs['href']
        if not website.startswith('http'):
            website = 'http://' + website.lstrip('/ ')
        best_match = {
            'thumbnail': self.url_base + table.select('td.image img')[0].attrs['src'],
            'website': website,
            'website_name': table.find(
                'img', {'class': 'service-icon'},
            ).find_parent('td').find(text=True, recursive=False).strip(),
            'size': {
                'width': int(size.split('×')[0]),
                'height': int(size.split('×')[1]),
            },
            'sfw': safe,
            'similarity': float(re.match(r'\d*', table.find('td', text=re.compile('similarity')).text)[0]),
            'provided by': '[IQDB](http://iqdb.org/)',
        }

        return best_match


class TinEyeReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for tineye.com"""

    def __init__(self):
        super(TinEyeReverseImageSearchEngine, self).__init__(
            url_base='https://tineye.com',
            url_path='/search?url={image_url}',
            name='TinEye',
        )

    @property
    def best_match(self):
        """

        Returns:

        """
        if not self.search_html:
            if not self.search_url:
                raise ValueError('No image given yet!')
            self.get_html(self.search_url)
        soup = BeautifulSoup(self.search_html, 'html.parser')

        match = soup.find('div', {'class', 'match'})
        if not match:
            return
        image_url = match.find('p', {'class': 'image-link'}).find('a').get('href')

        if not self.check_image_availability(image_url):
            match = match.find_next('div', {'class', 'match'})
            if not match:
                return
            image_url = match.find('p', {'class': 'image-link'}).find('a').get('href')
            if not self.check_image_availability(image_url):
                return

        match_row = match.find_parent('div', {'class': 'match-row'})
        match_thumb = match_row.find('div', {'class': 'match-thumb'})
        info = match_thumb.find('p').text
        info = [element.strip() for element in info.split(',')]

        return {
            'thumbnail': match_thumb.find('img').get('src'),
            'website_name': match.find('h4').text,
            'website': match.find('span', text='Found on: ').find_next('a').get('href'),
            'image_url': image_url,
            'type': info[0],
            'size': {
                'width': int(info[1].split('x')[0]),
                'height': int(info[1].split('x')[1]),
            },
            'volume': info[2],
            'provided by': '[TinEye](https://tineye.com/)',
        }

    def check_image_availability(self, url: str):
        """Check if image is still available

        Args:
            url (:obj:`str`): Url to image to check
        """
        try:
            return requests.head(url) == 200
        except:  # noqa: E722
            pass


class BingReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for bing.com"""

    def __init__(self):
        super(BingReverseImageSearchEngine, self).__init__(
            url_base='https://www.bing.com',
            url_path='/images/search?q=imgurl:{image_url}&view=detailv2&iss=sbi',
            name='Bing',
        )


class YandexReverseImageSearchEngine(ReverseImageSearchEngine):
    """A :class:`ReverseImageSearchEngine` configured for yandex.com"""

    def __init__(self):
        super(YandexReverseImageSearchEngine, self).__init__(
            url_base='https://yandex.com',
            url_path='/images/search?url={image_url}&rpt=imageview',
            name='Yandex',
        )

    def uses_list(self):
        if not self.search_html:
            if not self.search_url:
                raise ValueError('No image given yet!')
            self.get_html(self.search_url)
        soup = BeautifulSoup(self.search_html, 'html.parser')

        results = {}
        sites__snippet = soup.find_all('div', {'class': 'other-sites__snippet'})
        if not sites__snippet:
            return None

        for site in sites__snippet:
            outer_link = site.find('a', {'class', 'other-sites__outer-link'})
            if outer_link:
                s = outer_link.find_all(text=True, recursive=False)
                site_url = ' '.join([e.strip() for e in s])
                if site_url in results:
                    results[site_url] += 1
                else:
                    results[site_url] = 1
        for key, value in results.items():
            print(f' {key}: {value}')

        # pagination
        next_page = soup.find('div', {'class': 'more_direction_next'})
        data_bem = json.loads(next_page.get('data-bem'))
        next_url = data_bem['more']['url']
        print(f'      next_url: {next_url}')
        print('________________________________')
        page_data = self.session.get(f'https://yandex.ru{next_url}')
        print(f'      {type(page_data)} page_data: {page_data}')
        print(f'      page_data: {dir(page_data)}')
        print(f'      page_data: {len(page_data.content)}')

        soup2 = BeautifulSoup(page_data.text, 'html.parser')
        results2 = {}
        sites__snippet2 = soup2.find_all('div', {'class': 'other-sites__snippet'})
        if not sites__snippet2:
            return results
        for site in sites__snippet2:
            outer_link = site.find('a', {'class', 'other-sites__outer-link'})
            if outer_link:
                s = outer_link.find_all(text=True, recursive=False)
                site_url = ' '.join([e.strip() for e in s])
                if site_url in results:
                    results2[site_url] += 1
                else:
                    results2[site_url] = 1

        return results
