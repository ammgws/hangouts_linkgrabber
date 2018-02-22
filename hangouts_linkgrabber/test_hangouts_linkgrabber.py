#!/usr/bin/python3

import linkgrabber

import datetime
import pytest

test_data_time_validation = [
    ('0900', '1000', 1),
    ('0900', '0100', 16),
    ('1900', '0900', 14),
    ('0000', '1000', 10),
    ('1000', '0000', 14),
    ('0000', '0000', 24)
]

@pytest.mark.parametrize('a, b, expected', test_data_time_validation)
def test_create_search_arguements(a, b, expected):
    time_a = datetime.datetime.strptime(a, '%H%M')
    time_b = datetime.datetime.strptime(b, '%H%M')
    result_a, result_b = linkgrabber.create_search_args(time_a, time_b)
    found_result = result_b - result_a
    expected_result = expected * 3600
    assert found_result == expected_result
