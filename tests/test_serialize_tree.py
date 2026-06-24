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


def test_serialize_section_without_title_keeps_no():
    # Başlıksız bölüm (Medeni 4721 'BİRİNCİ BÖLÜM' — madde_baslik ayraçsız): başlık no'ya eşit/boş.
    madde = TreeNode(madde_no="5", madde_id="500", title=None,
                     madde_baslik="Madde No: 5 - Bir madde")
    bolum = TreeNode(madde_no=None, madde_id="100", title="BİRİNCİ BÖLÜM",
                     madde_baslik="BİRİNCİ BÖLÜM", children=[madde])
    tree = parse_tree(serialize_tree([bolum]))
    m5 = tree.by_no["5"]
    # ayraç yok → başlık ya no'ya eşit ya boş; no doğru olmalı
    assert m5.bolum_no == "BİRİNCİ BÖLÜM"
    assert m5.bolum_baslik in ("BİRİNCİ BÖLÜM", None, "")
