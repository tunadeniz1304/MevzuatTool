# -*- coding: utf-8 -*-
"""BGE-M3 sorgu embed — dense (CLS) + sparse (sparse_linear).

transformers ile (FlagEmbedding PC'de donuyor). Formüller FlagEmbedding
kaynağından birebir alındı (finetune/embedder/encoder_only/m3/modeling.py):
  - dense  : last_hidden_state[:, 0]  (CLS pooling) + L2 normalize
  - sparse : relu(sparse_linear(hidden)) -> token-id başına max ağırlık

Aynı-metin testi: transformers dense vs FlagEmbedding dense = 0.9998 (hizalı).

Model tek sefer yüklenir (lazy singleton). Sorgu embed'i hafif → CPU yeter.
"""
import torch
from transformers import AutoModel, AutoTokenizer
from huggingface_hub import hf_hub_download

_MODEL_ADI = "BAAI/bge-m3"

# Lazy singleton — ilk çağrıda yüklenir, sonra cache
_tok = None
_model = None
_sparse_linear = None


def _yukle():
    global _tok, _model, _sparse_linear
    if _model is not None:
        return
    _tok = AutoTokenizer.from_pretrained(_MODEL_ADI)
    _model = AutoModel.from_pretrained(_MODEL_ADI)
    _model.eval()
    # sparse_linear: Linear(1024 -> 1), BGE-M3 repo'sunda ayrı dosya
    sparse_path = hf_hub_download(_MODEL_ADI, "sparse_linear.pt")
    _sparse_linear = torch.nn.Linear(1024, 1)
    _sparse_linear.load_state_dict(torch.load(sparse_path, map_location="cpu"))
    _sparse_linear.eval()


def embed_sorgu(text: str, max_length: int = 8192):
    """Sorguyu dense + sparse vektöre çevir.

    Returns:
        dense  : list[float] (1024, L2-normalize)
        sparse : dict[str, float] (token-id -> ağırlık)
    """
    _yukle()
    inp = _tok(text, return_tensors="pt", truncation=True, max_length=max_length)
    with torch.no_grad():
        hidden = _model(**inp).last_hidden_state          # (1, T, 1024)
        # dense: CLS + normalize
        cls = hidden[:, 0]
        dense = torch.nn.functional.normalize(cls, dim=-1)[0].tolist()
        # sparse: relu(sparse_linear(hidden)) -> token-max
        weights = torch.relu(_sparse_linear(hidden)).squeeze(-1)[0].tolist()

    ids_list = inp["input_ids"][0].tolist()
    ozel = set(_tok.all_special_ids)   # cls/eos/pad/unk hariç
    sparse = {}
    for tid, w in zip(ids_list, weights):
        if tid in ozel or w <= 0:
            continue
        k = str(tid)
        if w > sparse.get(k, 0.0):
            sparse[k] = w
    return dense, sparse
