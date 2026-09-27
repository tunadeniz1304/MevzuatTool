# -*- coding: utf-8 -*-
"""Reranker (cross-encoder) — `BAAI/bge-reranker-v2-m3` ile (sorgu, madde) çiftlerini puanlar.

Bi-encoder (BGE-M3) sorguyu ve maddeyi AYRI vektörlere çevirir, benzerliği sonradan ölçer → hızlı ama
kaba. Cross-encoder sorgu + maddeyi TEK girdi olarak birlikte okur ([CLS] sorgu [SEP] madde) ve doğrudan
bir alaka skoru (logit) üretir → çok daha isabetli ama her aday için ayrı bir model geçişi gerekir.
Bu yüzden yalnız WSUM'un ilk RERANK_ADAY adayına uygulanır (iki aşamalı: getir → yeniden sırala).

Arayüz: `skorla(sorgu, metinler) -> list[float]` (metinlerle aynı sırada, büyük = daha alakalı).
  - TorchReranker : transformers `AutoModelForSequenceClassification` (FP32). `metrik_rerank.py`
                    `_rerank_yukle` / `rerank_skorla` mantığının kütüphane hali.
  - OnnxReranker  : aynı modelin ONNX export'u (FP32 veya dinamik int8), onnxruntime CPU.
Her ikisi de çiftleri uzunluğa göre sıralayıp batch'ler (padding israfı az) ve sonucu orijinal sıraya döndürür.
"""
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"


def _uzunluk_sirali_batchler(ciftler, batch):
    """Çiftleri kaba uzunluğa göre sırala → batch'le. (indeksler, çiftler) listesi döner."""
    sira = sorted(range(len(ciftler)), key=lambda i: len(ciftler[i][1]))
    for bas in range(0, len(sira), batch):
        idx = sira[bas: bas + batch]
        yield idx, [ciftler[i] for i in idx]


class TorchReranker:
    def __init__(self, model_adi=RERANK_MODEL, max_length=512, batch=16, cihaz="cpu"):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if cihaz == "auto":
            cihaz = "cuda" if torch.cuda.is_available() else "cpu"
        self._torch = torch
        self.cihaz = cihaz
        self.max_length = max_length
        self.batch = batch
        self.tok = AutoTokenizer.from_pretrained(model_adi)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_adi)
        self.model.eval()
        self.model.to(cihaz)

    def skorla(self, sorgu, metinler):
        return self.skorla_ciftler([[sorgu, m] for m in metinler])

    def skorla_ciftler(self, ciftler):
        """[[sorgu, metin], ...] → skor listesi (farklı sorguların çiftleri birlikte batch'lenebilir)."""
        if not ciftler:
            return []
        skor = [0.0] * len(ciftler)
        with self._torch.no_grad():
            for idx, grup in _uzunluk_sirali_batchler(ciftler, self.batch):
                inp = self.tok(grup, padding=True, truncation=True, max_length=self.max_length,
                               return_tensors="pt")
                inp = {k: v.to(self.cihaz) for k, v in inp.items()}
                cikti = self.model(**inp).logits.view(-1).float().cpu().tolist()
                for i, s in zip(idx, cikti):
                    skor[i] = s
        return skor


class OnnxReranker:
    """ONNX Runtime ile reranker. `model_yol` klasöründe tokenizer dosyaları da bulunur (onnx_export.py)."""

    def __init__(self, model_yol, max_length=512, batch=16, threads=4):
        import os
        import onnxruntime as ort
        from transformers import AutoTokenizer

        self.max_length = max_length
        self.batch = batch
        self.tok = AutoTokenizer.from_pretrained(os.path.dirname(model_yol))
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(model_yol, sess_options=so,
                                         providers=["CPUExecutionProvider"])
        self.girdiler = {i.name for i in self.sess.get_inputs()}

    def skorla(self, sorgu, metinler):
        return self.skorla_ciftler([[sorgu, m] for m in metinler])

    def skorla_ciftler(self, ciftler):
        import numpy as np

        if not ciftler:
            return []
        skor = [0.0] * len(ciftler)
        for idx, grup in _uzunluk_sirali_batchler(ciftler, self.batch):
            inp = self.tok(grup, padding=True, truncation=True, max_length=self.max_length,
                           return_tensors="np")
            besle = {k: v.astype(np.int64) for k, v in inp.items() if k in self.girdiler}
            logits = self.sess.run(["logits"], besle)[0].reshape(-1)
            for i, s in zip(idx, logits):
                skor[i] = float(s)
        return skor
