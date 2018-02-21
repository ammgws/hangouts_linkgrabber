from hypothesis import given
from hypothesis.strategies import datetimes

from hangouts_linkgrabber.linkgrabber import create_search_args


@given(datetimes(), datetimes())
def test_handles_reversed_search_args(datetime_a, datetime_b):
    # need to rewrite this to use time rather than datetime, then won't need this kludge:
    datetime_b = datetime_b.replace(year=datetime_a.year, month=datetime_a.month, day=datetime_a.day)
    timestamp_a, timestamp_b = create_search_args(datetime_a, datetime_b)
    assert timestamp_a <= timestamp_b
