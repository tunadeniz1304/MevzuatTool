"""OLD-vs-NEW korpus diff — yapısal-sadakat fazları için regresyon kapısı (FAZ 0.1).

İki korpus.jsonl'i id-bazlı eşleştirip bir parser değişikliğinin etkisini ölçer. Hiçbir
parser modülü import ETMEZ (yalnız json) — böylece OLD/NEW kod sürümünden bağımsızdır.

Kullanım:
  python scripts/compare_corpus.py OLD.jsonl NEW.jsonl
  python scripts/compare_corpus.py OLD.jsonl NEW.jsonl --kanun 4721,6098,6102,5846,2709
  python scripts/compare_corpus.py OLD.jsonl NEW.jsonl --flips        # status-flip id listesi
  python scripts/compare_corpus.py OLD.jsonl NEW.jsonl --gate         # kritik kapı → exit 1

Üretilen metrikler (master plan faz kapılarını besler):
  1. Özet sayım: chunk sayısı, ortak/yalnız-OLD/yalnız-NEW id (madde ekleme/silme)
  2. Status-flip: yürürlükte<->mülga geçen maddeler (FAZ 1 kapısı)
  3. Mülga oranı: OLD vs NEW (toplam)
  4. Bent dağılımı + sahte-bent proxy'si (>30 bent / tekrarlayan a) koşusu) (FAZ 2 kapısı)
  5. Fıkra dağılımı (FAZ 2/B1 kapısı)
  6. Etkilenen-madde: text/metadata değişen chunk; --kanun ile süzülür (FAZ 3 KRİTİK KAPISI)
  7. fikralar[-1] uzunluk dağılımı (FAZ 4 kapısı)
"""
import argparse
import io
import json
import pathlib
import statistics
import sys

# Windows konsolu (cp1254) bazı Unicode oklarını/işaretleri encode edemez → stdout'u UTF-8'e zorla.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

W = 94


def yukle(p):
    """id -> chunk dict. (Aynı id birden fazla görülürse son kazanır — beklenmez.)"""
    d = {}
    path = pathlib.Path(p)
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            d[o["id"]] = o
    return d


def _bent_sayisi(chunk):
    """Maddedeki toplam bent sayısı (tüm fıkralar, üst seviye)."""
    return sum(len(fk.get("bentler", [])) for fk in chunk["metadata"].get("fikralar", []))


def _fikra_sayisi(chunk):
    return len(chunk["metadata"].get("fikralar", []))


def _max_ardisik_bent(chunk):
    """Tek fıkrada en çok bent — sahte-bent (cetvel) proxy'si."""
    fl = chunk["metadata"].get("fikralar", [])
    return max((len(fk.get("bentler", [])) for fk in fl), default=0)


def _son_fikra_uzunluk(chunk):
    fl = chunk["metadata"].get("fikralar", [])
    return len(fl[-1].get("text", "")) if fl else 0


def _yurutluk(chunk):
    return chunk["metadata"].get("yurutluk")


def _kanun_no(chunk):
    return chunk["metadata"].get("kanun_no")


def _degisti(a, b):
    """text VEYA metadata farklı mı?"""
    return a.get("text") != b.get("text") or a.get("metadata") != b.get("metadata")


def _dagilim(vals):
    if not vals:
        return dict(n=0, ort=0.0, med=0, maks=0)
    return dict(n=len(vals), ort=statistics.mean(vals), med=statistics.median(vals),
                maks=max(vals))


