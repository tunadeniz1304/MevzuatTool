"""TEBLİĞ pipeline'ı — DENEYSEL, PARK EDİLDİ (ADR-0020, 2026-10-18). MVP'ye dahil DEĞİL.

MVP kapsamı yalnız KANUN'dur (ADR-0013). Bu paketteki kod 2026-07-10'da ölçülerek yazıldı,
sonra park edildi: OLDUĞU GİBİ kalır — silinmez, geliştirilmez. Geliştirmek MVP'yi
genişletmektir; önce `docs/decisions.md`'ye kapsam kararı yaz (ADR-0020'nin yerini alan ADR).

NE VAR:
  fetch.py      bedesten tebliğ çekici (`mevzuatTurList: ["TEBLIGLER"]`, cache `data/teblig/raw/`):
                ölçülmüş rate-limit modeli (pencere başına 9 istek + 31 sn), 3 paralel işçi,
                ağaçsız tebliğ desteği, `pageSize > 20` sessiz-hata kapısı.
                Ölçüm: docs/bedesten-rate-limit-olcumu.md
  chunker.py    `split_birimler`: tebliğ-sonu ek/cetvel kırpma → `MADDE N` birimleri; MADDE yoksa
                numaralı bölüm hiyerarşisi (roma `I-`/`1-`, ondalık `2.1.1.`, yaprak-düğüm kuralı).
                Çıktı `Birim` listesi — henüz `{id, text, metadata}` chunk'ı değil.
  scripts/teblig/yapi_olc.py   cache'teki tebliğlerin yapı ölçümü.
  tests/teblig/                53 test (ağsız; varsayılan `pytest -q` koşusunda).

NE YOK:
  tebliğ build script'i ve korpusu (`data/teblig/korpus.jsonl`), fıkra/bent ayrıştırma,
  yürürlük/mülga tespiti, metadata zenginleştirme (`metadata.mevzuat_tur` dahil), embed/index,
  retrieval ve servis entegrasyonu.

YENİDEN AÇILIRSA: ilk adımlar ADR-0020'de (kapsam kararı → cache'i kur ve yeniden ölç → build
script'i → korpus şeması + `mevzuat_tur` → ayrı Qdrant collection mı, birleşik şema mı).

Bu paket, `src/kanun/` ile **hiçbir kodu paylaşmaz** (ADR-0014). Bilinçli karar: her mevzuat türü
kendi fetch/chunker/parser'ını alır. Sebep — tebliğ, kanundan yapısal olarak farklıdır ve ortak
soyutlama (if tur=='KANUN' ... else ...) iki tarafı da bozar:

  - Tebliğlerin bir kısmında (ölçümde ~1/3) madde ağacı (`mevzuatMaddeTree`) BOŞ döner; kanun
    parser'ı ağaca dayanıyor (hiyerarşi, madde başlıkları, bleed-marker'ları).
  - Tebliğlerin çoğu `MADDE 1 –` taşır (ölçümde ~%96); kalanı numaralı bölüm (`I-`, `2.1.1.`)
    ya da düz metindir. Ek/cetvel ağırlıklı olabilir.
  - Kanunun `chunker.py`'sindeki bleed-kırpma kuralları (yürütme anchor'ı, kanun-sonu ek,
    E-tuzağı guard'ı) tebliğde anlamsız — hatta zararlı.

YÖNERGELER (park kaldırılırsa):
  1. Önce ÖLÇ, sonra yaz. Tebliğleri çek (`mevzuatTurList: ["TEBLIGLER"]`), yapısını incele
     (`scripts/teblig/yapi_olc.py`): madde ağacı var mı? Madde işareti nasıl? Fıkra/bent var mı?
  2. `src/kanun/` modüllerini OKU, uygun olanları KOPYALA (import etme). Kopyaladıktan
     sonra tebliğe özgü hale getir; kanun tarafına asla dokunma.
  3. Çıktı şeması `{id, text, metadata}` kalsın — böylece ileride tek Qdrant'ta birleşebilir.
     `metadata.mevzuat_tur = "TEBLIGLER"` ekle (kanun korpusu da taşır: `"KANUN"` — src/kanun/corpus.py).

Veri yolları (tür-kapsamlı, kanunla karışmaz; `data/` git-ignored):
  data/teblig/raw/          ham HTML + ağaç cache (`fetch.py` yazar)
  data/teblig/korpus.jsonl  çıktı — HENÜZ ÜRETİLMEDİ (build script'i yok)

Not: `scripts/kanun/build_corpus.py` çıktıyı "w" modunda EZER. Tebliğ build'i kendi
çıktı yoluna yazmalı — asla `data/kanun/` altına.
"""
