from mevzuat_tool.enrich import _madde_tipi


def test_madde_tipi_from_no():
    assert _madde_tipi("84") == "asil"
    assert _madde_tipi("257/A") == "asil"
    assert _madde_tipi("Geçici 84") == "gecici"
    assert _madde_tipi("Ek 2") == "ek"
    assert _madde_tipi("Mükerrer 80") == "mukerrer"
