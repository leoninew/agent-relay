from concurrent.futures import ThreadPoolExecutor

import pytest
from tsidpy import TSID

from conflua.domain.identifiers import TsidSource, is_tsid, require_tsid


def test_generate_offline_role_seed_batch() -> None:
    source = TsidSource(node=1023)
    batch = [source.next() for _ in range(3)]
    assert batch == sorted(set(batch))
    assert all(is_tsid(value) and TSID.from_string(value).number >> 22 > 0 for value in batch)
    assert all((TSID.from_string(value).number >> 12) & 1023 == 1023 for value in batch)
    print("Role seed TSIDs:", *batch)


def test_canonical_tsid_vectors_cover_the_sqlite_schema_range() -> None:
    vectors = {"0000000000000": 0, "0C04Q2BR40003": 432511671823499267, "7ZZZZZZZZZZZZ": 2**63 - 1}
    for encoded, number in vectors.items():
        assert require_tsid(encoded) == encoded
        assert str(TSID(number)) == encoded


def test_tsid_source_shares_counter_across_threads_and_separates_nodes() -> None:
    primary = TsidSource()
    secondary = TsidSource(node=1023)
    with ThreadPoolExecutor(max_workers=4) as workers:
        generated = set(workers.map(lambda _: primary.next(), range(512)))
    assert len(generated) == 512
    assert all(
        is_tsid(item) and (TSID.from_string(item).number >> 12) & 1023 == 0 for item in generated
    )
    other = secondary.next()
    assert is_tsid(other) and (TSID.from_string(other).number >> 12) & 1023 == 1023


@pytest.mark.parametrize(
    "value",
    ["8000000000000", "FZZZZZZZZZZZZ", "000000000000O", "000000000000a", "000000000000\n"],
)
def test_tsid_rejects_overflow_and_noncanonical_encodings(value: str) -> None:
    assert not is_tsid(value)
    with pytest.raises(ValueError):
        require_tsid(value)
