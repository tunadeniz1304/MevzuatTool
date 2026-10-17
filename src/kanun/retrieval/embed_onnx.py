# -*- coding: utf-8 -*-
"""BGE-M3 sorgu embed — ONNX Runtime (CPU) ile. `embed.py` `embed_sorgu` ile AYNI imza ve çıktı.

Model: `scripts/kanun/retrieval/onnx_export.py` üretir (FP32 `model.onnx`), `onnx_quantize.py`
dinamik int8'e çevirir (`model.int8.onnx`). Grafik dense (CLS + L2 normalize) ve token başına
sparse ağırlığını (`relu(sparse_linear(hidden))`) zaten hesaplar; burada yalnız token-id başına
max alınır (özel token'lar ve ≤0 ağırlıklar hariç) — embed.py ile birebir aynı kural.

torch GEREKTİRMEZ: onnxruntime + transformers tokenizer (servis imajı torch'suz).
Execution provider (EP) = ORT'nin grafiği hangi donanım arka ucunda koşturduğu; burada
`CPUExecutionProvider`. `intra_op_num_threads` tek bir operatörün (ör. MatMul) kaç thread'e
bölüneceğidir — fiziksel çekirdek sayısı (4) hyper-thread'li 8'den genelde daha kararlıdır.
"""
import os


class OnnxEmbedder:
    def __init__(self, model_yol, threads=4, max_length=8192):
        import onnxruntime as ort
        from transformers import AutoTokenizer

        if not os.path.exists(model_yol):
            raise FileNotFoundError(f"ONNX model yok: {model_yol} — önce onnx_export.py / onnx_quantize.py")
        self.max_length = max_length
        self.tok = AutoTokenizer.from_pretrained(os.path.dirname(model_yol))
        self.ozel = set(self.tok.all_special_ids)
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(model_yol, sess_options=so,
                                         providers=["CPUExecutionProvider"])

    def __call__(self, text):
        return self.embed_sorgu(text)

    def ham(self, text):
        """(dense np.ndarray(1024), token-ağırlıkları np.ndarray(T), input_ids list) — parity testleri için."""
        import numpy as np

        inp = self.tok(text, return_tensors="np", truncation=True, max_length=self.max_length)
        besle = {"input_ids": inp["input_ids"].astype(np.int64),
                 "attention_mask": inp["attention_mask"].astype(np.int64)}
        dense, sparse_w = self.sess.run(["dense", "sparse_w"], besle)
        return dense[0], sparse_w[0], inp["input_ids"][0].tolist()

    def embed_sorgu(self, text):
        """Returns: dense list[float] (1024, L2-normalize), sparse dict[str, float] (token-id -> ağırlık)."""
        dense, weights, ids_list = self.ham(text)
        sparse = {}
        for tid, w in zip(ids_list, weights.tolist()):
            if tid in self.ozel or w <= 0:
                continue
            k = str(tid)
            if w > sparse.get(k, 0.0):
                sparse[k] = w
        return dense.tolist(), sparse
