"""TEBLİĞ pipeline'ı — HENÜZ YAZILMADI (iskelet).

Bu paket, `src/kanun/` ile **hiçbir kodu paylaşmaz.** Bilinçli karar: her mevzuat türü
kendi fetch/chunker/parser'ını sıfırdan alır. Sebep — tebliğ, kanundan yapısal olarak
farklıdır ve ortak soyutlama (if tur=='KANUN' ... else ...) iki tarafı da bozar:

  - Tebliğlerin madde ağacı (`mevzuatMaddeTree`) çoğu zaman BOŞ döner; kanun parser'ı
    ağaca dayanıyor (hiyerarşi, madde başlıkları, bleed-marker'ları).
  - Tebliğ metni "MADDE 1 –" yerine düz paragraf, "Sıra No", ek/cetvel ağırlıklı olabilir.
  - Kanunun `chunker.py`'sindeki bleed-kırpma kuralları (yürütme anchor'ı, kanun-sonu ek,
    E-tuzağı guard'ı) tebliğde anlamsız — hatta zararlı.

BAŞLARKEN:
  1. Önce ÖLÇ, sonra yaz. Birkaç tebliği çek (`mevzuatTurList: ["TEBLIGLER"]`), yapısını
     incele: madde ağacı var mı? Madde işareti nasıl? Fıkra/bent var mı?
  2. `src/kanun/` modüllerini OKU, uygun olanları KOPYALA (import etme). Kopyaladıktan
     sonra tebliğe özgü hale getir; kanun tarafına asla dokunma.
  3. Çıktı şeması `{id, text, metadata}` kalsın — böylece ileride tek Qdrant'ta birleşebilir.
     `metadata.mevzuat_tur = "TEBLIGLER"` ekle (kanun korpusunda bu alan yok, tek-tür olduğu için).

Veri yolları (tür-kapsamlı, kanunla karışmaz):
  data/teblig/raw/        ham HTML + ağaç cache
  data/teblig/korpus.jsonl  çıktı

Not: `scripts/kanun/build_corpus.py` çıktıyı "w" modunda EZER. Tebliğ build'in kendi
çıktı yoluna yazmalı — asla `data/kanun/` altına.
"""
