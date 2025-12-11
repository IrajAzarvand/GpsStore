from django import template
from datetime import datetime
import jdatetime

register = template.Library()

@register.filter
def persian_date(value):
    if isinstance(value, datetime):
        jd = jdatetime.datetime.fromgregorian(datetime=value)
        return jd.strftime('%Y/%m/%d')
    return value