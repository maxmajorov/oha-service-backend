import json

from allauth.socialaccount.models import SocialAccount
from billing.models import get_expires_date
from billing.models import init_subscription
from billing.models import Invoice
from billing.models import Subscription
from billing.models import SubscriptionHistory
from core.models import Album
from core.models import Author
from core.models import Base
from core.models import DomainData
from core.models import Photo
from core.models import SearchResult
from core.utils.u_search_engine import PhotoInstance
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient


class GetStatsTest(TestCase):
    """ Test module for get photos stats API """

    def setUp(self):
        self.maxDiff = None
        self.email = 'user@example.com'
        self.user, created = User.objects.get_or_create(
            username='user',
            is_active=True,
            email=self.email,
            password='p@$$w0rd',
        )
        self.vk_user_id = '97596650'
        self.account, created = SocialAccount.objects.get_or_create(
            uid=self.vk_user_id,
            provider='vk',
            user=self.user,
        )
        self.vk_album_id = '271565395'
        self.url = f'https://vk.com/album{self.vk_user_id}_{self.vk_album_id}'
        self.vk_photo_ids = ['457239388', '457239387', '457239386', '457239385', '457239384', '457239382']
        self.domains = ['one.com', 'two.ru', 'three.com', 'four.ru', 'five.com', 'six.ru']
        self.results = {
            '457239388': ['one.com', ],
            '457239387': [],
            '457239386': ['one.com', 'two.ru'],
            '457239385': ['two.ru', 'three.com', 'four.ru', 'five.com', ],
            '457239384': ['four.ru', 'five.com', 'six.ru', ],
            '457239382': ['one.com', 'two.ru', 'three.com', 'four.ru', 'five.com', 'six.ru', ],
        }
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_authenticate(user=self.user)
        self.today = timezone.now()
        # Subscription
        init_subscription()
        subscription = Subscription.objects.get(sys_code='04012020_100')
        # Author
        author, created = Author.objects.get_or_create(src_id=self.vk_user_id, source=Base.ST_VK, )
        # Album
        album, created = Album.objects.get_or_create(
            src_id=self.vk_album_id,
            source=Base.ST_VK,
            url=self.url,
            author=author,
            user=self.user,
            status=Album.PS_DON,
            last_search_photos=self.today,
        )
        # Invoice
        invoice, created = Invoice.objects.get_or_create(
            user=self.user,
            status=Invoice.ST_NEW,
            subscription=subscription,
            amount=subscription.price,
            items=[self.vk_album_id, ],
        )
        # SubscriptionHistory
        sh, created = SubscriptionHistory.objects.get_or_create(
            user=invoice.user,
            subscription=invoice.subscription,
            invoice=invoice,
            items=invoice.items,
            active=True,
            activate_date=self.today,
            expires_date=get_expires_date(self.today),
            fix_parameter=invoice.subscription.parameter,
        )
        # Photo
        for vk_photo_id in self.vk_photo_ids:
            photo, created = Photo.objects.get_or_create(
                source=Photo.ST_VK,
                source_id=vk_photo_id,
                src_id=vk_photo_id,
                mini_url=f'https://sun9-28.userapi.com/{vk_photo_id}/image.jpg',
                maxi_url=f'https://sun9-13.userapi.com/{vk_photo_id}/image.jpg',
                source_album=self.vk_album_id,
                source_owner=self.vk_user_id,
                user=self.user,
                album=album,
                search_date=self.today,
            )
        # DomainData
        for domain in self.domains:
            domain, created = DomainData.objects.get_or_create(
                domain=domain,
                user=None,
            )
        # SearchResult
        for key, value in self.results.items():
            photo = Photo.get_by_vk_id(key, self.user.id)
            for domain in value:
                domain_data = DomainData.objects.get(domain=domain)
                duplicate, created = SearchResult.objects.get_or_create(
                    user=self.user,
                    photo=photo,
                    engine=PhotoInstance.SE_YANDEX,
                    domain=domain_data,
                    page_url=f'https://{domain}/index.html',
                    image_url=f'https://{domain}/image.jpeg',
                    found_image=True,
                    similar_images=False,
                    partial_matching=False,
                )

    def test_album_stats(self):
        # get API response
        response = self.client.post(
            reverse('user_info'),
            content_type='application/json',
        )
        activate_date = timezone.now().date()
        expires_date = get_expires_date(activate_date).date()
        valid_result = {
            'user_albums': [
                {
                    'id': '271565395',
                    'size': 0,
                    'title': '',
                    'thumb_src': '',
                    'stats': {
                        'vk_album_id': '271565395',
                        'search_done': True,
                        'site_count': 6,
                        'found_count': 5,
                        'mention_count': 0,
                    },
                },
            ],
            'subscription': {
                'expires_date': expires_date,
                'activate_date': activate_date,
                'sys_code': '04012020_100',
                'parameter': 100,
                'items': ['271565395'],
            },
        }
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, valid_result)

    def test_album_photos(self):
        # get API response
        response = self.client.post(
            reverse('album_photos'),
            data=json.dumps(
                {
                    'album_id': self.vk_album_id,
                    'limit': 10,
                    'offset': 1,
                },
            ),
            content_type='application/json',
        )
        valid_result = dict(
            album_search_done=True,
            photos=[
                {
                    'album_id': self.vk_album_id, 'photo_id': '457239385',
                    'sites': [
                        {
                            'page_url': 'https://two.ru/index.html', 'title': '',
                            'mention': False, 'domain': 'two.ru',
                        },
                        {
                            'page_url': 'https://three.com/index.html',
                            'title': '', 'mention': False, 'domain': 'three.com',
                        },
                        {
                            'page_url': 'https://four.ru/index.html', 'title': '',
                            'mention': False, 'domain': 'four.ru',
                        },
                        {
                            'page_url': 'https://five.com/index.html',
                            'title': '', 'mention': False, 'domain': 'five.com',
                        },
                    ],
                    'mini_url': 'https://sun9-28.userapi.com/457239385/image.jpg',
                    'maxi_url': 'https://sun9-13.userapi.com/457239385/image.jpg',
                    'duplicate_count': 4, 'in_progress': False,
                },
                {
                    'album_id': self.vk_album_id, 'photo_id': '457239384',
                    'sites': [
                        {
                            'page_url': 'https://four.ru/index.html', 'title': '',
                            'mention': False, 'domain': 'four.ru',
                        },
                        {
                            'page_url': 'https://five.com/index.html',
                            'title': '', 'mention': False, 'domain': 'five.com',
                        },
                        {
                            'page_url': 'https://six.ru/index.html', 'title': '',
                            'mention': False, 'domain': 'six.ru',
                        },
                    ],
                    'mini_url': 'https://sun9-28.userapi.com/457239384/image.jpg',
                    'maxi_url': 'https://sun9-13.userapi.com/457239384/image.jpg',
                    'duplicate_count': 3, 'in_progress': False,
                },
                {
                    'album_id': self.vk_album_id, 'photo_id': '457239386',
                    'sites': [
                        {
                            'page_url': 'https://one.com/index.html', 'title': '',
                            'mention': False, 'domain': 'one.com',
                        },
                        {
                            'page_url': 'https://two.ru/index.html', 'title': '',
                            'mention': False, 'domain': 'two.ru',
                        },
                    ],
                    'mini_url': 'https://sun9-28.userapi.com/457239386/image.jpg',
                    'maxi_url': 'https://sun9-13.userapi.com/457239386/image.jpg',
                    'duplicate_count': 2, 'in_progress': False,
                },
                {
                    'album_id': self.vk_album_id, 'photo_id': '457239388',
                    'sites': [
                        {
                            'page_url': 'https://one.com/index.html', 'title': '',
                            'mention': False, 'domain': 'one.com',
                        },
                    ],
                    'mini_url': 'https://sun9-28.userapi.com/457239388/image.jpg',
                    'maxi_url': 'https://sun9-13.userapi.com/457239388/image.jpg',
                    'duplicate_count': 1, 'in_progress': False,
                },
                {
                    'album_id': self.vk_album_id, 'photo_id': '457239387',
                    'sites': [],
                    'mini_url': 'https://sun9-28.userapi.com/457239387/image.jpg',
                    'maxi_url': 'https://sun9-13.userapi.com/457239387/image.jpg',
                    'duplicate_count': 0, 'in_progress': False,
                },
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, valid_result)

    def test_photo_stats(self):
        # get API response
        response = self.client.post(
            reverse('photo_stats'),
            data=json.dumps(
                {
                    'album_id': self.vk_album_id,
                    'photo_id': self.vk_photo_ids[0],
                },
            ),
            content_type='application/json',
        )
        valid_result = {
            'photo_id': self.vk_photo_ids[0],
            'sites': [
                {'page_url': 'https://one.com/index.html', 'title': '', 'mention': False, 'domain': 'one.com'},
            ],
            'mini_url': 'https://sun9-28.userapi.com/457239388/image.jpg',
            'maxi_url': 'https://sun9-13.userapi.com/457239388/image.jpg',
            'duplicate_count': 1,
            'in_progress': False,
            'album_id': self.vk_album_id,
        }

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, valid_result)
