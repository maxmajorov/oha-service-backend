import logging
from tempfile import TemporaryFile

import requests
from django.core.files import File

logger = logging.getLogger(__name__)


def download_to_file_field(url, field, file_name):
    try:
        with TemporaryFile() as tf:
            r = requests.get(url, stream=True)
            for chunk in r.iter_content(chunk_size=4096):
                tf.write(chunk)

            tf.seek(0)
            field.save(file_name, File(tf))
    except Exception as e:
        logger.error(
            f'download_to_file_field error {type(e)}',
            exc_info=True,
            extra={'url': url, },
        )
