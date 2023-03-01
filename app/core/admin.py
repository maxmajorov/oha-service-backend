from django.contrib import admin
from django.contrib.sessions.models import Session

from .models import Album
from .models import Author
from .models import Classifier
from .models import DomainContacts
from .models import DomainData
from .models import EngineCounter
from .models import Photo
from .models import SearchResult
from .models import UserNps
from .models import UserProfile
from .tasks import run_check_search_results


def load_photos(modeladmin, request, queryset):
    for item in queryset:
        item.update_photos()


def reset_status(modeladmin, request, queryset):
    for item in queryset:
        item.reset_status()


def check_photo_similarity(modeladmin, request, queryset):
    for item in queryset:
        item.check_similarity()


def full_check_results(modeladmin, request, queryset):
    for item in queryset:
        item.full_check_results()


def full_check_similarity(modeladmin, request, queryset):
    for item in queryset:
        item.full_check_similarity()


def search_uses(modeladmin, request, queryset):
    for item in queryset:
        item.search_photo()


def check_result(modeladmin, request, queryset):
    item: SearchResult
    for item in queryset:
        run_check_search_results.apply_async(
            kwargs={'db_result_id': item.id, },
            queue='high_priority',
            countdown=1,
        )


def get_exif(modeladmin, request, queryset):
    for item in queryset:
        item.get_exif()


def activate_classifier(modeladmin, request, queryset):
    if queryset.count() != 1:
        return
    item = queryset.first()
    item.set_active()


load_photos.short_description = 'Скачать инфо по всем фото в альбоме'
full_check_results.short_description = 'Обновить инфо по всем результатам поиска фоток в альбоме'
search_uses.short_description = 'Поиск картинки в интернет'
get_exif.short_description = 'Получение EXIF'
check_photo_similarity.short_description = 'Расчитать похожесть фото и её поисковых результатов'
check_result.short_description = 'Проверить результат'
activate_classifier.short_description = 'Использовать выбранную модель'
reset_status.short_description = 'Сбросить статус на Новый'
full_check_similarity.short_description = 'Выполнить расчёт предсказания похожести'


class AuthorAdmin(admin.ModelAdmin):
    search_fields = ('src_id', 'first_name', 'last_name')
    list_display = (
        'id', 'link', 'is_group', 'source', 'first_name', 'last_name',
        'followers_count', 'user', 'create_date', 'update_date',
    )
    date_hierarchy = 'create_date'


class AlbumAdmin(admin.ModelAdmin):
    search_fields = ('url', )
    list_display = (
        'id', 'source', 'src_id', 'status', 'url', 'user', 'author_id', 'count',
        'create_date', 'update_date', 'last_update_photos', 'last_search_photos',
    )
    list_filter = ('source', 'status')
    date_hierarchy = 'create_date'
    actions = [load_photos, full_check_results, reset_status, full_check_similarity]


class PhotoAdmin(admin.ModelAdmin):
    search_fields = ('id', 'mini_url', 'source_id', 'source_album', 'source_owner')
    list_display = ('id', 'image_tag', 'source', 'mini_url', 'user', 'update_date', 'search_date')
    date_hierarchy = 'create_date'
    actions = [search_uses, get_exif, check_photo_similarity]


class SearchResultAdmin(admin.ModelAdmin):
    search_fields = ('engine', 'photo_id', 'title', 'image_url', 'page_url', 'domain__domain')
    list_display = (
        'id', 'photo_id', 'found_image', 'mention_exact_match',
        'engine', 'domain', 'title', 'create_date', 'last_checked',
    )
    list_filter = (
        'engine', 'found_image', 'mention_exact_match', 'predict_similar', 'verified_similarity',
        'partial_matching', 'similar_images',
    )
    date_hierarchy = 'create_date'
    actions = [check_result]


class DomainDataAdmin(admin.ModelAdmin):
    search_fields = ('domain',)
    list_display = ('id', 'domain', 'create_date', 'update_date', 'search_date')
    date_hierarchy = 'create_date'


class DomainContactsAdmin(admin.ModelAdmin):
    search_fields = ('domain',)
    list_display = ('id', 'domain', 'engine', 'create_date', 'update_date', 'search_date')
    list_filter = ('engine', )
    date_hierarchy = 'create_date'


class EngineCounterAdmin(admin.ModelAdmin):
    search_fields = ('engine', 'album')
    list_display = (
        'id', 'engine', 'name', 'album', 'photo', 'user',
        'search_date', 'is_free', 'successful', 'search_count', 'result_count',
    )
    list_filter = ('engine', 'is_free', 'successful', )
    date_hierarchy = 'search_date'


class ClassifierAdmin(admin.ModelAdmin):
    search_fields = ('id', 'file_path')
    list_display = ('id', 'active', 'version', 'score', 'confusion_matrix', 'file_name')
    list_filter = ('version', 'active')
    actions = [activate_classifier]


class UserProfileAdmin(admin.ModelAdmin):
    search_fields = ('user', 'photo', 'anonym_session_key', 'total_photos')
    list_display = ('user', 'founders_access', 'photo', 'anonym_session_key', 'total_photos')


class UserNpsAdmin(admin.ModelAdmin):
    search_fields = ('user', 'nps', 'message')
    list_display = ('user', 'nps', 'message')


admin.site.register(Author, AuthorAdmin)
admin.site.register(Album, AlbumAdmin)
admin.site.register(Photo, PhotoAdmin)
admin.site.register(SearchResult, SearchResultAdmin)
admin.site.register(DomainData, DomainDataAdmin)
admin.site.register(DomainContacts, DomainContactsAdmin)
admin.site.register(EngineCounter, EngineCounterAdmin)
admin.site.register(Classifier, ClassifierAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(UserNps, UserNpsAdmin)
admin.site.register(Session)
