# -*- coding: utf-8 -*-
"""kanun.retrieval.olcum — sıra metrikleri ve önceden çıkarılmış adaylar üzerinde rerank kuralı."""
import json

import pytest

from kanun.retrieval.olcum import gold_sorgular, metrikler, rerank_uygula, sira


def test_sira_ilk_k():
    assert sira(["a", "b", "c"], "b") == 2
    assert sira(["a", "b", "c"], "c", k=2) == 0
    assert sira([], "a") == 0


def test_metrikler():
    m = metrikler([1, 2, 0, 11])
    assert m["N"] == 4
    assert m["R@1"] == 0.25 and m["R@5"] == 0.5 and m["R@10"] == 0.5
    assert m["MRR"] == pytest.approx((1 + 0.5) / 4)      # 11. sıra MRR@10'a girmez


def test_metrikler_bos():
    assert metrikler([])["N"] == 0


def test_rerank_uygula_yalniz_bas_kismi_ve_kararli():
    assert rerank_uygula(["a", "b", "c", "d"], [0.1, 0.9, 0.5], 3) == ["b", "c", "a", "d"]
    assert rerank_uygula(["a", "b", "c"], [0.0, 0.0, 0.0], 3) == ["a", "b", "c"]


def test_gold_sorgular_mulga_ve_yok_atlanir(tmp_path):
    korpus = tmp_path / "k.jsonl"
    korpus.write_text("\n".join(json.dumps({"metadata": {"kanun_no": k, "madde_no": m, "yurutluk": y}})
                                for k, m, y in [("1", "1", "yürürlükte"), ("1", "2", "mülga")]),
                      encoding="utf-8")
    gold = tmp_path / "g.jsonl"
    gold.write_text("\n".join(json.dumps({"ilgi": f"s{i}", "kanun_no": k, "madde_no": m})
                              for i, (k, m) in enumerate([("1", "1"), ("1", "2"), ("9", "9")] * 3)),
                    encoding="utf-8")
    cikti = gold_sorgular(10, korpus_yol=str(korpus), gold_yol=str(gold))
    assert len(cikti) == 3 and all(h == ("1", "1") for _, h in cikti)
    assert gold_sorgular(10, korpus_yol=str(korpus), gold_yol=str(gold)) == cikti   # deterministik
