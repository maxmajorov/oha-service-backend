#### Разработка

- Получение JWT токена:
    ```bash
    curl \
      -k -X POST \
      -H "Content-Type: application/json" \
      -d '{"username": "admin", "password": "adminpass"}' \
      https://ohaoha.ru/api/v1/auth/jwt/create/
    ```

- Продление JWT токена:
    ```bash
    curl \
      -k -X POST \
      -H "Content-Type: application/json" \
      -d '{"refresh":"eyJ0eXAiDWaSRDw0"}' \
      https://ohaoha.ru/api/v1/auth/jwt/refresh/
    ```

- Информация о пользователе:
    ```bash
    curl \
      -k -X GET \
      -H "Authorization: Bearer eyJ0e4_0" \
      https://ohaoha.ru/api/v1/rest-auth/user/
    ```

- Авторизация через Facebook

    ```bash
    https://ohaoha.ru/api/v1/accounts/facebook/login/ 
    ```

- Авторизация через VK

    ```bash
    https://ohaoha.ru/api/v1/accounts/vk/login/
    ```

- Проверить портфолио

    ```bash
    
    ```
