from dataclasses import dataclass

from mevzuat_tool.ids import slug, assign_ids


@dataclass
class _Stub:
    no: str
    id: str = ""


def test_slug_normalizes_turkish_and_suffix():
    assert slug("84") == "84"
    assert slug("Geçici 1") == "Gecici1"
    assert slug("Ek 2") == "Ek2"
    assert slug("Mükerrer 257") == "Mukerrer257"
    assert slug("123/A") == "123A"


def test_assign_basic_id():
    ms = [_Stub("84"), _Stub("85")]
    assign_ids(ms, "193")
    assert ms[0].id == "193-84"
    assert ms[1].id == "193-85"


def test_duplicate_no_gets_sequence_suffix():
    ms = [_Stub("Geçici 1"), _Stub("Geçici 1")]
    assign_ids(ms, "193")
    assert ms[0].id == "193-Gecici1-1"
    assert ms[1].id == "193-Gecici1-2"


def test_all_ids_unique():
    ms = [_Stub("84"), _Stub("Geçici 1"), _Stub("Geçici 1"), _Stub("123/A")]
    assign_ids(ms, "193")
    ids = [m.id for m in ms]
    assert len(ids) == len(set(ids))
