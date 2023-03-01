from api.models import expand_subscription
from api.models import get_album_page
from api.models import get_album_page_stats
from api.models import get_album_results
from api.models import get_invoice_status
from api.models import get_photo_results
from api.models import get_request_parameter
from api.models import get_user_info
from api.models import get_user_invoice
from api.models import get_user_tariffs
from core.tasks import run_free_album_search
from core.utils.u_rest_framework import get_valid_url
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

url_param = openapi.Parameter('url', openapi.IN_QUERY, description='vk album url', type=openapi.TYPE_STRING)

# VK-AUTH

# class SignIn(APIView):
#     @swagger_auto_schema(
#         manual_parameters=[url_param, ],
#         operation_description='album_processing запуск поиска по альбому',
#         responses={400: 'validation error', 200: 'free_album_search: OK'},
#     )
#     def post(self, request):
#         url = get_valid_url(request.data)

#         run_free_album_search.apply_async(
#             kwargs={'url': url},
#             queue='high_priority',
#             retry=True,
#             retry_policy={
#                 'max_retries': 3,
#                 'interval_start': 0.2,
#                 'interval_step': 0.3,
#                 'interval_max': 0.3,
#             },
#         )
#         return Response({'detail': 'OK'}, status=status.HTTP_200_OK)



class AlbumProcessingView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        manual_parameters=[url_param, ],
        operation_description='album_processing запуск поиска по альбому',
        responses={400: 'validation error', 200: 'free_album_search: OK'},
    )
    def post(self, request):
        url = get_valid_url(request.data)

        run_free_album_search.apply_async(
            kwargs={'url': url},
            queue='high_priority',
            retry=True,
            retry_policy={
                'max_retries': 3,
                'interval_start': 0.2,
                'interval_step': 0.3,
                'interval_max': 0.3,
            },
        )
        return Response({'detail': 'OK'}, status=status.HTTP_200_OK)


# Запрос статуса задачи и тестовых результатовa
class AlbumResultView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        manual_parameters=[url_param, ],
        operation_description='album_result получение результата',
        responses={400: 'validation error', 200: 'album_result', 303: 'other user album'},
    )
    def post(self, request):
        url = get_valid_url(request.data)
        results = get_album_results(url)
        return Response(results, status=status.HTTP_200_OK)


# Получение тарифов для пользователя
class TariffView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        results = get_user_tariffs(request.user)
        return Response(results, status=status.HTTP_200_OK)


# Создание счёта
class InvoiceView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        sys_code = get_request_parameter(request.data, 'code')
        items = get_request_parameter(request.data, 'items')
        results = get_user_invoice(request.user, sys_code, items)
        return Response(results, status=status.HTTP_200_OK)


# Запрос статуса оплаты
class InvoiceStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        label = get_request_parameter(request.data, 'label')
        results = get_invoice_status(request.user, label)
        return Response(results, status=status.HTTP_200_OK)


# Получить информацию по пользователю (выполняется один раз при запуске приложения у клиента)
class UserInfoView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        operation_description='albums получение информации о пользователе (Имя, Фото, Альбомы, Подписка)',
        responses={200: 'first_name, last_name, photo, user_albums, subscription', },
    )
    def get(self, request):#post
        results = get_user_info(request.user)
        return Response(results, status=status.HTTP_200_OK)


# Получить информацию по фотографиям в альбоме
class AlbumPhotosView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        album_id = get_request_parameter(request.data, 'album_id')
        photos = get_album_page(request, album_id, request.user)
        results = get_album_page_stats(album_id, photos, request.user.id)
        return Response(results, status=status.HTTP_200_OK)


# Получить статистику и данные по одной фотографии
class PhotoStatsView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        album_id = get_request_parameter(request.data, 'album_id')
        photo_id = get_request_parameter(request.data, 'photo_id')
        results = get_photo_results(album_id, photo_id, request.user.id)
        return Response(results, status=status.HTTP_200_OK)


# Создание счёта
class SubscriptionExpandView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        items = get_request_parameter(request.data, 'items')
        results = expand_subscription(request.user, items)
        return Response(results, status=status.HTTP_200_OK)
