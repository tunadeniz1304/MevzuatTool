# -*- coding: utf-8 -*-
"""Korpus SAĞLIK KARNESİ — korpus.jsonl'in kendi içinde yapısal sağlık taraması.

Ağ YOK, ground-truth YOK — sadece mevcut korpusun iç tutarlılığı.
Plandaki "zehir" tanımlarını (master-plan) doğrudan sayar:
  1. Boş / çok kısa bent (yapı bozulması: len(text)<=3 alt-bent)
  2. Harf-sırası kırılması (a) b) d) — c) atlanmış  VEYA  tekrarlı harf a)..a))
  3. Bleed şüphesi (fıkra sonunda büyük-harfle başlık gibi kuyruk)
  4. Yürürlük dağılımı + şüpheli (boş-text mülga, tek-kelime text)
  5. Genel: fıkra/bent istatistiği, text uzunluk sağlığı

Çıktı: konsol raporu + data/gold/saglik_supheliler.jsonl (elle inceleme için).
"""
import json
import re
import collections

CORPUS = "data/corpus/korpus.jsonl"
OUT_SUP = "data/gold/saglik_supheliler.jsonl"

_HARF_ISARET = re.compile(r"^([a-zçğıöşü])\)")
_BUYUK_BASLIK_KUYRUK = re.compile(r"[.!?]\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[a-zçğıöşü]+){0,3})\s*$")


def bent_bos_mu(b):
    """Bir bent yapı-bozuk mu: text çok kısa (işaret var ama içerik yok)."""
    t = (b.get("text") or "").strip()
    # işaret sonrası içerik: "a)" veya "a) " → boş
    govde = re.sub(r"^[a-zçğıöşü0-9]{1,3}[\).]\s*", "", t)
    return len(govde) <= 2


def harf_sirasi_kirik(bentler):
    """Harf-bent sırası kırık mı: eksik harf VEYA tekrar."""
    harfler = []
    for b in bentler:
        m = _HARF_ISARET.match((b.get("text") or "").strip())
        if m:
            harfler.append(m.group(1))
    if len(harfler) < 2:
        return False, None
    # tekrar var mı?
    if len(harfler) != len(set(harfler)):
        tekrar = [h for h, c in collections.Counter(harfler).items() if c > 1]
        return True, f"tekrar:{tekrar}"
    # Türk alfabesi sırası
    alfabe = "abcçdefgğhıijklmnoöprsştuüvyz"
    idx = [alfabe.index(h) for h in harfler if h in alfabe]
    # ilk harften itibaren ardışık mı? (büyük atlama = şüpheli)
    for i in range(1, len(idx)):
        if idx[i] - idx[i-1] > 2:  # 2'den fazla atlama (ı/i toleransı)
            return True, f"atlama:{harfler}"
    return False, None


def main():
    n = 0
    yur = collections.Counter()
    tip = collections.Counter()
    bos_bent_madde = []
    harf_kirik_madde = []
    bleed_suphe = []
    mulga_bos_text = []
    tek_kelime = 0
    toplam_fikra = 0
    toplam_bent = 0
    fikrasiz = 0
    uzunluk = []

    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            m = r["metadata"]
            yur[m["yurutluk"]] += 1
            tip[m.get("madde_tipi")] += 1
            text = r.get("text") or ""
            uzunluk.append(len(text))

            if len(text.split()) <= 1:
                tek_kelime += 1
            # mülga ama text dolu değil (sadece künye kalıntısı olabilir)
            if m["yurutluk"] == "mülga" and len(text.strip()) < 15:
                mulga_bos_text.append(r["id"])

            fikralar = m.get("fikralar") or []
            if not fikralar:
                fikrasiz += 1
            toplam_fikra += len(fikralar)

            for fik in fikralar:
                bentler = fik.get("bentler") or []
                toplam_bent += len(bentler)
                # boş bent
                bos = [b for b in bentler if bent_bos_mu(b)]
                if bos:
                    bos_bent_madde.append((r["id"], len(bos), len(bentler)))
                # harf sırası
                kirik, sebep = harf_sirasi_kirik(bentler)
                if kirik:
                    harf_kirik_madde.append((r["id"], sebep))
                # bleed: fıkra text sonunda başlık-gibi kuyruk
                ft = fik.get("text") or ""
                mb = _BUYUK_BASLIK_KUYRUK.search(ft)
                if mb and len(ft) > 60:
                    bleed_suphe.append((r["id"], mb.group(1)))

    uzunluk.sort()
    nn = len(uzunluk)

    print("=" * 68)
    print(f"KORPUS SAĞLIK KARNESİ — {n} chunk")
    print("=" * 68)
    print(f"Yürürlük     : {dict(yur)}")
    print(f"Madde tipi   : {dict(tip)}")
    print(f"Text uzunluk : medyan {uzunluk[nn//2]} | p10 {uzunluk[nn//10]} | p90 {uzunluk[nn*9//10]}")
    print(f"Fıkra toplam : {toplam_fikra} | Bent toplam: {toplam_bent} | Fıkrasız madde: {fikrasiz}")
    print("-" * 68)
    print("YAPI BOZULMASI (plandaki 'gerçek zehir' kriterleri):")
    print(f"  Boş/çok-kısa bent içeren madde : {len(bos_bent_madde)}")
    print(f"  Harf-sırası kırık madde        : {len(harf_kirik_madde)}")
    print(f"  Bleed şüphesi (başlık kuyruğu)  : {len(bleed_suphe)}")
    print("-" * 68)
    print("YÜRÜRLÜK/TEXT ŞÜPHE:")
    print(f"  Tek-kelimelik text chunk        : {tek_kelime}")
    print(f"  Mülga ama text<15 krk (künye?)  : {len(mulga_bos_text)}")
    print("=" * 68)

    # İlk örnekler
    if bos_bent_madde:
        print("\nBoş-bent örnekleri (id, boş-sayı/toplam-bent):")
        for x in sorted(bos_bent_madde, key=lambda t: -t[1])[:8]:
            print(f"  {x[0]}: {x[1]}/{x[2]}")
    if harf_kirik_madde:
        print("\nHarf-sırası-kırık örnekleri (id, sebep):")
        for x in harf_kirik_madde[:8]:
            print(f"  {x[0]}: {x[1]}")
    if bleed_suphe:
        print("\nBleed-şüphe örnekleri (id, kuyruk):")
        for x in bleed_suphe[:8]:
            print(f"  {x[0]}: ...{x[1]}")

    # Şüphelileri diske yaz (elle inceleme)
    with open(OUT_SUP, "w", encoding="utf-8") as out:
        for tid, bsay, btop in bos_bent_madde:
            out.write(json.dumps({"tip": "bos_bent", "id": tid, "bos": bsay, "toplam": btop}, ensure_ascii=False) + "\n")
        for tid, sebep in harf_kirik_madde:
            out.write(json.dumps({"tip": "harf_kirik", "id": tid, "sebep": sebep}, ensure_ascii=False) + "\n")
        for tid, kuyruk in bleed_suphe:
            out.write(json.dumps({"tip": "bleed", "id": tid, "kuyruk": kuyruk}, ensure_ascii=False) + "\n")
    print(f"\nŞüpheliler -> {OUT_SUP}")


if __name__ == "__main__":
    main()
