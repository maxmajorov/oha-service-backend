#### Разработка

- Окружение:
    Python 3.7.4
    ```bash
    python --version
    ```

- Зависимости:
    ```bash
    pip install -U pip
    pip install -U setuptools
    pip install -r requirements-dev.txt
    ```

- Добавляем хуки на коммиты, пуши:
    ```bash
    pre-commit install -f
    pre-commit install -f --hook-type pre-push
    ```

- Собрать и поднять локальные сервисы:

    ```bash
    docker-compose -f docker-compose.yml build --pull
    docker-compose -f docker-compose.yml up -d
    ```

- Подготовка БД
    ```bash
    python manage.py makemigrations --settings=app.settings.dev
    python manage.py migrate --settings=app.settings.dev
    python manage.py init_app

    python manage.py shell -c "from django.contrib.auth.models import User; from core.models import UserProfile; u = User.objects.create_superuser(username='admin', email='admin@example.com', password='adminpass', first_name='Adam',last_name='Smith'); profile = UserProfile(user=u); profile.save();"
    ```

- Генерация сертификата SSL для локальной разработки

    ```bash
    cd app/tmp
    openssl req -x509 -out localhost.crt -keyout localhost.key \
      -newkey rsa:2048 -nodes -sha256 \
      -subj '/CN=localhost' -extensions EXT -config <( \
       printf "[dn]\nCN=localhost\n[req]\ndistinguished_name = dn\n[EXT]\nsubjectAltName=DNS:localhost\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth")
     ```

- Запуск приложения
    ```bash
    python manage.py runserver localhost:8000 --settings=app.settings.dev

    python manage.py runserver_plus localhost:8000 --cert-file tmp/localhost.crt --key-file tmp/localhost.key --settings=app.settings.dev
    ```

- Запуск тестов
    ```bash
    python manage.py test
    ```

- Работа с переводом
    ```bash
    python manage.py makemessages -l ru && python manage.py compilemessages -l ru
    ```

- Обновление статики
    ```bash
    python manage.py collectstatic --noinput | tail -1
    ```

- Проверка urls
    ```bash
    python manage.py show_urls
    ```

- Проверка сборки docker образов
    ```bash
    docker-compose -f docker-compose.publish.yml build --pull
    ```

- Отладка настроек сервера
    ```bash
    cd deploy/setup
    docker run --rm -it -v ${PWD}/srv_home:/home -w /home debian:10 bash
    ```

- Локальное воспроизведение задач пользователя

    - запуск обновления информации по альбомам пользователя
```python
from core.tasks import run_free_album_search

```

- Локальная авторизация через VK
    запрос:
    https://localhost:8000/api/accounts/vk/login/?method=oauth2

    для проверки:
    https://localhost:8000/api/v1/user/info/


- Собрать и поднять локальный worker

    ```bash
    docker-compose -f docker-local-worker.yml build --no-cache --pull worker_lo
    docker-compose -f docker-local-worker.yml up -d
    ```

- Правки в базовом образе

    https://github.com/noxxer/python37_science_image/edit/master/requirements.txt

- Server postgres backup

    # подключение
    ```bash
    sudo sudo -u postgres psql
    ```
    # Список баз
    ```bash
    \l
    \q
    ```

    # Права на папку с дампами
    ```bash
    chown -R devops:devops /home/devops
    ```

    # Выполнение дампа
    ```bash
    sudo su - postgres
    time pg_dump -U postgres -Fc ohaoha > /home/devops/backup/ohaoha/database_ohaoha_fc_21042020.dump.gz
    curl -X POST https://content.dropboxapi.com/2/files/upload \
        --header "Authorization: Bearer <TOKEN>" \
        --header "Dropbox-API-Arg: {\"path\": \"/home/devops/backup/ohaoha/database_ohaoha_fc_21042020.dump.gz\"}" \
        --header "Content-Type: application/octet-stream" \
        --data-binary @database_ohaoha_fc_21042020.dump.gz
    ```
    # Локальное восстановление
     docker-compose exec postgres pg_restore -C --clean --no-acl --no-owner -U dev -d ohaoha /app/data/backups/database_ohaoha_fc_21042020.dump.gz
     docker-compose exec postgres pg_restore --data-only -U dev -d ohaoha /app/data/backups/database_ohaoha_fc_21042020.dump.gz

     python manage.py shell -c "from django.contrib.auth.models import User; from core.models import UserProfile; u = User.objects.create_superuser(username='admin', email='admin@example.com', password='adminpass', first_name='Adam',last_name='Smith'); profile = UserProfile(user=u); profile.save();"
