# -*- coding: utf-8 -*-
"""BGE-M3 sorgu embedder'ı ve bge-reranker-v2-m3'ü ONNX'e export et (FP32).

ONNX = modelin hesap grafiğini (matris çarpımları, softmax, ...) framework'ten bağımsız bir dosyaya
yazan açık format. ONNX Runtime (ORT) bu grafiği torch olmadan, CPU için optimize ederek çalıştırır;
quantization (onnx_quantize.py) da bu grafik üzerinde yapılır.

Çıktılar (models/ gitignored — commit edilmez):
  models/onnx/bge-m3/model.onnx (+ model.onnx.data)              girdiler: input_ids, attention_mask
                                                                   çıktılar: dense (B,1024), sparse_w (B,T)
  models/onnx/bge-reranker-v2-m3/model.onnx (+ model.onnx.data)   çıktı: logits (B,1)
  + her klasöre tokenizer dosyaları (save_pretrained) — ORT tarafı tokenizer'ı buradan yükler.

Embedder sarmalayıcısı `embed.py`'deki formülü grafiğe gömer:
  dense    = L2normalize(last_hidden_state[:, 0])          (CLS pooling)
  sparse_w = relu(sparse_linear(last_hidden_state))         (token başına ağırlık; token-max Python'da)
FP32 model ~2.2 GB > protobuf'un 2 GB sınırı → ağırlıklar ayrı dosyaya (external data) yazılır.

Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/onnx_export.py [embed|rerank|hepsi]
"""
import os
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

import onnx
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

from kanun.retrieval.config import ayarlar_oku

EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
OPSET = 17


class EmbedSarmal(torch.nn.Module):
    """BGE-M3 + sparse_linear → (dense, sparse_w). embed.py ile aynı matematik."""

    def __init__(self, model, sparse_linear):
        super().__init__()
        self.model = model
        self.sparse_linear = sparse_linear

    def forward(self, input_ids, attention_mask):
        hidden = self.model(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        dense = torch.nn.functional.normalize(hidden[:, 0], dim=-1)
        sparse_w = torch.relu(self.sparse_linear(hidden)).squeeze(-1)
        return dense, sparse_w


def _kaydet_tek_dosya(gecici_onnx, hedef_onnx):
    """torch'un yazdığı (çok parçalı) external data'yı tek `model.onnx.data` dosyasına topla."""
    m = onnx.load(gecici_onnx, load_external_data=True)
    veri = os.path.basename(hedef_onnx) + ".data"
    for yol in (hedef_onnx, hedef_onnx + ".data"):
        if os.path.exists(yol):
            os.remove(yol)
    onnx.save_model(m, hedef_onnx, save_as_external_data=True, all_tensors_to_one_file=True,
                    location=veri, size_threshold=1024)
    onnx.checker.check_model(hedef_onnx)   # yol ile → >2GB modelde de çalışır


def _export(modul, girdiler, girdi_adlari, cikti_adlari, dinamik, hedef_onnx):
    os.makedirs(os.path.dirname(hedef_onnx), exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.path.dirname(hedef_onnx)) as tmp:
        gecici = os.path.join(tmp, "model.onnx")
        with torch.no_grad():
            torch.onnx.export(modul, girdiler, gecici, input_names=girdi_adlari,
                              output_names=cikti_adlari, dynamic_axes=dinamik,
                              opset_version=OPSET, do_constant_folding=True)
        _kaydet_tek_dosya(gecici, hedef_onnx)
    boyut = sum(os.path.getsize(p) for p in (hedef_onnx, hedef_onnx + ".data") if os.path.exists(p))
    print(f"  ✓ {hedef_onnx}  ({boyut / 1e9:.2f} GB)")


def embed_export(model_dir):
    print(f"[embed] {EMBED_MODEL} export ediliyor...")
    hedef = os.path.join(model_dir, "bge-m3", "model.onnx")
    tok = AutoTokenizer.from_pretrained(EMBED_MODEL)
    model = AutoModel.from_pretrained(EMBED_MODEL, attn_implementation="eager").eval()
    sl = torch.nn.Linear(1024, 1)
    sl.load_state_dict(torch.load(hf_hub_download(EMBED_MODEL, "sparse_linear.pt"),
                                  map_location="cpu", weights_only=True))
    sarmal = EmbedSarmal(model, sl.eval()).eval()
    ornek = tok(["kira artışı nasıl belirlenir", "memur disiplin cezası"], padding=True,
                return_tensors="pt")
    _export(sarmal, (ornek["input_ids"], ornek["attention_mask"]),
            ["input_ids", "attention_mask"], ["dense", "sparse_w"],
            {"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"},
             "dense": {0: "batch"}, "sparse_w": {0: "batch", 1: "seq"}}, hedef)
    tok.save_pretrained(os.path.dirname(hedef))


def rerank_export(model_dir):
    print(f"[rerank] {RERANK_MODEL} export ediliyor...")
    hedef = os.path.join(model_dir, "bge-reranker-v2-m3", "model.onnx")
    tok = AutoTokenizer.from_pretrained(RERANK_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        RERANK_MODEL, attn_implementation="eager").eval()

    class LogitSarmal(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask):
            return self.m(input_ids=input_ids, attention_mask=attention_mask).logits

    ornek = tok([["kira artışı", "Kira bedeli her yıl artırılır."], ["memur", "Disiplin cezası"]],
                padding=True, return_tensors="pt")
    _export(LogitSarmal(model).eval(), (ornek["input_ids"], ornek["attention_mask"]),
            ["input_ids", "attention_mask"], ["logits"],
            {"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"},
             "logits": {0: "batch"}}, hedef)
    tok.save_pretrained(os.path.dirname(hedef))


def main():
    hangisi = sys.argv[1] if len(sys.argv) > 1 else "hepsi"
    model_dir = ayarlar_oku().model_dir
    if hangisi in ("embed", "hepsi"):
        embed_export(model_dir)
    if hangisi in ("rerank", "hepsi"):
        rerank_export(model_dir)


if __name__ == "__main__":
    main()
