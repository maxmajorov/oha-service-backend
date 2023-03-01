import logging

from django.conf import settings
from pytineye import Backlink
from pytineye import Match
from pytineye import TinEyeAPIRequest

logger = logging.getLogger(__name__)
public_key = settings.TINEYE_PUBLIC_KEY
private_key = settings.TINEYE_PRIVATE_KEY
tineye_api = TinEyeAPIRequest(
    'http://api.tineye.com/rest/',
    # public_key,
    private_key,
)


def get_tineye_remaining_searches():
    result = 0
    try:
        responce = tineye_api.remaining_searches()
        if 'total_remaining_searches' in responce:
            result = responce['total_remaining_searches']
    except Exception as e:
        logger.error(
            f'get_tineye_remaining_searches: {type(e)}',
            exc_info=True,
            extra={},
        )
    return result


def detect_tineye_matches(url):
    result = {
        'matches': [],
        'stats': {},
    }
    try:
        responce = tineye_api.search_url(url=url)
        matches = responce.matches
        match: Match
        for match in matches:
            backlink: Backlink
            sites = []
            for backlink in match.backlinks:
                sites.append({
                    'page_url': backlink.backlink,
                    'image_url': backlink.url,
                    'crawl_date': backlink.crawl_date,
                })
            result['matches'].append({
                'image_url': match.image_url,
                'sites': sites,
                'score': match.score,
                'width': match.width,
                'height': match.height,
                'overlay': match.overlay,
            })
        result['stats'] = responce.stats
    except Exception as e:
        logger.error(
            f'get_tineye_remaining_searches: {type(e)}',
            exc_info=True,
            extra={'url': url},
        )
    return result
