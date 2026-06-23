# DEVİR PROMPTU — Tam 916 KANUN korpus ölçümü (OTONOM, soru sorma)

> Bunu yeni bir chat'e **olduğu gibi** yapıştır. Kullanıcı uyuyor — **HİÇBİR SORU SORMA**, tüm
> kararları aşağıdaki talimatlara göre kendin ver, tam 916'yı bitir, sonunda kapsamlı rapor sun.

---

## BAĞLAM (ne yapıldı, neredeyiz)

Türk mevzuatı (KANUN türü) için vanilla-RAG retrieval pipeline'ı. mevzuat-mcp/bedesten'den HTML
çekilip madde-madde parse + metadata zenginleştiriliyor. Bu chat'in görevi: **916 KANUN'un
TAMAMINI çekip pipeline'dan geçirmek ve ne kadar iyi parse ettiğimizi ölçen tam raporu sunmak.**

**Branch:** `phase-c/data-ingest` (zaten buradasın, checkout etme gerekmez — doğrula: `git branch --show-current`).

**Çalışan altyapı (hepsi commit'li, test edilmiş — DOKUNMA, sadece kullan):**
- `src/mevzuat_tool/fetch.py` — `MevzuatFetcher`: Retry-After-uyumlu (429 token-bucket ~10 istek/pencere,
  sunucu `Retry-After` header'ı veriyor), cache'li (`data/raw/html_<mid>.html`), pydantic'siz
  (`.venv` python'uyla çalışır, mevzuat-mcp python'una GEREK YOK). Deterministik, sıfır-kayıp.
- `scripts/eval_corpus.py` — korpus ölçüm harness'ı. `MevzuatFetcher` kullanır, devam-güvenli
  (`data/raw/_corpus_results.jsonl`'e ekler, cache'teki mid'leri atlar).
- `scripts/eval_corpus_report.py` — JSONL'den 5 bölümlü rapor üretir.
- `src/mevzuat_tool/aralik.py` — içeriksiz 'MADDE N ilâ M / gruplu-tire / ve' tespiti (eval metrik dürüstlüğü).
- Pipeline modülleri: chunker(madde böl), normalize, tree, enrich(metadata), dipnot, fikra, degisiklik,
  ids, html_split, html_table, html_dipnot.

**Bu chat'te düzeltilen 2 gövde-bug (commit'li):**
- `_strip_bleed` over-truncation (commit a481073): tree-marker gövdeyi yanlış kesiyordu → level/madde
  marker ayrımı + suffix-only kırpma. KVKK M23 örtüşme 0.99.
- `split_dipnot_apendiksi` over-split (commit 2b07a31): yayılmış [n] referanslarını apendiks sanıyordu →
  yoğunluk kontrolü (ort-aralık >800krk = apendiks değil). 7174 M8 örtüşme 0.07→0.96. 60 esas kanunda
  gerçek over-split kalıntısı = 0.

**Şu anki cache:** ~105 kanunun HTML'i cache'li, `data/raw/_corpus_results.jsonl` 100 kanun içeriyor
AMA bu **fix ÖNCESİ** üretilmiş (eski gövde-bugları içeriyor). → BU JSONL'İ SİL, sıfırdan tam 916'yı çek.

---

## ÖLÇÜM KARARLARI (kullanıcı bunları onayladı — uygula, sorma)

1. **Kapsam:** 916 KANUN'un TAMAMI çekilir. Esas-kanun vs değişiklik-paketi AYRI raporlanır
   (`is_degisiklik_paketi` zaten harness'ta).
2. **Ground-truth:** bedesten article-tree (madde no kümesi). Ek/Geçici/Mükerrer/suffix FP'leri
   "sahte-FP" olarak ayrılır (Faz B kanıtı: bunlar ağacın eksiği, pipeline doğru) → düzeltilmiş precision.
3. **Aralık-FN:** içeriksiz 'ilâ/gruplu/ve' maddeleri gerçek-FN'den ayrılır → dürüst recall (zaten harness'ta).
4. **Gövde-doğruluğu:** rapora EK olarak ölç (aşağıda Adım 4).

---

## YAPILACAKLAR (sırayla, otonom)

### Adım 0 — Sağlık kontrolü
```bash
cd "c:/Users/tuna9/OneDrive/Masaüstü/MevzuatTool"
git branch --show-current          # phase-c/data-ingest olmalı
.venv/Scripts/python.exe -m pytest -q   # 101 passed olmalı; değilse DUR, neyin bozulduğunu raporla
```

### Adım 1 — Eski (fix-öncesi) sonucu sil, tam 916'yı çek
```bash
rm -f data/raw/_corpus_results.jsonl
# CORPUS_LIMIT verme (0=hepsi) → tam 916. .venv python'u yeter (fetch.py pydantic'siz).
CORPUS_LIMIT=0 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/eval_corpus.py
```
- Bu uzun sürer (~916 kanun × Retry-After bekleme; tahmini 30-60 dk). **run_in_background:true** ile başlat.
- Devam-güvenli: kesilirse aynı komut kaldığı yerden devam eder (cache + JSONL append).
- İlerlemeyi periyodik kontrol et: `wc -l data/raw/_corpus_results.jsonl` (hedef 916) ve log'da "ÇEKİM TAMAM".
- 429/throttle OLURSA: fetch.py zaten Retry-After'a uyuyor, takılma OLMAMALI. Eğer bir kanun
  sürekli hata verirse, harness onu atlar ve devam eder (try/except'li) — sorun değil, raporla.

### Adım 2 — Çekim bitince madde-set raporu
```bash
PYTHONIOENCODING=utf-8 python scripts/eval_corpus_report.py
```
- Bu 5 bölüm verir: (A) madde-set P/R/F1 (esas vs değişiklik), (B) metadata doğruluğu,
  (C) parse-sağlık (0-madde, çöküş, gerçek-FN), (D) Faz B kapsama (tablo/dipnot), (E) gerçek-FP.

### Adım 3 — Sağlık doğrulaması (throttle artefaktı var mı?)
JSONL'i kontrol et: kaç kanun `gt=0`? Eğer çok sayıda kanun `gt=0` ise (throttle ile boş gelmişse),
o kanunları yeniden çek (cache'teki bozuk olanları sil, harness tekrar dener). Beklenen: `gt=0`
yalnızca GERÇEK içeriksiz kanunlarda (uluslararası anlaşma onayı vb.), ~%1-2. Eğer >%10 ise
throttle artefaktı var demektir → o mid'lerin html cache'ini silip yeniden çek.
Bilinen büyük kanunları spot-check et (Medeni 4721→1030 madde, TTK 6102→1535, TCK 5237→345 olmalı).

### Adım 4 — GÖVDE-DOĞRULUĞU spot-check (madde-sayısından farklı, kritik)
Madde-sayısı doğru olsa bile gövde içeriği kesik/karışık olabilir. Rastgele ~30 esas kanundan
örnek maddeleri, resmî tek-madde gövdesiyle karşılaştır:
- Resmî gövde: `bedesten get_article_content` = `_post_with_retry(client,"/getDocumentContent",
  _wrap({"documentType":"MADDE","id":madde_id}), rate)` → `_decode_base64` → `strip_html`.
  (madde_id ağaçtan gelir: `fetch_tree(mid)` → node.madde_id.)
- Pipeline gövde: `enrich(...)` çıktısı `Madde.body`.
- Metrik: resmî gövdenin anlamlı kelimelerinin (>=4 harf) kaçı pipeline gövdesinde var (içerik-recall).
  Örtüşme >=0.85 = İYİ, 0.6-0.85 = orta, <0.6 = DÜŞÜK (incele).
- DÜŞÜK çıkanları say + birkaç örnek göster. Beklenen: %95+ İYİ (2 gövde-bug düzeltildi).
- Referans için bu chat'te yazılan `scripts/_eval_govde.py` benzeri bir script kullanabilirsin (yoksa yaz,
  geçici script — commit etme, `_` prefiksli geçici dosya).

### Adım 5 — Kalan gerçek-FN ve gerçek-FP analizi
Rapordaki gerçek-FN (aralık-olmayan kayıp) ve gerçek-FP (düz-numara uydurma) olan kanunları listele.
Birkaçının ham metnini incele (kök neden). Bunlar düzeltilmeli mi yoksa bilinen-sınır mı, kısa değerlendir.
DÜZELTME YAPMA (kullanıcı uyuyor) — sadece TESPİT et ve rapora yaz. Düzeltme önerilerini rapora ekle.

### Adım 6 — Commit (sadece geçici-olmayan üretilmiş şeyler)
- `data/` gitignored — JSONL/HTML commit edilmez (doğru).
- Geçici `_`-prefiksli script yazdıysan SİL.
- Bu chat'te kod değişikliği YAPMADIYSAN (sadece ölçüm), commit gerekmez.
- Eğer Adım 5'te küçük bir düzeltme GEREKTİĞİNE ikna olursan bile YAPMA — rapora "öneri" olarak yaz,
  kullanıcı uyandığında karar verir.

---

## RAPOR (sabah kullanıcıya sun — Türkçe, net, sayısal)

Şu yapıda kapsamlı bir rapor sun:

1. **ÖZET:** 916 kanun çekildi mi? Kaç esas / kaç değişiklik-paketi / kaç içeriksiz (gt=0)?
   Toplam kaç madde parse edildi?
2. **MADDE-SET:** esas kanunlar + tüm korpus için recall_dürüst, precision_düzeltilmiş, F1.
   (Esas kanunlarda hedef: recall ~1.0, precision ~1.0.)
3. **METADATA:** madde_baslik / maddeId / hiyerarsi_yolu doğruluk % (hedef %100).
4. **GÖVDE-DOĞRULUĞU:** spot-check sonucu — % İYİ / orta / DÜŞÜK madde. DÜŞÜK örnekleri.
5. **PARSE-SAĞLIK:** 0-madde kanun sayısı, pipeline-çöküş, gerçek-FN toplam (+ en çok FN'li kanunlar).
6. **FAZ B KAPSAMA:** kaç içerik tablosu, kaç bağlı dipnot, kaç kanunda.
7. **KALAN SORUNLAR + ÖNERİLER:** gerçek-FN/FP kök nedenleri, düzeltme önerileri (yapma, öner).
8. **THROTTLE/ÇEKİM:** kaç dakika sürdü, throttle takılması oldu mu, kaç kanun atlandı/hata.

Raporu hem ekrana yaz hem `docs/superpowers/916-korpus-raporu.md` dosyasına kaydet (commit ET — bu
kalıcı bir doküman, branch'te kalsın).

---

## KRİTİK KURALLAR
- **SORU SORMA.** Tüm kararlar yukarıda. Belirsizlik olursa en muhafazakâr/güvenli seçeneği al, rapora not düş.
- **DÜZELTME YAPMA** (kod değiştirme) — sadece ÖLÇ + TESPİT et. (Adım 5 istisnası bile yasak: öner, yapma.)
- **fetch.py / pipeline modüllerine DOKUNMA** — çalışıyorlar.
- **mevzuat-mcp python'una gerek yok** — fetch.py `.venv` python'uyla çalışır (pydantic'siz). Test komutları
  ve script'ler hep `.venv/Scripts/python.exe` ile.
- **Windows/cp1254:** print'lerde Unicode tik kullanma, ASCII `[OK]`. PYTHONIOENCODING=utf-8 ekle.
- **Devam-güvenli ol:** uzun çekim background'da; periyodik kontrol et, bittiğinde raporla. Kesinti olursa
  aynı komut kaldığı yerden devam eder.
- **Token/zaman:** Tüm geceyi kullanabilirsin. Acele etme, tam ve doğru bitir. Sabah kullanıcı uyandığında
  hem 916 çekilmiş hem rapor hazır olsun.
