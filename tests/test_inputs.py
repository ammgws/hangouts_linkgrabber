from hypothesis import given
from hypothesis.strategies import times

from hangouts_linkgrabber.linkgrabber import create_search_args


@given(times(), times())
def test_handles_reversed_search_args(start_time, end_time):
    start_timestamp, end_timestamp = create_search_args(start_time, end_time)
    assert start_timestamp <= end_timestamp
