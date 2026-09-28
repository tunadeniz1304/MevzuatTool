# -*- coding: utf-8 -*-
"""ONNX FP32 → dinamik int8 (ORT `quantize_dynamic`, QInt8, per-channel) — ADR-0016.

Quantization = ağırlıkları 32-bit float yerine 8-bit tamsayı (+ ölçek) olarak saklamak: model ~4×
küçülür, CPU'da int8 matris çarpımı (VNNI/AVX2 komutları) FP32'den hızlıdır. Bedeli: küçük sayısal hata.
  - DİNAMİK int8: yalnız AĞIRLIKLAR önceden int8'e çevrilir; aktivasyonların (ara çıktıların) ölçeği
    her çağrıda çalışma anında hesaplanır → kalibrasyon verisi GEREKMEZ.
  - STATİK int8 (kapsam dışı, V-6): aktivasyon ölçekleri de önceden bir kalibrasyon setiyle sabitlenir.
  - per_channel: her çıkış kanalı (matris satırı) kendi ölçeğini alır → tek ölçekten daha az hata.

Karma hassasiyet (ADR-0016): tüm MatMul'ları int8 yapmak BGE-M3 dense'inde torch'a kosinüsü 0.985'e
düşürdü (< 0.99 eşiği). Deney (40 sorgu): Gather/embedding hariç 0.985 (etkisiz), FFN çıkışları hariç 0.990,
ilk 4 katman hariç 0.985, SON 4 katman hariç 0.991 (0.72 GB), son 6 hariç 0.994 (0.80 GB). Hata son katmanlarda
birikiyor (CLS vektörü doğrudan son katmandan çıkar) → embed'de son HARIC_SON_KATMAN transformer katmanı FP32
kalır. Reranker'da tam int8 yeterli (top-10 kesişimi ≥ 0.9).

Çıktı: aynı klasörde `model.int8.onnx` (< 2 GB → tek dosya). Boyutlar raporlanır.
Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/onnx_quantize.py [embed|rerank|hepsi]
          ek ortam: QUANT_HARIC="dugum1,dugum2" (ek hariç düğümler), QUANT_HARIC_SON_EMBED=4 (vars.)
"""
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from onnxruntime.quantization import QuantType, quantize_dynamic

from kanun.retrieval.config import ayarlar_oku

KLASORLER = {"embed": "bge-m3", "rerank": "bge-reranker-v2-m3"}
KATMAN_SAYISI = 24   # XLM-RoBERTa-large
KATMAN_MATMUL = ("attention/self/query/MatMul", "attention/self/key/MatMul", "attention/self/value/MatMul",
                 "attention/output/dense/MatMul", "intermediate/dense/MatMul", "output/dense/MatMul")


def son_katman_dugumleri(onek, k):
    """Son k transformer katmanının ağırlıklı MatMul düğüm adları (torch.onnx.export adlandırması)."""
    return [f"{onek}/encoder/layer.{i}/{p}" for i in range(KATMAN_SAYISI - k, KATMAN_SAYISI)
            for p in KATMAN_MATMUL]


def _boyut(yol):
    return sum(os.path.getsize(p) for p in (yol, yol + ".data") if os.path.exists(p))


def quantize(klasor, son_k=0, onek="/model"):
    girdi = os.path.join(klasor, "model.onnx")
    cikti = os.path.join(klasor, "model.int8.onnx")
    haric = [d for d in os.environ.get("QUANT_HARIC", "").split(",") if d]
    haric += son_katman_dugumleri(onek, son_k)
    print(f"[quant] {girdi} → {cikti}" + (f"  (FP32 kalan: son {son_k} katman, {len(haric)} düğüm)"
                                          if haric else ""))
    quantize_dynamic(girdi, cikti, weight_type=QuantType.QInt8, per_channel=True,
                     nodes_to_exclude=haric or None,
                     extra_options={"MatMulConstBOnly": True})
    a, b = _boyut(girdi), _boyut(cikti)
    print(f"  FP32 {a / 1e9:.2f} GB → int8 {b / 1e9:.2f} GB  ({a / b:.1f}× küçük)")


def main():
    hangisi = sys.argv[1] if len(sys.argv) > 1 else "hepsi"
    model_dir = ayarlar_oku().model_dir
    son_embed = int(os.environ.get("QUANT_HARIC_SON_EMBED", "4"))
    for ad, alt in KLASORLER.items():
        if hangisi in (ad, "hepsi"):
            # embed sarmalayıcısında modül adı "model", reranker LogitSarmal'da "m" → onek "/m/roberta"
            quantize(os.path.join(model_dir, alt), son_k=son_embed if ad == "embed" else 0)


if __name__ == "__main__":
    main()
