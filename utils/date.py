from calendar import monthrange
from datetime import datetime, timedelta
from typing import Union

import pytz
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from pytz.tzinfo import DstTzInfo, StaticTzInfo


def timezone_with_fallback(
    timezone_string: str, fallback: str = "UTC"
) -> Union[StaticTzInfo, DstTzInfo]:
    """
    Determine if it is an hour shift or a timezone name and call the functions accordingly
    :param timezone_string: Timezone or offset. E.g. '+03:00' or 'US/Eastern'
    :return: Timezone (returns UTC if timezone_string and fallback are not suitable)
    """

    timezone = exception_handled_timezone(timezone_string)
    if not timezone:
        timezone = get_timezone_from_offset(timezone_string)
    if not timezone:
        timezone = exception_handled_timezone(fallback)
    if not timezone:
        timezone = pytz.timezone("UTC")
    return timezone


def exception_handled_timezone(timezone_string: str) -> Union[StaticTzInfo, DstTzInfo]:
    try:
        timezone = pytz.timezone(timezone_string)
    except:
        timezone = None
    return timezone


def get_timezone_from_offset(offset_str: str) -> Union[StaticTzInfo, DstTzInfo, None]:
    try:
        try:
            hour_shift = offset_str.split(":")[0]
            sign = "+" if hour_shift[0] == "-" else "-"
            hour = hour_shift.replace("+", "").replace("-", "")
            shift = int(hour)
            timezone_filter = "GMT" + sign + str(shift)
        except:
            timezone_filter = (
                offset_str  # In case timezone name is given instead of offset
            )

        user_timezones = list(
            filter(lambda x: timezone_filter in x, pytz.all_timezones)
        )
        if len(user_timezones) < 1:
            return None
        user_timezone = user_timezones[0]
        user_tz = pytz.timezone(user_timezone)
        return user_tz
    except:
        return None


def get_user_day_range_for_start_hour(
    user_tz: Union[StaticTzInfo, DstTzInfo], start_hour: int
) -> (datetime, datetime):
    """
    Gets start and end time for current day according to timezone and specified day start hour
    :param user_tz: Timezone of the user. E.g. 'US/Eastern'
    """
    now = timezone.now().astimezone(user_tz)
    drop_one_day = int(
        now.hour < start_hour
    )  # When start_hour is 10 and the hour is 01:00 the start day should be calculated from previous day

    current_day_start = user_tz.localize(
        datetime(now.year, now.month, now.day - drop_one_day, start_hour, 0, 0)
    )
    next_day_start = current_day_start + timedelta(days=1)

    return current_day_start, next_day_start


def get_user_week_range(
    user_timezone: Union[StaticTzInfo, DstTzInfo],
) -> (datetime, datetime):
    now = timezone.now().astimezone(user_timezone)

    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return start_of_week, end_of_week


def get_user_month_range(
    user_timezone: Union[StaticTzInfo, DstTzInfo],
) -> (datetime, datetime):
    now = timezone.now().astimezone(user_timezone)
    year = now.year
    month = now.month

    _, last_day = monthrange(year, month)

    first_time_of_month = user_timezone.localize(datetime(year, month, 1, 0, 0))
    last_time_of_month = user_timezone.localize(datetime(year, month, last_day, 23, 59))

    return first_time_of_month, last_time_of_month


def get_user_year_range(
    user_timezone: Union[StaticTzInfo, DstTzInfo],
) -> (datetime, datetime):
    now = timezone.now().astimezone(user_timezone)
    year = now.year

    first_time_of_year = user_timezone.localize(datetime(year, 1, 1, 0, 0))
    last_time_of_year = (
        first_time_of_year + relativedelta(years=1) - relativedelta(microseconds=1)
    )

    return first_time_of_year, last_time_of_year


def shift_date_with_timezone(
    timezone: Union[StaticTzInfo, DstTzInfo], date: datetime, reversed: bool = False
) -> datetime:
    offset = timezone.utcoffset(date)
    return date + offset if not reversed else date - offset
