# FAZ 0 — Altyapı (regresyon kapısı) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam**
> **Kod değişikliği YOK** (parser'a dokunulmaz). Yalnız: 1 yeni script + 1 yeni test dosyası.
> Amaç: Sonraki tüm fazların "0 yanlış-pozitif" disiplinini ölçecek **regresyon altyapısını** kurmak.

## ✅ SONUÇ (tamamlandı)
- `tests/test_marginal_numbers.py` — **5 koruma testi yeşil** (TMK/TBK/TTK/FSEK/Anayasa gerçek desenleri; TTK M4 marjinal-başlık+gerçek-harf-bent vakası dahil).
- `scripts/compare_corpus.py` — OLD-vs-NEW diff aracı; **kendine-diff = 0 smoke geçti** (status-flip 0, etkilenen-madde 0, 5 korumalı kanun 0, `--gate` exit 0).
- Tam test: **175 passed** (170 + 5). Smoke build (`CORPUS_LIMIT=2`) parse hatasız.
- **Araç baseline'da bile bulguları yakalıyor:** sahte-bent şüphesi 21 madde (>30 bent), bent maks 864 (104030-5 Büyükşehir cetveli), son-fıkra maks 160163 (tablo şişmesi) — FAZ 2/3/4 hedefleriyle birebir.

> ⚠️ **TUZAK (gelecek fazlar için):** `build_corpus.py` çıktısı SABİT `data/corpus/korpus.jsonl`. Smoke build (`CORPUS_LIMIT`/`CORPUS_MID`) bu dosyayı **üzerine yazar** — tam korpusu siler. Her faz regresyonunda: önce `cp data/corpus/korpus.jsonl data/gold/korpus_baseline.jsonl` ile baseline al, NEW üret, compare et, sonra baseline'dan **geri yükle**. (`data/gold/` gitignore'da.)

---

## Context — neden FAZ 0 önce?

Sonraki her faz (yürürlük, fıkra/bent, sızma) korpus-geneli etki yaratacak. Bu etkiyi ölçmeden "0 yanlış-pozitif" iddiası kanıtlanamaz. İki altyapı parçası gerekiyor:

1. **`compare_corpus.py`** — bir parser değişikliğinin OLD-vs-NEW korpus etkisini (mülga-flip, bent-sayısı, sahte-bent, etkilenen-madde) ölçen diff aracı. **Her fazın 4. regresyon adımı buna dayanıyor.**
2. **E-tuzağı koruma testleri** — 998 kenar-numaralı madde (TMK/TBK/TTK/FSEK/Anayasa) FAZ 3'te toplu bozulma riski taşıyor. Koruma testleri **şimdi** yazılıp yeşil olmalı ki FAZ 3 onları kıramasın.

İkisi de salt-okur/test — parser davranışını değiştirmez, dolayısıyla mevcut 173 testin hiçbiri kırılmaz.

---

## Doğrulanmış gerçekler (bu oturumda korpustan)

- **E-tuzağı gerçek id'leri** (koruma testleri bunları kullanacak):
  | Kanun | id örnek | madde_baslik | fıkra/bent (mevcut DOĞRU çıktı) |
  |---|---|---|---|
  | TMK 4721 | `103249-1` M1 | `A. Hukukun uygulanması ve kaynakları` | fıkra=1, **bent=0** |
  | TMK 4721 | `103249-3` M3 | `II. İyiniyet` | fıkra=1, **bent=0** |
  | TBK 6098 | `103273-63` M63 | `1. Genel olarak` | fıkra=1, **bent=0** |
  | TTK 6102 | `103039-4` M4 | `1. Genel olarak` | fıkra=1, **bent=6** ⚠️ (gerçek harf-bentler — korunmalı) |
  | FSEK 5846 | `104458-14` M14 | `1. Umuma arz salahiyeti` | fıkra=1, **bent=0** |
  | Anayasa 2709 | `103165-1` M1 | `I. Devletin şekli` | fıkra=1, **bent=0** |