def _baslik(s):
    print("=" * W)
    print(s)
    print("=" * W)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--kanun", default="", help="virgülle kanun_no listesi (etkilenen-madde süzgeci)")
    ap.add_argument("--flips", action="store_true", help="status-flip id listesini dök")
    ap.add_argument("--gate", action="store_true", help="kritik kapı ihlalinde exit 1")
    args = ap.parse_args()

    OLD = yukle(args.old)
    NEW = yukle(args.new)
    old_ids, new_ids = set(OLD), set(NEW)
    ortak = old_ids & new_ids
    yalniz_old = old_ids - new_ids
    yalniz_new = new_ids - old_ids
    kanun_suzgec = {k.strip() for k in args.kanun.split(",") if k.strip()}

    _baslik(f"KORPUS DIFF — OLD={len(OLD)} chunk  NEW={len(NEW)} chunk")
    print(f"  Ortak id: {len(ortak)}  |  Yalnız-OLD (silinen): {len(yalniz_old)}  "
          f"|  Yalnız-NEW (eklenen): {len(yalniz_new)}")
    if yalniz_old:
        print(f"    silinen örnek: {sorted(yalniz_old)[:8]}")
    if yalniz_new:
        print(f"    eklenen örnek: {sorted(yalniz_new)[:8]}")

    # 2. Status-flip (yalnız ortak id'lerde)
    flip_to_mulga, flip_to_yur = [], []
    for i in ortak:
        yo, yn = _yurutluk(OLD[i]), _yurutluk(NEW[i])
        if yo != yn:
            (flip_to_mulga if yn == "mülga" else flip_to_yur).append(i)
    print()
    _baslik("STATUS-FLIP (yürürlük değişen madde) — FAZ 1 kapısı")
    print(f"  yürürlükte → mülga : {len(flip_to_mulga)}")
    print(f"  mülga → yürürlükte : {len(flip_to_yur)}")
    if args.flips:
        print(f"    →mülga: {sorted(flip_to_mulga)[:40]}")
        print(f"    →yürürlükte: {sorted(flip_to_yur)[:40]}")

    # 3. Mülga oranı
    def mulga_oran(d):
        if not d:
            return 0.0
        return sum(1 for c in d.values() if _yurutluk(c) == "mülga") / len(d) * 100
    print()
    _baslik("MÜLGA ORANI")
    print(f"  OLD: %{mulga_oran(OLD):.2f}   NEW: %{mulga_oran(NEW):.2f}")

    # 4. Bent dağılımı + sahte-bent proxy
    old_bent = [_bent_sayisi(c) for c in OLD.values()]
    new_bent = [_bent_sayisi(c) for c in NEW.values()]
    old_sahte = sum(1 for c in OLD.values() if _max_ardisik_bent(c) > 30)
    new_sahte = sum(1 for c in NEW.values() if _max_ardisik_bent(c) > 30)
    print()
    _baslik("BENT DAĞILIMI + SAHTE-BENT PROXY (>30 bent/fıkra) — FAZ 2 kapısı")
    do, dn = _dagilim(old_bent), _dagilim(new_bent)
    print(f"  OLD bent: ort={do['ort']:.2f} med={do['med']} maks={do['maks']}  |  "
          f"NEW bent: ort={dn['ort']:.2f} med={dn['med']} maks={dn['maks']}")
    print(f"  Sahte-bent şüphesi madde (>30 bent): OLD={old_sahte}  NEW={new_sahte}")

    # 5. Fıkra dağılımı
    do = _dagilim([_fikra_sayisi(c) for c in OLD.values()])
    dn = _dagilim([_fikra_sayisi(c) for c in NEW.values()])
    print()
    _baslik("FIKRA DAĞILIMI — FAZ 2/B1 kapısı")
    print(f"  OLD fıkra: ort={do['ort']:.2f} med={do['med']} maks={do['maks']}  |  "
          f"NEW fıkra: ort={dn['ort']:.2f} med={dn['med']} maks={dn['maks']}")

    # 6. Etkilenen-madde (ortak id'lerde text/metadata farkı)
    etkilenen = [i for i in ortak if _degisti(OLD[i], NEW[i])]
    print()
    _baslik("ETKİLENEN MADDE (text/metadata değişti) — FAZ 3 KRİTİK KAPISI")
    print(f"  Toplam etkilenen: {len(etkilenen)} / {len(ortak)} ortak")
    kanun_ihlali = 0
    if kanun_suzgec:
        suzulen = [i for i in etkilenen if _kanun_no(NEW[i]) in kanun_suzgec]
        kanun_ihlali = len(suzulen)
        print(f"  --kanun {sorted(kanun_suzgec)} → etkilenen: {kanun_ihlali} "
              f"(KRİTİK KAPI: 0 olmalı)")
        if suzulen:
            print(f"    İHLAL örnek: {sorted(suzulen)[:20]}")

    # 7. fikralar[-1] uzunluk dağılımı
    do = _dagilim([_son_fikra_uzunluk(c) for c in OLD.values()])
    dn = _dagilim([_son_fikra_uzunluk(c) for c in NEW.values()])
    print()
    _baslik("SON-FIKRA (fikralar[-1]) UZUNLUK — FAZ 4 kapısı")
    print(f"  OLD: ort={do['ort']:.0f} med={do['med']} maks={do['maks']}  |  "
          f"NEW: ort={dn['ort']:.0f} med={dn['med']} maks={dn['maks']}")

    print()
    _baslik("ÖZET")
    print(f"  Etkilenen madde: {len(etkilenen)}  |  Status-flip: "
          f"{len(flip_to_mulga) + len(flip_to_yur)}  |  "
          f"Eklenen/Silinen: +{len(yalniz_new)}/-{len(yalniz_old)}")

    if args.gate:
        ihlal = []
        if kanun_suzgec and kanun_ihlali > 0:
            ihlal.append(f"korumalı kanunlarda {kanun_ihlali} madde etkilendi")
        if ihlal:
            print(f"\n  ❌ KAPI İHLALİ: {'; '.join(ihlal)}")
            sys.exit(1)
        print("\n  ✅ Kapı geçildi")


if __name__ == "__main__":
    main()
