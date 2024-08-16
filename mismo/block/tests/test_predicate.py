import ibis
import pytest
from mismo.block import _predicate as predicate

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", ["foo"]),
        ("foo bar", ["foo bar"]),
]
)
def test_whole_field_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.whole_field_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", ["foo"]),
        ("foo bar", ["foo", "bar"]),
        ("foo!, bar", ["foo", "bar"]),
]
)
def test_token_field_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.token_field_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", "foo"),
        ("foo bar", "foo"),
        ("foo!, bar", "foo"),
]
)
def test_first_token_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.first_token_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", ""),
        ("foo bar", "foo bar"),
        ("foo!, bar", "foo!, bar"),
]
)
def test_first_two_tokens_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.first_two_tokens_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", []),
        ("foo1 bar2", [1, 2]),
        ("foo, bar11  22", [11, 22]),
        ("-100", [-100]),
]
)
def test_common_integer_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.common_integer_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", ["foo"]),
        ("foo1 bar2", ["foo1", "bar2"]),
        ("foo, bar11  22", ["foo", "bar11", "22"]),
]
)
def test_alpha_numeric_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.alpha_numeric_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", []),
        ("1", [0, 1, 2]),
        ("foo1 bar2", [0, 1, 2, 3])
]
)
def test_near_integers_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.near_integers_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("foo", []),
        ("1", [0]),
        ("101 149, 150", [100, 100, 200]),
        ("-101", [-100])
]
)
def test_hundred_integer_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.hundred_integer_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("250", [300]),
        ("251", [301]),
        ("199 and 301", [201, 301]),
        ("102 and 3050", [100, 3100]),
        ("0030 and 0999", [0, 1001]),
        ("foo bar", []),
        ("123456789", [123456801]),
        ("-250 and -751", [-300, -801]),
    ]
)
def test_hundred_integers_odd_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.hundred_integers_odd_predicate(input).execute()
    assert expected == result

@pytest.mark.parametrize(
    "input, expected",
    [
        ("123", [123]),             # Simple integer
        ("abc 123 def", [123]),     # Integer within text
        ("abc -123 def", [-123]),   # Negative integer within text
        ("00123", [123]),           # Leading zeros
        ("no digits here", []),       # No integers
        ("42 and 17", [42]),        # Multiple integers, expect the first one
        ("foo 123bar", [123]),      # Integer followed by text
        ("-42", [-42]),             # Simple negative integer
        ("+42", [42]),              # Positive integer with a sign
        ("123abc456", [123]),       # Integer immediately followed by text
    ]
)
def test_first_integer_predicate(input, expected):
    input = ibis.literal(input)
    result = predicate.first_integer_predicate(input).execute()
    assert expected == result

def test_ngams_tokens_predicate(input, expected):
    result = predicate.ngrams_tokens(input).execute()
    assert expected == result

def test_common_two_tokens_predicate(input, expected):
    result = predicate.common_two_tokens(input).execute()
    assert expected == result

def test_common_three_tokens_predicate(input, expected):
    result = predicate.common_three_tokens(input).execute()
    assert expected == result

def test_fingerprint_predicate(input, expected):
    result = predicate.fingerprint(input).execute()
    assert expected == result

def test_one_gram_fingerprint_predicate(input, expected):
    result = predicate.one_gram_fingerprint(input).execute()
    assert expected == result

def test_two_gram_fingerprint_predicate(input, expected):
    result = predicate.two_gram_fingerprint(input).execute()
    assert expected == result

def test_common_four_gram_predicate(input, expected):
    result = predicate.common_four_gram(input).execute()
    assert expected == result

def test_common_six_gram_predicate(input, expected):
    result = predicate.common_six_gram(input).execute()
    assert expected == result

def test_same_three_char_start_predicate(input, expected):
    result = predicate.same_three_char_start_predicate(input).execute()
    assert expected == result

def test_same_five_char_start_predicate(input, expected):
    result = predicate.same_five_char_start_predicate(input).execute()
    assert expected == result

def test_suffix_array_predicate(input, expected):
    result = predicate.suffix_array(input).execute()
    assert expected == result

def test_sorted_acronym_predicate(input, expected):
    result = predicate.sorted_acronym(input).execute()
    assert expected == result

def test_double_metaphone_predicate(input, expected):
    result = predicate.double_metaphone(input).execute()
    assert expected == result

def test_metaphone_token_predicate(input, expected):
    result = predicate.metaphone_token(input).execute()
    assert expected == result

def test_whole_set_predicate(input, expected):
    result = predicate.whole_set_predicate(input).execute()
    assert expected == result

def test_common_set_element_predicate(input, expected):
    result = predicate.common_set_element_predicate(input).execute()
    assert expected == result

def test_common_two_elements_predicate(input, expected):
    result = predicate.common_two_elements_predicate(input).execute()
    assert expected == result

def test_common_three_elements_predicate(input, expected):
    result = predicate.common_three_elements_predicate(input).execute()
    assert expected == result

def test_last_set_element_predicate(input, expected):
    result = predicate.last_set_element_predicate(input).execute()
    assert expected == result

def test_first_set_element_predicate(input, expected):
    result = predicate.first_set_element_predicate(input).execute()
    assert expected == result

def test_magnitude_of_cardinality(input, expected):
    result = predicate.magnitude_of_cardinality(input).execute()
    assert expected == result

def test_lat_long_grid_predicate(input, expected):
    result = predicate.lat_long_grid_predicate(input).execute()
    assert expected == result

def test_order_of_magnitude(input, expected):
    result = predicate.order_of_magnitude(input).execute()
    assert expected == result

def test_round_to_one(input, expected):
    result = predicate.round_to_one(input).execute()
    assert expected == result