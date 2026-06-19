# Commit Disiplini

Bu repoda commit, branch ve entegrasyon kurallarının **tek kaynağı** bu dosyadır.
Yeni katılan herkes (insan veya AI ajan) buradaki kurallara uymak zorundadır.

---

## 1. Altın Kurallar (özet)

| Kural | Durum |
|---|---|
| Commit mesajlarında AI co-author / "Generated with" satırı | ❌ **YASAK** |
| `main` branch'ine doğrudan push | 🚫 **YASAK** |
| Branch isimleri `phase-N/feature-adi` formatında | ✅ **ZORUNLU** |
| Her commit atomik (tek mantıksal değişiklik) | ✅ **ZORUNLU** |
| `main`'e yalnızca PR üzerinden merge | ✅ **ZORUNLU** |

---

## 2. Commit Mesajı Kuralları

### 2.1. AI imzası yasağı
Commit mesajlarına **hiçbir koşulda** şunlar eklenmez:

- `Co-Authored-By: Claude ...` veya başka bir AI co-author satırı
- `🤖 Generated with ...` / `Generated with Claude Code` benzeri footer
- Herhangi bir araç/asistan reklamı

> Commit'in yazarı, `git config user.name` ile tanımlı kişidir. Başka imza eklenmez.

### 2.2. Format
Conventional Commits tarzı kullanılır:

```
<type>(<scope>): <kısa özet>

<opsiyonel gövde — NE ve NEDEN, NASIL değil>
```

**type** değerleri: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `build`.

Örnekler:
```
feat(chunking): madde bazlı atomik chunk üreticisi ekle
fix(metadata): mülga hüküm bayrağı yanlış işaretleniyordu
docs(roadmap): faz 5 bağımlılıklarını netleştir
chore(docker): qdrant servisini compose'a ekle
```

- Özet satırı emir kipinde, ~72 karakteri geçmez, sonunda nokta yok.
- Gövde gerekiyorsa **neden** değiştiğini anlatır.

---

## 3. Atomik Commit

Bir commit = **tek mantıksal değişiklik**. Geri alınabilir, gözden geçirilebilir, kendi başına anlamlı olmalı.

**Yap:**
- Bir özellik + onun testi → ayrı ayrı veya birlikte ama tek konu
- Bağımsız iki düzeltme → iki ayrı commit
- "Çalışan ara durum" bırak; her commit derlenebilir/çalışır olmalı

**Yapma:**
- "wip", "fix2", "asdf" gibi mesajlar
- Tek commit'te chunking + docker + readme karışık değişiklik
- Formatlama (whitespace) ile mantık değişikliğini aynı commit'te karıştırma

---

## 4. Branch Stratejisi

### 4.1. İsimlendirme — `phase-N/feature-adi`
`N` = roadmap'teki faz numarası, `feature-adi` = kısa, kebab-case, açıklayıcı.

```
phase-0/project-governance-docs
phase-1/data-acquisition
phase-2/structural-chunking
phase-3/metadata-enrichment
phase-4/corpus-artifact
phase-5/embedding-index
phase-6/retrieval-api
phase-7/dockerize
```

- Faza bağlanmayan acil işler için: `phase-N/<feature>` yerine yine en yakın faz numarası kullanılır; gerçekten faz-dışı bakım için `chore/<konu>` kabul edilir.
- Bir branch tek bir feature/iş kalemine odaklanır.

### 4.2. Akış
```
main  ──●────────────────────●──  (yalnız PR ile ilerler)
         \                  /
          phase-N/feature ●─●─●   (atomik commit'ler)
```

1. `main`'den güncel branch aç: `git checkout main && git pull && git checkout -b phase-N/feature-adi`
2. Atomik commit'lerle çalış.
3. Push: `git push -u origin phase-N/feature-adi` (asla `main`'e değil).
4. PR aç → gözden geçir → `main`'e merge et.
5. Merge sonrası branch silinir.

---

## 5. `main` Koruması

### 5.1. Politika
`main`'e **doğrudan push yapılmaz**. Tüm değişiklikler PR üzerinden gelir.

### 5.2. GitHub Branch Protection kurulumu (UI'dan yapılacak)
GitHub repo ayarlarından `main` kilitlenmelidir:

> **Settings → Branches → Add branch ruleset (veya Add rule)**, `main` için:
> - ✅ **Require a pull request before merging** (doğrudan push'u engeller)
>   - (opsiyonel) Require approvals: 1
> - ✅ **Require status checks to pass before merging** (CI eklenince)
> - ✅ **Require linear history** (atomik/temiz geçmiş için önerilir)
> - ✅ **Do not allow bypassing the above settings** (admin dahil)
> - ✅ **Block force pushes**

Ayar yapılana kadar kural **manuel** uygulanır: kimse `git push origin main` çalıştırmaz.

### 5.3. (Opsiyonel) Yerel emniyet
İsteğe bağlı olarak yerel bir `pre-push` hook ile `main`'e push engellenebilir. Bu repoda şimdilik politika + GitHub koruması yeterli kabul edilmiştir.

---

## 6. Kontrol Listesi (her commit öncesi)

- [ ] Değişiklik tek bir mantıksal konuyla mı sınırlı?
- [ ] Mesaj `type(scope): özet` formatında mı?
- [ ] AI co-author / "Generated with" satırı **yok** mu?
- [ ] `main`'de değil, `phase-N/feature-adi` branch'inde miyim?
- [ ] Değişiklik kapsam (`compliance.md`) sınırları içinde mi?
