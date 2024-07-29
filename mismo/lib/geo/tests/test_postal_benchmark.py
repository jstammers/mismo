from __future__ import annotations

from pathlib import Path

import ibis
from ibis import _
import ibis.expr.types as ir
import pytest

from mismo.lib.geo import postal_parse_address
from mismo.lib.geo._postal import _ADDRESS_SCHEMA

try:
    from postal.parser import parse_address as _parse_address
except ImportError:
    # Need to make it so that pytest can at least collect the tests on CI on windows
    # (or wherever postal is not available).
    # Of course, actually running the tests will explode things.
    pass

_NOOP_ADDRESS = {
    "street1": None,
    "street2": None,
    "postal_code": None,
    "city": None,
    "state": None,
    "country": None,
}

udf = ibis.udf.scalar.python(signature=((str,), _ADDRESS_SCHEMA))


@udf
def noop(address_string: str | None) -> dict:
    return _NOOP_ADDRESS


@udf
def python_only(address_string: str | None) -> dict:
    result: dict[str, str | None] = {
        "house_number": None,
        "road": None,
        "unit": None,
        "city": None,
        "state": None,
        "postcode": None,
        "country": None,
    }

    # Fake 'parse_address' function that emits just one field ("street")
    # containing the whole address.
    parsed_fields = (("street", address_string),)
    for value, label in parsed_fields:
        current = result.get(label, False)
        if current is not False:
            result[label] = value if current is None else f"{current} {value}"

    house_number = result.pop("house_number")
    if house_number is not None:
        road = result["road"]
        if road is None:
            result["road"] = house_number
        else:
            result["road"] = f"{house_number} {road}"

    result["street1"] = result.pop("road")
    result["street2"] = result.pop("unit")
    result["postal_code"] = result.pop("postcode")

    return result


@udf
def postal_only(address_string: str | None) -> dict:
    _parse_address(address_string or "")
    return _NOOP_ADDRESS


@udf
def complete(address_string: str | None) -> dict | None:
    if address_string is None:
        return None
    # Initially, the keys match the names of pypostal fields we need.
    # Later, this dict is modified to match the shape of an `ADDRESS_SCHEMA`.
    result: dict[str, str | None] = {
        "house_number": None,
        "road": None,
        "unit": None,
        "city": None,
        "state": None,
        "postcode": None,
        "country": None,
    }

    parsed_fields = _parse_address(address_string)
    for value, label in parsed_fields:
        # Pypostal returns more fields than the ones we actually need.
        # Here `False` is used as a placeholder under the assumption that
        # such value is never returned by pypostal a field value.
        current = result.get(label, False)

        # Keep only the fields declared when `result` is initialized.
        # Pypostal fields can be repeated, in such case we concat their values.
        if current is not False:
            result[label] = value if current is None else f"{current} {value}"

    # Hack to prepend "house_number" to "road"
    house_number = result.pop("house_number")
    if house_number is not None:
        road = result["road"]
        if road is None:
            result["road"] = house_number
        else:
            result["road"] = f"{house_number} {road}"

    # Modify `result` in-place to match the shape of an `ADDRESS_SCHEMA`.
    result["street1"] = result.pop("road")
    result["street2"] = result.pop("unit")
    result["postal_code"] = result.pop("postcode")

    return result


def download_test_data() -> ir.Table:
    # download test data from https://github.com/NickCrews/apoc-data/releases/tag/20240717-111158
    URL_TEMPLATE = "https://github.com/NickCrews/apoc-data/releases/download/20240717-111158/income_{year}.csv"
    conn = ibis.duckdb.connect()
    sub_tables = [
        conn.read_csv(
            (URL_TEMPLATE.format(year=year) for year in range(2011, 2024)),
            all_varchar=True,
        )
    ]
    t = ibis.union(*sub_tables)
    t = t.select(
        full_address=_.Address
        + ", "
        + _.City
        + ", "
        + _.State
        + ", "
        + _.Zip
        + ", "
        + _.Country
    )
    return t


@pytest.fixture
def data(backend: ibis.BaseBackend) -> ir.Table:
    pq = Path(__file__).parent / "apoc_addresses_1M.parquet"
    if not pq.exists():
        download_test_data().to_parquet(pq)
    t = backend.read_parquet(pq)
    t = t.cache()  # ensure in memory, we don't want to benchmark disk IO
    return t


@pytest.mark.parametrize(
    "fn",
    [
        noop,
        python_only,
        postal_only,
        complete,
        postal_parse_address,
    ],
)
@pytest.mark.parametrize(
    "nrows",
    [
        pytest.param(1_000, id="1k"),
        pytest.param(10_000, id="10k"),
        pytest.param(100_000, id="100k"),
        pytest.param(1_000_000, id="1m"),
    ],
)
# run with eg
# just bench -k test_benchmark_parse[100k-postal_parse_address]
# just bench -k 10k mismo/lib/geo/tests/test_postal_benchmark.py
# just bench -k 100k-postal_only mismo/lib/geo/tests/test_postal_benchmark.py
def test_benchmark_parse(backend, data, nrows, fn, benchmark):
    inp = data.head(nrows).full_address

    def run():
        t = fn(inp).lift()
        # Not sure if this is needed, but being defensive:
        # If we use .cache(), then when benchmark() runs this in a loop,
        # computation will only happen the first time, and the rest of the
        # times it will just return the cached result.
        return backend.create_table("temp", t, overwrite=True)

    result = benchmark(run)
    assert len(result.execute()) == nrows
