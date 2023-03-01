from django.contrib.auth.models import User
from django.test import TestCase

from ..models import Album
from ..models import Author
from ..models import Base


class AlbumTest(TestCase):
    """ Test module for Album model """
    def setUp(self):
        self.vk_user_id = '232627122'
        self.vk_album_id = '271563395'
        self.url = f'https://vk.com/album{self.vk_user_id}_{self.vk_album_id}'
        self.email = 'user@example.com'
        user, created = User.objects.get_or_create(
            username='user',
            is_active=True,
            email=self.email,
        )
        author, created = Author.objects.get_or_create(src_id=self.vk_user_id, source=Base.ST_VK,)
        Album.objects.create(
            src_id=self.vk_album_id,
            source=Base.ST_VK,
            url=self.url,
            author=author,
            user=user,
        )

    def test_album_get_by_vk_id(self):
        user = User.objects.first()
        album = Album.get_by_vk_id(self.vk_album_id, user.id)
        self.assertEqual(
            album.url, self.url,
        )
