# FAZ 7 — Roman-rakam `i)` 3. seviye sızması (Z1) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (0 FP)**
> "Kalan Zehir Kalemleri" listesinin **en ağır** kalemi (atıf çözümü çöküyor, gerçek içerik kaçıyor).
> Dosya: `src/mevzuat_tool/fikra.py`.

## ✅ SONUÇ (commit `c82baee` — etkilenen 5, 0 FP)

- **Z1** ([fikra.py](../../src/mevzuat_tool/fikra.py) `_roman_i_idx` + `_harf_alt_bentler`):
  üç-seviye hiyerarşide (`2. > a) > i) ii)`) roman `i)` harf-bent sanılıp harf-listesine kardeş
  giriyordu → bir önceki harf-bent BOŞ kalıyordu. Artık roman `i)` işaret olarak atlanır,
  dilimleme onu bir önceki harf-bende yapıştırır.
- **Birim test:** +3 (tekrarlı-roman + boş-önce-roman + meşru-`i)`-koruma). Tam paket **202 passed**.
- **916-kanun regresyon:** etkilenen **5 madde** (`103011-Ek1`, `103017-Ek2`, `103044-27`,
  `103044-227`, `103111-94`), hepsi **text korundu** (kayıp yok); **boş-alt-bent 3→0**; meşru-`i)`
  listeleri (`103111-89`, `103006-Mukerrer298`, `103161-Gecici11`) korundu (**0 FP**);
  status-flip 0, fıkra/bent dağılımı sabit.

> 🔑 **DERS:** İlk analiz "~12 üst-bent" dedi ama gerçek zehir **5 madde** — kalanı MEŞRU `i)`
> harf-bent (Türkçe alfabe `...ı) i) j)...` veya `ı)` atlanmış `...h) i) j)...`). KESİN sinyal
> (tekrarlı `i)` VEYA önceki-harf-boş) bu ayrımı 0 FP ile yaptı. "Şüpheli" sayılan
> `103006-Mukerrer298` doğru biçimde meşru çıktı, dokunulmadı. **998-kenar-numara dersinin
> tekrarı:** alfabetik konum + içerik-doluluk, harf işaretinden daha güvenilir sinyaldir.

## Context

Gerçek yapı 3 seviyeli: `2.` (üst, numara) → `a) b) c)...` (orta, harf) → `i) ii) iii)` (alt-alt,
roman). `_BENT_HARF_ISARET = [a-zçğıöşü]\)` roman `i)`'yi orta-seviye harf-bent sanıyordu →
`a)`'nın altındaki `i)` `a)`'dan koparılıp ayrı alt-bent oluyor, `b)`'nin `i)`'si de `b)`'den
koparılıyor → `b)` bomboş (`len=2`, 103017-Ek2 Damga V.). B3 (FAZ 3) iki-seviye destekliyor,
3. seviye yoktu.

### Doğrulanmış gerçekler (oturumda)
- `i)` içeren harf-alt-bent listeleri 12 → sınıflandırma: **4 kesin-roman** (`i)` tekrarlı),
  **4 şüpheli** (`i)` tek, `ı)` öncesi değil), **4 meşru** (`i)` tek, `ı)` hemen öncesi).
- Şüpheli 4 incelendi: `103044-227` (`f)` boş + `i)`) = gerçek roman; `103111-89`/`103006` =
  meşru `i)` (komşular dolu, sıralı). Ayrım sinyali kesinleşti.

## Kapsam kararı (kullanıcı): DAR (kesin-roman)
**Tetik:** `i)` TEKRARLI (2+) VEYA `i)` öncesi harf-bent BOŞ (`f) i)` bitişik). 3. seviye katmanı
(yeni AltAltBent dataclass) KURULMADI — roman `i)` metni bir önceki harf-bende düz birleşir.
Reddedilen: tam 3. seviye modelleme (şema değişimi + FP riski), salt-boş-bent (hiyerarşi düz kalır).

## Regresyon / Doğrulama
1. 🔴→🟢 TDD: tekrarlı-roman (103017-Ek2 deseni) + boş-önce-roman (103044-227) hedef testleri.
2. 🛡️ FP-koruma: meşru `i)` (`...h) i) j)...`) roman SANILMAMALI testi.
3. ♻️ Tam `pytest` → 202 passed.
4. 📊 916-kanun compare: etkilenen-madde (beklenen ~5), boş-alt-bent (azalmalı), text korunması
   (değişmemeli), meşru-`i)` listelerinin dokunulmadığı (FP kapısı).
   > ⚠️ Smoke build korpusu ezer → baseline al/geri yükle.

## Bilinen sınır
Roman `i)` metni bir önceki harf-bende DÜZ birleşir (ayrı `i)` alt-alt-bent düğümü oluşmaz).
3. seviye atıf (`a) bendinin i) alt-bendi`) hâlâ ayrı çözülmez ama içerik kaybı/boş düğüm YOK —
bu MVP için yeterli (atomik birim madde; derin alt-seviye future work).

## Çıktılar (commit'ler)
- `fix(fikra): roman-rakam 'i)' 3. seviye sızmasını harf-listeden ayır (Z1)`
- `docs(faz-7): roman-i) 3. seviye tamamlandı + master Z1 güncel`