- **`build_corpus.py` çıktı yolu SABİT** (`data/corpus/korpus.jsonl`, [build_corpus.py:31](../../scripts/build_corpus.py#L31)) — env ile değiştirilemiyor. → compare için baseline'ı **kopyalayarak** alacağız (script yolu parametre alacak).
- **Çalıştırma:** `.venv/Scripts/python.exe scripts/build_corpus.py` (cache'ten ~saniyeler, ağ yok). `CORPUS_MID=`/`CORPUS_LIMIT=` env'leri mevcut.
- **Stil referansı:** [eval_corpus_report.py](../../scripts/eval_corpus_report.py) — agregat + segment + tablo çıktısı. `compare_corpus.py` bunu taklit eder ama TEK korpus yerine İKİ korpus diff'i yapar.

---

## Yapılacaklar

### 0.1 — `scripts/compare_corpus.py` (YENİ)

**Amaç:** İki `korpus.jsonl` (OLD baseline + NEW aday) id-bazlı eşleştirip yapısal farkları raporlamak.

**Arayüz:**
```
python scripts/compare_corpus.py <OLD.jsonl> <NEW.jsonl> [--kanun 4721,6098,...] [--flips]
```

**Üreteceği metrikler (faz kapılarını besler):**
1. **Özet sayım:** OLD/NEW chunk sayısı, ortak id, yalnız-OLD, yalnız-NEW (madde eklenme/silinme).
2. **Status-flip tablosu:** `yurutluk` değişen maddeler — `yürürlükte→mülga` ve `mülga→yürürlükte` ayrı listeler + sayılar (FAZ 1 kapısı). `--flips` ile id listesi dökülür.
3. **Mülga oranı:** OLD vs NEW toplam + segment (esas/değişiklik) yüzdesi.
4. **Bent-sayısı dağılımı:** madde başına bent histogramı (OLD vs NEW); **sahte-bent proxy'si** = tek maddede >30 ardışık bent VEYA tekrarlayan `a)` koşusu olan madde sayısı (FAZ 2 kapısı).
5. **Fıkra-sayısı dağılımı:** madde başına fıkra (FAZ 2/B1 kapısı — dipnot birleşmesi düzelince fıkra sayısı artar).
6. **Etkilenen-madde:** text VEYA metadata değişen chunk id sayısı; `--kanun` ile belirli kanunlara kısıtlanabilir (FAZ 3 KRİTİK KAPISI: TMK/TBK/TTK/FSEK/Anayasa → 0 olmalı).
7. **`fikralar[-1]` uzunluk dağılımı:** son-fıkra text uzunluğu (FAZ 4 kapısı — sızma kırpılınca kısalır; aşırı-kısalma = regresyon).

**Tasarım notları:**
- Salt-okur; iki dosyayı dict'e (`id → chunk`) yükle, ortak/fark id setleri çıkar.
- Çıktı [eval_corpus_report.py](../../scripts/eval_corpus_report.py) gibi bölümlü düz-metin tablo (`=`*94 başlıklar).
- Hiçbir parser modülü import etmez (sadece `json`); böylece OLD/NEW kod sürümünden bağımsız çalışır.
- Exit code: yalnızca rapor (kapı kontrolü manuel; ileride `--gate` eklenebilir).

### 0.2 — `tests/test_marginal_numbers.py` (YENİ)

**Amaç:** Kenar-numaralı (İsviçre-geleneği) maddelerin marjinal `1.`/`A.`/`I.` başlıklarının fıkra/bent SAYILMADIĞINI kilitlemek. FAZ 3 öncesi yeşil, sonrası da yeşil kalmalı.

**Stil:** [test_fikra.py](../../tests/test_fikra.py) inline-fixture + gerçek-madde referanslı yorum.

**Test vakaları (gerçek desenlerle):**
1. `test_marginal_letter_title_not_bent` — gövde `A. Hukukun uygulanması ... düzenler.` (TMK M1 deseni) → `parse_fikralar` tek fıkra, `bentler=[]`.
2. `test_marginal_roman_title_not_bent` — `II. İyiniyet ... korunur.` (TMK M3) → bent yok.
3. `test_marginal_number_title_not_bent` — `1. Genel olarak ... uygulanır.` (TBK M63) → bent yok.
4. `test_marginal_number_with_real_harf_bentler_preserved` — `1. Genel olarak: a) ilk b) ikinci c) üçüncü` (TTK M4 deseni: marjinal başlık + GERÇEK harf-bentler) → `a) b) c)` bentleri **korunur**, marjinal `1.` bent SAYILMAZ. ⚠️ En kritik vaka.
5. `test_consecutive_marginal_numbers_not_numbered_bentler` — `1. ... metni. 2. ... metni.` ardışık marjinal numara (TBK M63→M64 sızma riski) → bunlar numara-bent SAYILMAZ (mevcut sıralı-koşu mantığı zaten eler; bu kilit).

> Not: Bu testler MEVCUT davranışı doğruluyor (hepsi şimdiden yeşil geçmeli). FAZ 3'te B3 düzeltmesi yapılınca **yine yeşil** kalmaları regresyon kanıtı olur.

---

## Regresyon / Doğrulama (FAZ 0 sonu)

1. `.venv/Scripts/python.exe -m pytest -q` → **173 + 5 = 178 test**, 0 kırık (parser değişmedi).
2. `.venv/Scripts/python.exe -m pytest tests/test_marginal_numbers.py -v` → 5 yeni test yeşil.
3. **compare_corpus.py smoke:** baseline'ı kopyala → tekrar üret → kendine karşı diff = **0 fark** (sanity):
   ```
   cp data/corpus/korpus.jsonl /tmp/korpus_OLD.jsonl
   .venv/Scripts/python.exe scripts/build_corpus.py            # NEW üret (kod aynı → birebir)
   .venv/Scripts/python.exe scripts/compare_corpus.py /tmp/korpus_OLD.jsonl data/corpus/korpus.jsonl
   # beklenen: 0 status-flip, 0 etkilenen-madde, dağılımlar birebir
   ```
   Bu "kendine-diff = 0" testi compare_corpus.py'nin doğru çalıştığını kanıtlar (deterministik baseline).
4. `--kanun 4721,6098,6102,5846,2709` ile süzülen çıktı → 0 fark (FAZ 3 kapısının çalıştığını şimdiden doğrula).

---

## Çıktılar (commit'ler)
- `feat(scripts): compare_corpus.py — OLD-vs-NEW korpus diff (faz regresyon kapısı)`
- `test(fikra): kenar-numaralı madde koruma testleri (E-tuzağı, FAZ 3 önkoşulu)`

İkisi atomik ayrı commit. Branch: mevcut `phase-c/data-ingest` üzerinde mi yoksa yeni `phase-d/structural-fidelity` mi — **kullanıcı kararı.**

---

## Açık karar (kullanıcıya)
- **Branch:** Yeni `phase-d/...` mı, mevcut branch mi?
- **Kapanış-kırpma fix'i** çalışma ağacında duruyor (46 FP). FAZ 0 ona dokunmaz ama compare_corpus.py "kendine-diff=0" testi için çalışma ağacının **temiz** olması iyi olur → kapanış-kırpma'yı geri almak compare smoke'unu netleştirir.
