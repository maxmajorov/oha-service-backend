import logging

import html2text
import lxml.html as html
import pymorphy2
import requests
from core.utils.u_string import transliterate
from django.utils import timezone

logger = logging.getLogger(__name__)
morph = pymorphy2.MorphAnalyzer()


def get_inner_page_view(html_doc):
    if not isinstance(html_doc, html.HtmlElement):
        logging.error(f'get_inner_page_view: wrong param type: {type(html_doc)}')
        return None
    # 1 (vc.ru, tjournal.ru, ..)
    views = html_doc.find_class('views__value')
    if len(views) == 1 and str(views[0]).isdecimal():
        value = None
        try:
            value = int(str(views[0]))
        except:  # noqa: E722
            return None
        return value
    return None


def get_favicon(html_doc, url):
    short_url = None
    try:
        parts = url.split('//', 1)
        short_url = parts[0] + '//' + parts[1].split('/', 1)[0]
    except:  # noqa: E722
        pass

    favicons = html_doc.xpath('//link[@rel="shortcut icon"]/@href')
    if len(favicons) > 0:
        favicon = favicons[0]
    elif short_url:
        favicon = f'{short_url}/favicon.ico'
    else:
        favicon = None
    if favicon and 'http:' not in favicon and short_url:
        favicon = f'{short_url}/favicon.ico'
    try:
        r = requests.get(favicon, timeout=(2, 2))
        if r.status_code != 200:
            return None
    except:  # noqa: E722
        favicon = None
    return favicon


def get_page_title(html_doc):
    title = ''
    try:
        title = html_doc.find('.//title').text
    except:  # noqa: E722
        pass
    return title


def get_page_last_modified(headers):
    if 'Last-Modified' in headers:
        modified_text = headers['Last-Modified']
    elif 'Date' in headers:
        modified_text = headers['Date']
    else:
        modified_text = None
    if modified_text:
        try:
            last_modified = timezone.datetime.strptime(modified_text, '%a, %d %b %Y %H:%M:%S %Z')
        except:  # noqa: E722
            return None
        return last_modified
    return None


def _instr(text, items):
    for item in items:
        if item in text:
            return True
    return False


def is_mention_in_html(html_text, first_name, last_name):
    if not first_name and not last_name:
        return False, False
    latin_name = False
    first_name = first_name.lower()
    last_name = last_name.lower()
    fn = morph.parse(first_name)[0]
    ln = morph.parse(last_name)[0]
    if 'LATN' in fn.tag and 'LATN' in ln.tag:
        latin_name = True
    h = html2text.HTML2Text()
    h.ignore_links = True
    text_str = h.handle(html_text)
    text_str = text_str.replace('\r\n', ' ').replace('\n', ' ').replace(
        '    ', ' ',
    ).replace('  ', ' ').replace('  ', ' ')
    latin_first_name = transliterate(first_name)
    latin_last_name = transliterate(last_name)
    latin_list = []
    cyr_list = []
    for w in text_str.split(' '):
        if len(w) < 2:
            continue
        p = morph.parse(w)[0]
        normal_form = p.normal_form
        if {'NOUN', 'anim', 'masc'} in p.tag and _instr(
                normal_form, [first_name, last_name],
        ) and normal_form not in cyr_list:
            cyr_list.append(normal_form)
        if 'LATN' in p.tag and _instr(
                normal_form, [latin_first_name, latin_last_name],
        ) and normal_form not in latin_list:
            latin_list.append(normal_form)
    pairs = zip(cyr_list[::1], cyr_list[1::1])
    cyr_variants = []
    for item in pairs:
        if item not in cyr_variants:
            cyr_variants.append(item)
    pairs = zip(latin_list[::1], latin_list[1::1])
    latin_variants = []
    for item in pairs:
        if item not in latin_variants:
            latin_variants.append(item)
    #
    exact_match = False
    similar = False
    if latin_name:
        for item in latin_variants:
            if first_name in item and last_name in item:
                exact_match = True
        for item in cyr_variants:
            trans_fn = transliterate(item[0])
            trans_ln = transliterate(item[1])
            n_item = (trans_fn, trans_ln)
            if first_name in n_item and last_name in n_item:
                exact_match = True
    else:

        for item in latin_variants:
            if latin_first_name in item and latin_last_name in item:
                exact_match = True
        for item in cyr_variants:
            if first_name in item and last_name in item:
                exact_match = True
    return exact_match, similar


def get_page_info(page_url, image_url, first_name=None, last_name=None):
    result = {
        'favicon_url': '',
        'page_title': '',
        'page_view': '',
        'found_image': False,
        'last_modified': '',
        'mention_exact_match': False,
        'mention_similar': False,
    }
    try:
        r = requests.get(page_url, timeout=(10, 30))
        if r.status_code != 200:
            return result
        # r.headers['Last-Modified'] 'Fri, 08 Nov 2019 05:42:14 GMT'
        doc = html.document_fromstring(r.text)
        # last modified
        result['last_modified'] = get_page_last_modified(r.headers)
        # url favicon
        result['favicon_url'] = get_favicon(doc, page_url)
        # page title
        result['page_title'] = get_page_title(doc)
        # page views
        result['page_view'] = get_inner_page_view(doc)
        # found image
        result['found_image'] = image_url in r.text
        # Athor name Сергей Крылов / Sergey	Krylov
        mention_exact_match, mention_similar = is_mention_in_html(r.text, first_name, last_name)
        result['mention_exact_match'] = mention_exact_match
        result['mention_similar'] = mention_similar
    except Exception:  # noqa: E722
        return result
    return result


def get_image_url_from_vk(vk_url):
    image_url = ''
    try:
        r = requests.get(vk_url, timeout=(20, 40))
        if r.status_code != 200:
            return image_url
        # r.headers['Last-Modified'] 'Fri, 08 Nov 2019 05:42:14 GMT'
        doc = html.document_fromstring(r.text)
        if '/wall' in vk_url:
            el_cover = doc.find_class('thumb_map_img')
            if len(el_cover) == 1:
                el = el_cover[0]
                if 'data-src_big' in el.attrib and el.attrib['data-src_big']:
                    background = el.attrib['data-src_big']
                    image_url = str(background).split('|')[0]
        elif '/photo' in vk_url:
            el_action = doc.find_class('mv_actions')
            if len(el_action) == 1:
                els = el_action[0].find_class('mva_item')
                for el in els:
                    if 'href' in el.attrib and el.attrib['href']:
                        image_url = el.attrib['href']
                        break
    except Exception:  # noqa: E722
        return image_url
    return image_url
