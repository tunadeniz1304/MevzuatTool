"""KANUN pipeline'ı — ham HTML → yapısal `{id, text, metadata}` korpus.

MevzuatTool'un ilk ve şu an tek tamamlanmış mevzuat türü. Vanilla RAG'ın retrieval
yarısı; generation (LLM) kapsam dışı. Bkz. docs/mevzuat-mvp-kapsam.md, docs/arch.md.

Bu paket **yalnız KANUN'a** özgüdür. Tebliğ/yönetmelik kendi paketlerinde (`src/teblig/`,
`src/yonetmelik/`) sıfırdan yazılır — ortak soyutlama YOK, kod paylaşımı YOK (bilinçli).
Buradaki bir kuralı değiştirmek başka türü asla bozamaz.

Build zinciri (scripts/kanun/build_corpus.py orkestre eder):
    fetch → normalize → chunker → tree → enrich(dipnot·degisiklik·fikra·ids) → corpus

Kritik invariant'lar (bozulursa korpus SESSİZCE bozulur):
  1. `\\x1f` paragraf sınırı: fetch.strip_html üretir → normalize korur → fikra böler.
  2. fikra.py bent-listeli fıkra devam-koruması (yoksa rakamlı bent listeleri parçalanır).
  3. 'Ancak' yeni-fıkra sinyali DEĞİLDİR (bent-içi istisna cümlesi de öyle başlar).
  4. Mülga maddeler korpusta KALIR (işaretli), elenmez.
  5. Chunk id `mevzuatId` tabanlıdır, `kanun_no` değil (çakışan no'lar var: 6551).

Doğrulama: `python scripts/kanun/build_corpus.py` → 916 kanun / 31.419 chunk;
`k193 m7` = 2 fıkra, 7 bent.
"""
