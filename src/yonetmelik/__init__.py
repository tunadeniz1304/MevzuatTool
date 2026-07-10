"""YÖNETMELİK pipeline'ı — HENÜZ YAZILMADI (iskelet).

Bu paket, `src/kanun/` ve `src/teblig/` ile **hiçbir kodu paylaşmaz.** Bilinçli karar:
her mevzuat türü kendi fetch/chunker/parser'ını sıfırdan alır (bkz. `src/teblig/__init__.py`).

Yönetmelik, yapı olarak kanuna tebliğden daha yakındır (MADDE/fıkra/bent düzeni benzer),
bu yüzden `src/kanun/` modüllerinin çoğu KOPYALANIP küçük değişikliklerle çalışabilir.
Ama yine de kopyala — import etme. Kanun tarafında bir bleed-kuralı değiştiğinde
yönetmeliğin sessizce bozulmasını istemiyoruz.

Dikkat edilecek farklar (ölçmeden varsayma):
  - Bedesten'de iki ayrı tür var: `YONETMELIK` (Bakanlar Kurulu) ve `KKY` (Kurum/Kuruluş)
    ve `CB_YONETMELIK`, `UY` (Üniversite). Hangisini çekeceğine karar ver.
  - Yönetmeliklerde "Dayanak" maddesi ve ek/cetveller yaygın.
  - Kanunun `_KANUN_SONU_ANCHOR`'ı ("... yürütür") yönetmelikte de var ama farklı ifadeyle.

BAŞLARKEN:
  1. Önce ÖLÇ: birkaç yönetmelik çek, madde ağacı geliyor mu, madde işareti nasıl bak.
  2. `src/kanun/` modüllerini kopyala, yönetmeliğe uyarla, testlerini `tests/yonetmelik/` altına yaz.
  3. Çıktı şeması `{id, text, metadata}` + `metadata.mevzuat_tur = "YONETMELIK"`.

Veri yolları (tür-kapsamlı):
  data/yonetmelik/raw/         ham HTML + ağaç cache
  data/yonetmelik/korpus.jsonl çıktı
"""
