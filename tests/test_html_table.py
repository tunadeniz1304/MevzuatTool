from mevzuat_tool.html_table import parse_tables, _table_to_markdown, _is_apendiks


def test_table_to_markdown_pipe_format():
    html = (
        "<table><tr><td>18.000 TL kadar</td><td>%15</td></tr>"
        "<tr><td>40.000 TL fazlası</td><td>%20</td></tr></table>"
    )
    md = _table_to_markdown(html)
    assert "| 18.000 TL kadar | %15 |" in md
    assert "| 40.000 TL fazlası | %20 |" in md
    # markdown tablo ayraç satırı (header separator) içerir
    assert "---" in md


def test_unescapes_entities_and_nbsp():
    html = "<table><tr><td>a&nbsp;b</td><td>&quot;x&quot;</td></tr><tr><td>c</td><td>d</td></tr></table>"
    md = _table_to_markdown(html)
    assert "a b" in md          # &nbsp; -> boşluk
    assert '"x"' in md          # &quot; -> "


def test_is_apendiks_blacklist():
    apendiks = "<table><tr><td>Değiştiren Kanunun No</td><td>Yürürlüğe Giriş Tarihi</td></tr></table>"
    icerik = "<table><tr><td>18.000 TL</td><td>%15</td></tr></table>"
    assert _is_apendiks(apendiks) is True
    assert _is_apendiks(icerik) is False


def test_parse_tables_skips_apendiks_keeps_content():
    html = (
        "<p><span>Madde 103 - (1) Tarife:</span></p>"
        "<table><tr><td>18.000 TL</td><td>%15</td></tr><tr><td>40.000 TL</td><td>%20</td></tr></table>"
        "<p><span>Madde 999 - değişiklik cetveli:</span></p>"
        "<table><tr><td>Değiştiren Kanunun No</td><td>Yürürlüğe Giriş Tarihi</td></tr>"
        "<tr><td>5479</td><td>2006</td></tr></table>"
    )
    result = parse_tables(html)
    assert "103" in result               # içerik tablosu tutuldu
    assert len(result["103"]) == 1
    assert "%15" in result["103"][0]
    assert "999" not in result           # apendiks tablosu atlandı


def test_empty_html_returns_empty():
    assert parse_tables("") == {}
