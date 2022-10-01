import datetime

from pydantic.datetime_parse import parse_duration, parse_datetime


def validate_time(time: str) -> str:
    """Parses time to timedelta and converts to HH+:MM:SS.ffff

    Args:
        time: A string on the format HH+:MM:SS.ffff

    Returns:
        A string on the format HH+:MM:SS.ffff
    """
    duration = parse_duration(time)
    days_in_hours = duration.days * 24
    minutes, seconds = divmod(duration.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{days_in_hours + hours}:{minutes}:{seconds}.{duration.microseconds}"


def validate_datetime(datetime: datetime.datetime) -> str:
    """Validate datetime and convert to string

    Args:
        datetime: datetime object

    Returns:
        A string of the datetime object
    """
    return str(parse_datetime(datetime))