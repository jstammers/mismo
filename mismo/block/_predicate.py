import ibis
import ibis.expr.types as ir
import ibis.expr.datatypes as dt
from typing import Union

# Define regex patterns for Ibis use

words = r"[\w']+"
not_words = r"[^\w']+"
integers = r"\d+"
not_integers = r"[^-0-9]+"
start_word = r"^([\w']+)"
two_start_words = r"^([\w']+\W+[\w']+)"
start_integer = r"^(\d+)"
alpha_numeric = r"(?=[a-zA-Z]*\d)[a-zA-Z\d]+"
not_alpha_numeric = r"[^a-zA-Z\d]+"

def whole_field_predicate(field: ir.StringValue) -> ir.ArrayValue:
    """Return the whole field as an array with a single element"""
    return ibis.array([field]).name('whole_field')

def token_field_predicate(field: ir.StringValue) -> ir.ArrayValue:
    """Returns the tokens from the string"""
    return field.re_split(not_words).name('tokens')

def first_token_predicate(field: ir.StringValue) -> ir.StringValue:
    """Returns the first token from the string"""
    return field.re_extract(start_word, 0).name('first_token')

def first_two_tokens_predicate(field: ir.StringValue) -> ir.StringValue:
    """Returns the first two tokens from the string"""
    return field.re_extract(two_start_words,0).name('first_two_tokens')

def common_integer_predicate(field: ir.StringValue) -> ir.ArrayValue:
    """Return any integers from the string"""
    # filter out empty strings from the split
    return field.re_split(not_integers).filter(lambda x: x.length() > 0).cast("array<int>").name('common_integers')

def alpha_numeric_predicate(field: ir.StringValue) -> ir.ArrayValue:
    """Return alphanumeric substrings"""
    return field.re_split(not_alpha_numeric).name('alpha_numeric')

def near_integers_predicate(field: ir.StringValue) -> ir.ArrayValue:
    """Return integers N-1, N, and N+1 for each integer N in the field"""
    return (common_integer_predicate(field)
                .map(lambda i: ibis.array([i - 1, i, i + 1]))
                .flatten().unique().sort()
                .name('near_integers'))

def hundred_integer_predicate(field: ir.StringValue) -> ir.ArrayValue:
    """Return the rounded down integers to the nearest hundred"""
    return common_integer_predicate(field).map(lambda i: (100 * (i / 100).round()).cast("int")).name('hundred_integers')

def hundred_integers_odd_predicate(field: ir.StringValue) -> ir.ArrayValue:
    """Return integers rounded to the nearest hundred with odd/even parity"""
    return common_integer_predicate(field).map(lambda i: ((100 * (i / 100).round()) + i % 2).cast("int")).name('hundred_integers_odd')

def first_integer_predicate(field: ir.StringValue) -> ir.StringValue:
    """Return the first integer at the start of a string"""
    return field.re_extract(start_integer, 0).cast("int").name('first_integer')

def ngrams_tokens(field: ir.ArrayValue, n: int) -> ir.ArrayValue:
    """Generate n-grams from tokens"""
    return field.window(rows=n).map(lambda tokens: ' '.join(tokens)).name(f'{n}_grams')

def common_two_tokens(field: ir.StringValue) -> ir.ArrayValue:
    """Return 2-grams from the string"""
    tokens = field.split()
    return ngrams_tokens(tokens, 2)

def common_three_tokens(field: ir.StringValue) -> ir.ArrayValue:
    """Return 3-grams from the string"""
    tokens = field.split()
    return ngrams_tokens(tokens, 3)

def fingerprint(field: ir.StringValue) -> ir.StringValue:
    """Return a fingerprint of the string by sorting its tokens"""
    tokens = field.split()
    return tokens.sort().join('').name('fingerprint')

def one_gram_fingerprint(field: ir.StringValue) -> ir.StringValue:
    """Return a fingerprint of the string by sorting its characters"""
    characters = field.replace(" ", "").split()
    return characters.sort().join('').name('one_gram_fingerprint')

def two_gram_fingerprint(field: ir.StringValue) -> ir.StringValue:
    """Return a fingerprint using 2-grams"""
    if field.length() > 1:
        characters = field.replace(" ", "").split()
        return unique_ngrams(characters, 2).sort().join('').name('two_gram_fingerprint')
    else:
        return ibis.null().cast(dt.string).name('two_gram_fingerprint')

