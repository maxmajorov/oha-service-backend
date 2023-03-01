import math

from core.utils.u_chart import add_months
from core.utils.u_chart import ColorPalete
from core.utils.u_chart import dict_fetch_all
from core.utils.u_chart import formatted_label
from core.utils.u_chart import get_range_labels
from django.db import connection
from django.db.models import Count
from django.db.models import Sum
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncWeek
from django.db.models.functions import TruncYear
from django.utils import timezone


def get_default_group_count(group):
    if group == 'day':
        return 10
    if group == 'week':
        return 8
    if group == 'month':
        return 6
    if group == 'year':
        return 3
    return 10


def get_valid_group(group):
    if group == 'week' or group == 'month' or group == 'year' or group == 'day':
        return group
    else:
        return 'day'


class ChartTimeLine:
    chart_type = 'bar'  # line bar
    style = ColorPalete.STYLE_QUALITATIVE
    y_axes_steps = 7

    def __init__(self, group='day', group_count=30, title=None, stacked=False):
        self.group = group
        self.group_count = group_count
        self.data_sets = []
        self.options = {}
        self.max_value = 0
        self.default_value = 0
        self.palette = ColorPalete()
        if title:
            title_display = True
        else:
            title_display = False
            title = ''
        self.options = {
            'responsive': True,
            'legend': {'position': 'top'},
            'title': {
                'display': title_display,
                'text': title,
            },
        }
        self.date_to = timezone.now()
        self.date_from = self._get_date_from()
        self.labels = get_range_labels(self.date_from, self.date_to, self.group)

    def _get_date_from(self):
        if self.group == 'week':
            start = self.date_to - timezone.timedelta(days=self.group_count * 7)
        elif self.group == 'month':
            start = add_months(self.date_to, -self.group_count)
        elif self.group == 'year':
            start = add_months(self.date_to, -self.group_count * 12)
        elif self.group == 'day':
            start = self.date_to - timezone.timedelta(days=self.group_count)
        else:
            self.group = 'day'
            start = self.date_to - timezone.timedelta(days=self.group_count)
        return start

    def _get_series(self, result, label, progressive):
        values = []
        last_value = self.default_value
        if result is not None:
            for item in self.labels:
                if item in result:
                    values.append(result[item])
                    last_value = result[item]
                else:
                    if progressive:
                        values.append(last_value)
                    else:
                        values.append(self.default_value)
        series = {
            'label': label,
            'data': values,
            'backgroundColor': self.palette.get_bg(self.style),
            'borderColor': self.palette.get_br(self.style),
            'borderWidth': 2,
        }
        next(self.palette)
        return series

    def _get_series_from_cursor(self, cursor, label, progressive=False):
        db_result = dict_fetch_all(cursor)
        result = {}
        for item in db_result:
            n = int(item['value'])
            result[str(item['label'])] = n
            if n > self.max_value:
                self.max_value = n
        series = self._get_series(result, label, progressive)
        next(self.palette)
        return series

    def _get_time_group_queryset(self, queryset, time_field):
        # cut period
        filter_column = time_field + '__gt'
        cut_queryset = queryset.filter(**{filter_column: self.date_from})
        # group by
        if self.group == 'week':
            trunc_queryset = cut_queryset.annotate(label=TruncWeek(f'{time_field}'))
        elif self.group == 'month':
            trunc_queryset = cut_queryset.annotate(label=TruncMonth(f'{time_field}'))
        elif self.group == 'year':
            trunc_queryset = cut_queryset.annotate(label=TruncYear(f'{time_field}'))
        elif self.group == 'day':
            trunc_queryset = cut_queryset.annotate(label=TruncDay(f'{time_field}'))
        else:
            self.group = 'day'
            trunc_queryset = cut_queryset.annotate(label=TruncDay(f'{time_field}'))
        return trunc_queryset

    def _get_split_series_from_queryset(self, queryset, time_field, split_field, sum_field, label, progressive=False):
        # {
        #     label: 'Low',
        #     data: [67.8],
        #     backgroundColor: '#D6E9C6' // green
        # }
        trunc_queryset = self._get_time_group_queryset(queryset, time_field)
        if sum_field:
            db_result = trunc_queryset.values(f'{split_field}', 'label').annotate(value=Sum(f'{sum_field}')).values(
                f'{split_field}', 'label', 'value',
            )
        else:
            db_result = trunc_queryset.values(f'{split_field}', 'label').annotate(value=Count('id')).values(
                f'{split_field}', 'label', 'value',
            )

        results_set = {}
        for item in db_result:
            v = int(item['value'])
            lb = formatted_label(item['label'], self.group)
            split_name = item[f'{split_field}']
            if split_name not in results_set:
                results_set[split_name] = {}
            results_set[split_name][str(lb)] = v
            if v > self.max_value:
                self.max_value = v
        split_series = []
        for key, value in results_set.items():
            series = self._get_series(results_set[key], key, progressive)
            split_series.append(series)
        return split_series

    def _get_series_from_queryset(self, queryset, time_field, label, progressive=False):

        trunc_queryset = self._get_time_group_queryset(queryset, time_field)
        db_result = trunc_queryset.values('label').annotate(value=Count('id')).values('label', 'value')

        result = {}
        for item in db_result:
            v = int(item['value'])
            lb = formatted_label(item['label'], self.group)
            result[str(lb)] = v
            if v > self.max_value:
                self.max_value = v
        series = self._get_series(result, label, progressive)
        return [series]

    def append_by_sql(self, sql, label):
        with connection.cursor() as cursor:
            cursor.execute(sql, [self.date_from])
            series = self._get_series_from_cursor(cursor, label=label)
            self.data_sets.append(series)

    def append_by_queryset(self, queryset, time_field, label, split_field=None, sum_field=None):
        if split_field:
            self.data_sets = self._get_split_series_from_queryset(queryset, time_field, split_field, sum_field, label)
            # self.options['scales'] = {
            #     'xAxes': [{'stacked': 'true'}],
            # }
        else:
            self.data_sets = self._get_series_from_queryset(queryset, time_field, label)

    def get_chart_data(self):
        ticks = {
            'suggestedMin': 0,
        }
        if self.max_value > 0:
            ticks['stepSize'] = math.ceil(self.max_value / self.y_axes_steps)
        else:
            ticks['stepSize'] = 10
        if 'scales' not in self.options:
            self.options['scales'] = {}
        self.options['scales']['yAxes'] = [{'ticks': ticks}]
        return {
            'type': self.chart_type,
            'data': {
                'labels': self.labels,
                'datasets': self.data_sets,
            },
            'options': self.options,
        }
