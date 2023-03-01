import calendar
import logging
import math

from dateutil.relativedelta import relativedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def completed_quarter(dt):
    """
    Цель: по дате вернуть оформленный квартал года (2017Q2)

    :param dt:
    :return:
    """
    quarter_map = ((1, 0), (2, 0), (3, 0), (4, 0))
    quarter, yd = quarter_map[(dt.month - 1) // 3]
    return '{}Q{}'.format(dt.year + yd, quarter)


def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = int(source_date.year + month / 12)
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return timezone.datetime(year, month, day)


def completed_week(dt):
    # %U - На основании четвертого января (воскресенье первый день недели)
    # %V - На основании первого четверга (понедельник первый день недели)
    # %W - На основании четвертого января (понедельник первый день недели)
    # +1 - сдвиг, в питоне нумерация с 00, в ГОСТ ИСО 8601-2001 с 01.
    week = int(dt.strftime('%V'))
    year = int(dt.strftime('%y'))
    if dt.month == 1 and week > 50:
        year -= 1
    elif dt.month == 12 and week < 2:
        year += 1
    return '{}W{}'.format(year, '%02d' % week)


def formatted_label(date, detail):
    if detail == 'month':
        return date.strftime('%m.%y')
    elif detail == 'day':
        return date.strftime('%d.%m.%y')
    elif detail == 'week':
        return completed_week(date)
    elif detail == 'quarter':
        return completed_quarter(date)
    elif detail == 'year':
        if isinstance(date, int):
            return date
        return date.year
    else:
        logging.error(f'formatted_label: unknown detail: {detail}')
        return date.strftime('%d.%m.%y')


def get_range_labels(start_date, end_date, detail='month'):
    """
    Цель: по двум датам и коду интервала вернуть список оформленных интервалов из указанного диапазона
    """
    # detail
    # day     - DD.MM.YY
    # week    - YY-Www
    # month   - MM.YY
    # quarter - YYYYQN
    # year    - YYYY
    # datetime.replace([year[, month[, day[, hour[, minute[, second[, microsecond[, tzinfo]]]]]]]])
    # print('debug: type[{}], end_date[{}]'.format(type(end_date),str(end_date)))
    end_date = end_date.replace(hour=23, minute=59, second=59)
    if detail == 'month':
        period_count = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
        labels = [formatted_label(end_date - relativedelta(months=x), detail)
                  for x in reversed(list(range(period_count)))]
    elif detail == 'day':
        period_count = (end_date - start_date).days + 1
        labels = [formatted_label(end_date - relativedelta(days=x), detail)
                  for x in reversed(list(range(period_count)))]
    elif detail == 'week':
        s_week = int(start_date.strftime('%V'))
        s_year = start_date.year
        if start_date.month == 1 and s_week > 50:
            s_year -= 1
        e_week = int(end_date.strftime('%V'))
        e_year = end_date.year
        if end_date.month == 12 and e_week < 2:
            e_year += 1
        period_count = (e_year - s_year) * 52 + (e_week - s_week) + 1
        labels = [formatted_label(end_date - relativedelta(weeks=x), detail)
                  for x in reversed(list(range(period_count)))]
    elif detail == 'quarter':
        s_quart = int(math.ceil(start_date.month / 3.))
        e_quart = int(math.ceil(end_date.month / 3.))
        period_count = (end_date.year - start_date.year) * 4 + (e_quart - s_quart) + 1
        labels = [formatted_label(end_date - relativedelta(months=x * 3), detail)
                  for x in reversed(list(range(period_count)))]
    elif detail == 'year':
        period_count = end_date.year - start_date.year + 1
        labels = [formatted_label(end_date.year - x, detail)
                  for x in reversed(list(range(period_count)))]
    else:
        labels = ['Не определённый интеравал']
    return labels


def dict_fetch_all(cursor):
    """
    Return all rows from a cursor as a dict

    :param cursor:
    :return:
    """
    columns = [col[0] for col in cursor.description]
    return [
        dict(list(zip(columns, row)))
        for row in cursor.fetchall()
    ]


class ColorPalete:
    # https://experience.sap.com/fiori-design-web/values-and-names/
    STYLE_DEFAULT = 'default'  # По умолчанию
    STYLE_QUALITATIVE = 'qualitative'  #
    STYLE_NEUTRAL_BLUE = 'neutral blue'
    background = {
        'default': [
            '255,  99, 132',
            '54,  162, 235',
            '255, 206,  86',
            '75,  192, 192',
            '153, 102, 255',
            '255, 159,  64',
        ],
        'qualitative': [
            '92, 186, 230',
            '182, 217, 87',
            '250, 195, 100',
            '140, 211, 255',
            '217, 152, 203',
            '242, 210, 73',
            '147, 185, 198',
            '204, 197, 168',
            '82, 186, 204',
            '219, 219, 70',
            '152, 170, 251',
        ],
        'neutral blue': [
            '25, 52, 65',
            '62, 96, 111',
            '145, 170, 157',
            '209, 219, 189',
        ],
    }

    def __init__(self):
        self.current = 0

    def get_bg(self, style):
        colors = '255, 99, 132'
        if style in self.background and len(self.background[style]) > self.current:
            colors = self.background[style][self.current]
        result = 'rgba({}, 0.2)'.format(colors)
        return result

    def get_bg_next(self, style):
        result = self.get_bg(style)
        next(self)
        return result

    def get_br(self, style):
        colors = '255, 99, 132'
        if style in self.background and len(self.background[style]) > self.current:
            colors = self.background[style][self.current]
        result = 'rgba({}, 1)'.format(colors)
        return result

    def get_br_next(self, style):
        result = self.get_br(style)
        next(self)
        return result

    def __next__(self):
        self.current += 1