def common_four_gram(field: ir.StringValue) -> ir.ArrayValue:
    """Return 4-grams from the string"""
    characters = field.replace(" ", "").split()
    return unique_ngrams(characters, 4).name('four_grams')

def common_six_gram(field: ir.StringValue) -> ir.ArrayValue:
    """Return 6-grams from the string"""
    characters = field.replace(" ", "").split()
    return unique_ngrams(characters, 6).name('six_grams')

def same_three_char_start_predicate(field: ir.StringValue) -> ir.StringValue:
    """Return the first three characters"""
    return field.substr(0, 3).name('first_three_chars')

def same_five_char_start_predicate(field: ir.StringValue) -> ir.StringValue:
    """Return the first five characters"""
    return field.substr(0, 5).name('first_five_chars')

def same_seven_char_start_predicate(field: ir.StringValue) -> ir.StringValue:
    """Return the first seven characters"""
    return field.substr(0, 7).name('first_seven_chars')

def suffix_array(field: ir.StringValue) -> ir.ArrayValue:
    """Return suffixes of the field with a minimum length"""
    n = field.length() - 4
    return field.map(lambda f: [f[i:] for i in range(0, n)]).name('suffix_array') if n > 0 else ibis.null().cast(dt.string).name('suffix_array')

def sorted_acronym(field: ir.StringValue) -> ir.StringValue:
    """Return a sorted acronym of the field"""
    return field.split().map(lambda x: x[0]).sort().join('').name('sorted_acronym')

def double_metaphone(field: ir.StringValue) -> ir.ArrayValue:
    """Return double metaphone representation of the field"""
    # This function requires external logic or a UDF, as Ibis does not directly support metaphone
    return doublemetaphone_udf(field)

def metaphone_token(field: ir.StringValue) -> ir.ArrayValue:
    """Return double metaphone for each token"""
    tokens = field.split()
    return tokens.map(lambda token: doublemetaphone_udf(token)).flatten().name('metaphone_tokens')

def whole_set_predicate(field_set: ir.ArrayValue) -> ir.ArrayValue:
    """Return the whole set as an array"""
    return field_set.as_array()

def common_set_element_predicate(field_set: ir.ArrayValue) -> ir.ArrayValue:
    """Return set as individual elements"""
    return field_set.distinct().name('common_set_elements')

def common_two_elements_predicate(field: ir.ArrayValue) -> ir.ArrayValue:
    """Return 2-grams of elements from the set"""
    return ngrams_tokens(field.sort(), 2).name('common_two_elements')

def common_three_elements_predicate(field: ir.ArrayValue) -> ir.ArrayValue:
    """Return 3-grams of elements from the set"""
    return ngrams_tokens(field.sort(), 3).name('common_three_elements')

def last_set_element_predicate(field_set: ir.ArrayValue) -> ir.StringValue:
    """Return the last element of the set"""
    return field_set.max().name('last_set_element')

def first_set_element_predicate(field_set: ir.ArrayValue) -> ir.StringValue:
    """Return the first element of the set"""
    return field_set.min().name('first_set_element')

def magnitude_of_cardinality(field_set: ir.ArrayValue) -> ir.IntegerValue:
    """Return the order of magnitude of the set cardinality"""
    return order_of_magnitude(field_set.count())

def lat_long_grid_predicate(field: ir.ArrayValue, digits: int = 1) -> ir.ArrayValue:
    """Return grid coordinates at the nearest base value"""
    if field.count() > 0:
        return field.map(lambda dim: round(dim, digits)).as_array().name('lat_long_grid')
    else:
        return ibis.null().cast(dt.string).name('lat_long_grid')

def order_of_magnitude(field: ir.NumericValue) -> ir.StringValue:
    """Return the order of magnitude of a given numeric field."""
    is_positive = field > 0
    log_value = field.log10().floor()
    result = log_value.round().cast(dt.int64).cast(dt.string)
    return result.ifelse(is_positive, ibis.literal('')).name('order_of_magnitude')

def round_to_one(field: ir.FloatingValue) -> ir.StringValue:
    """Round a float field to 1 significant figure."""
    abs_field = field.abs()
    order = abs_field.log10().floor().cast(dt.int64)
    rounded = (abs_field / (10 ** order)).round() * (10 ** order)
    rounded_with_sign = rounded * field.sign()
    result = rounded_with_sign.cast(dt.int64).cast(dt.string)
    return result.name('round_to_1')