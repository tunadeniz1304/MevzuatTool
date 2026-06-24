"""serialize_tree (scripts/eval_corpus.py) bölüm/kısım GERÇEK başlığını korumalı.

Bug: serialize_tree level düğümünde n.title (sadece no, 'ÜÇÜNCÜ BÖLÜM') alıyor, başlığı içeren
n.madde_baslik ('ÜÇÜNCÜ BÖLÜM - Haklar ve Yükümlülükler') atılıyordu → bolum_baslik no-tekrarı
oluyordu. Uçtan uca test: serialize_tree çıktısı → parse_tree → madde.bolum_baslik gerçek başlık.
"""
import importlib.util
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from mevzuat_tool.fetch import TreeNode
from mevzuat_tool.tree import parse_tree

_spec = importlib.util.spec_from_file_location(
    "ec", str(pathlib.Path(__file__).resolve().parent.parent / "scripts" / "eval_corpus.py"))
_ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ec)
serialize_tree = _ec.serialize_tree


def _bolum_node():
    # Bedesten formatı: title = sadece no, madde_baslik = 'NO - BAŞLIK'.
    madde = TreeNode(madde_no="11", madde_id="1643063",
                     title=None, madde_baslik="Madde No: 11 - İlgili kişinin hakları")
    return TreeNode(madde_no=None, madde_id="1643056",
                    title="ÜÇÜNCÜ BÖLÜM",
                    madde_baslik="ÜÇÜNCÜ BÖLÜM - Haklar ve Yükümlülükler",
                    children=[madde])


def test_serialize_preserves_section_title():
    tree = parse_tree(serialize_tree([_bolum_node()]))
    m11 = tree.by_no["11"]
    # bolum_baslik gerçek başlığı içermeli (no-tekrarı 'ÜÇÜNCÜ BÖLÜM' DEĞİL)
    assert m11.bolum_baslik == "Haklar ve Yükümlülükler"
    assert m11.bolum_no == "ÜÇÜNCÜ BÖLÜM"


def test_serialize_section_without_title_keeps_null_baslik():
    # Başlıksız bölüm (Medeni 4721 'BİRİNCİ BÖLÜM' — madde_baslik ayraçsız): null-tutma kararı →
    # bolum_baslik None (no-tekrarı 'BİRİNCİ BÖLÜM' DEĞİL). serialize_tree no-kopyalama yapmamalı.
    madde = TreeNode(madde_no="5", madde_id="500", title=None,
                     madde_baslik="Madde No: 5 - Bir madde")
    bolum = TreeNode(madde_no=None, madde_id="100", title="BİRİNCİ BÖLÜM",
                     madde_baslik="BİRİNCİ BÖLÜM", children=[madde])
    tree = parse_tree(serialize_tree([bolum]))
    m5 = tree.by_no["5"]
    assert m5.bolum_no == "BİRİNCİ BÖLÜM"
    assert m5.bolum_baslik is None              # no-tekrarı YOK


def test_serialize_baslangic_container_kept():
    # BAŞLANGIÇ kabı (Medeni 4721): no'suz tek-kelime seviye; altındaki madde köksüz kalmamalı.
    madde = TreeNode(madde_no="1", madde_id="1001", title=None,
                     madde_baslik="Madde No: 1 - Hukukun uygulanması")
    baslangic = TreeNode(madde_no=None, madde_id="1000", title="BAŞLANGIÇ",
                         madde_baslik="BAŞLANGIÇ", children=[madde])
    tree = parse_tree(serialize_tree([baslangic]))
    m1 = tree.by_no["1"]
    assert m1.hiyerarsi_yolu == "BAŞLANGIÇ › Madde 1"


def test_serialize_titleless_kitap_no_repeat_in_path():
    # Uçtan uca: ayraçsız KİTAP/KISIM/BÖLÜM → hiyerarşi_yolu'nda no-tekrarı olmaz (sadece no).
    madde = TreeNode(madde_no="8", madde_id="80", title=None,
                     madde_baslik="Madde No: 8 - Hak ehliyeti")
    bolum = TreeNode(madde_no=None, madde_id="3", title="BİRİNCİ BÖLÜM",
                     madde_baslik="BİRİNCİ BÖLÜM", children=[madde])
    kisim = TreeNode(madde_no=None, madde_id="2", title="BİRİNCİ KISIM",
                     madde_baslik="BİRİNCİ KISIM", children=[bolum])
    kitap = TreeNode(madde_no=None, madde_id="1", title="BİRİNCİ KİTAP",
                     madde_baslik="BİRİNCİ KİTAP", children=[kisim])
    tree = parse_tree(serialize_tree([kitap]))
    m8 = tree.by_no["8"]
    assert m8.kitap_no == "BİRİNCİ KİTAP" and m8.kitap_baslik is None
    assert m8.hiyerarsi_yolu == "BİRİNCİ KİTAP › BİRİNCİ KISIM › BİRİNCİ BÖLÜM › Madde 8"
