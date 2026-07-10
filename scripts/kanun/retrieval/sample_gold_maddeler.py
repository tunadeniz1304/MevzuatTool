# -*- coding: utf-8 -*-
"""
Gold set için tabakalı (stratified) madde örnekleme.

Amaç: korpustan 200 maddeyi, gold set üretimi için ADİL ve ÇEŞİTLİ biçimde seçmek.
Bilimsel deneyde tekrarlanabilirlik şart → SABİT seed (random.seed).

Tabakalar:
  1. Kanun çeşitliliği   : bir kanun gold'u domine etmesin (kanun başına kota).
  2. Uzunluk tabakası     : kısa / orta / uzun madde dengesi.
  3. Yürürlük             : ~%90 yürürlükte + ~%10 mülga (yürürlük filtresini de test etmek için).
  4. Çok-madde kümeleri   : bazı maddeler, aynı kanundan komşularıyla birlikte işaretlenir
                            (kavramsal çok-madde soruları için subagent'ın gerçek ek-doğru
                            maddeleri GÖREBİLMESİ gerekir; uydurmasın diye).

Çıktı: data/gold/gold_maddeler.jsonl
  Her satır bir "görev" (task) — subagent'a verilecek:
  {
    "task_id": int,
    "hedef_id": "657-125",            # sorunun türetileceği ana madde
    "hedef_text": "...",
    "kanun_no": "657", "kanun_ad": "...", "madde_no": "125",
    "yurutluk": "yürürlükte" | "mülga",
    "uzunluk_tabaka": "kisa"|"orta"|"uzun",
    "komsu_maddeler": [               # aynı kanundan, kavramsal çok-madde için (subagent görecek)
        {"id":"657-124","text":"...","madde_no":"124"}, ...
    ]
  }
"""
import json
import random
import collections
import os

CORPUS = "data/kanun/korpus.jsonl"
OUT = "data/gold/gold_maddeler.jsonl"
SEED = 4721            # sabit seed → tekrarlanabilir örnekleme
N_HEDEF = 200          # toplam gold görev sayısı
MULGA_KOTA = 20        # bunların ~20'si mülga olsun
KANUN_KOTA = 6         # bir kanundan en fazla bu kadar HEDEF madde
MIN_CHAR = 200         # bundan kısa metinden soru üretilmez
KOMSU_MAX = 3          # her hedefe kaç komşu madde eklensin (çok-madde için)


def uzunluk_tabaka(n):
    if n < 400:
        return "kisa"
    if n < 1200:
        return "orta"
    return "uzun"


def main():
    random.seed(SEED)

    # 1) Korpusu kanun -> [madde kaydı] olarak yükle
    by_kanun = collections.defaultdict(list)
    kayit = {}  # id -> kayıt
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            kayit[r["id"]] = r
            by_kanun[m["kanun_no"]].append(r)

    # 2) Uygun hedef havuzu: metin yeterince uzun
    def uygun(r):
        return len(r["text"]) >= MIN_CHAR

    yururlukte, mulga = [], []
    for kn, kayitlar in by_kanun.items():
        for r in kayitlar:
            if not uygun(r):
                continue
            (yururlukte if r["metadata"]["yurutluk"] == "yürürlükte" else mulga).append(r)

    random.shuffle(yururlukte)
    random.shuffle(mulga)

    # 3) Tabakalı seçim: kanun kotası + uzunluk dengesi
    secilen = []
    kanun_sayac = collections.Counter()
    tabaka_sayac = collections.Counter()
    hedef_yururlukte = N_HEDEF - MULGA_KOTA

    def uygun_sec(havuz, limit):
        for r in havuz:
            if len(secilen) >= limit and limit == len(secilen):
                pass
            kn = r["metadata"]["kanun_no"]
            if kanun_sayac[kn] >= KANUN_KOTA:
                continue
            tab = uzunluk_tabaka(len(r["text"]))
            # uzunluk tabakalarını kabaca dengede tut (her tabakaya ~1/3)
            if tabaka_sayac[tab] >= (limit // 3) + 15:
                continue
            secilen.append((r, tab))
            kanun_sayac[kn] += 1
            tabaka_sayac[tab] += 1
            if len([1 for s in secilen if s[0]["metadata"]["yurutluk"] ==
                    ("mülga" if havuz is mulga else "yürürlükte")]) >= limit:
                break

    # yürürlükte seç
    for r in yururlukte:
        if sum(1 for s in secilen if s[0]["metadata"]["yurutluk"] == "yürürlükte") >= hedef_yururlukte:
            break
        kn = r["metadata"]["kanun_no"]
        if kanun_sayac[kn] >= KANUN_KOTA:
            continue
        tab = uzunluk_tabaka(len(r["text"]))
        if tabaka_sayac[tab] >= (hedef_yururlukte // 3) + 20:
            continue
        secilen.append((r, tab))
        kanun_sayac[kn] += 1
        tabaka_sayac[tab] += 1

    # mülga seç (kota kadar)
    m_alindi = 0
    for r in mulga:
        if m_alindi >= MULGA_KOTA:
            break
        kn = r["metadata"]["kanun_no"]
        if kanun_sayac[kn] >= KANUN_KOTA:
            continue
        secilen.append((r, uzunluk_tabaka(len(r["text"]))))
        kanun_sayac[kn] += 1
        m_alindi += 1

    # 4) Her hedefe komşu maddeler ekle (aynı kanun, madde_no yakınlığı)
    def komsu_bul(hedef):
        kn = hedef["metadata"]["kanun_no"]
        h_no = hedef["metadata"]["madde_no"]
        # sayısal madde_no'ları yakala
        adaylar = []
        for r in by_kanun[kn]:
            if r["id"] == hedef["id"]:
                continue
            if len(r["text"]) < 120:
                continue
            adaylar.append(r)
        # aynı kanundan rastgele birkaç komşu (gerçek ek-doğru madde ADAYI; subagent karar verir)
        random.shuffle(adaylar)
        return adaylar[:KOMSU_MAX]

    # 5) Görevleri yaz
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as out:
        for i, (hedef, tab) in enumerate(secilen):
            m = hedef["metadata"]
            komsular = komsu_bul(hedef)
            gorev = {
                "task_id": i,
                "hedef_id": hedef["id"],
                "hedef_text": hedef["text"],
                "kanun_no": m["kanun_no"],
                "kanun_ad": m["kanun_ad"],
                "madde_no": m["madde_no"],
                "yurutluk": m["yurutluk"],
                "uzunluk_tabaka": tab,
                "komsu_maddeler": [
                    {"id": k["id"], "madde_no": k["metadata"]["madde_no"],
                     "text": k["text"][:600]}
                    for k in komsular
                ],
            }
            out.write(json.dumps(gorev, ensure_ascii=False) + "\n")

    # 6) Özet rapor
    print(f"Toplam görev      : {len(secilen)}")
    print(f"Yürürlükte / mülga: "
          f"{sum(1 for s in secilen if s[0]['metadata']['yurutluk']=='yürürlükte')} / "
          f"{sum(1 for s in secilen if s[0]['metadata']['yurutluk']=='mülga')}")
    print(f"Uzunluk tabaka    : {dict(tabaka_sayac)}")
    print(f"Farklı kanun      : {len(set(s[0]['metadata']['kanun_no'] for s in secilen))}")
    print(f"Kanun başına max  : {kanun_sayac.most_common(3)}")
    print(f"Çıktı             : {OUT}")


if __name__ == "__main__":
    main()
