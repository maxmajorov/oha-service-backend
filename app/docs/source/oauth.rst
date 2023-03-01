Описание работы
===============

Авторизация через VK
----------------------------------------------

Url для выполнения авторизации

``api/accounts/vk/login/?method=oauth2``

Redirect URI настроенный на стороне VK

``api/accounts/vk/login/callback/``

Url перенаправления после авторизации указан

``LOGIN_REDIRECT_URL = '/'``
