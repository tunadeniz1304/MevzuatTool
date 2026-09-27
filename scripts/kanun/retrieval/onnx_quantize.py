# -*- coding: utf-8 -*-
"""ONNX FP32 → dinamik int8 (ORT `quantize_dynamic`, QInt8, per-channel) — ADR-0016.

Quantization = ağırlıkları 32-bit float yerine 8-bit tamsayı (+ ölçek) olarak saklamak: model ~4×
küçülür, CPU'da int8 matris çarpımı (VNNI/AVX2 komutları) FP32'den hızlıdır. Bedeli: küçük sayısal hata.
  - DİNAMİK int8: yalnız AĞIRLIKLAR önceden int8'e çevrilir; aktivasyonların (ara çıktıların) ölçeği
    her çağrıda çalışma anında hesaplanır → kalibrasyon verisi GEREKMEZ.
  - STATİK int8 (kapsam dışı, V-6): aktivasyon ölçekleri de önceden bir kalibrasyon setiyle sabitlenir.
  - per_channel: her çıkış kanalı (matris satırı) kendi ölçeğini alır → tek ölçekten daha az hata.

Çıktı: aynı klasörde `model.int8.onnx` (< 2 GB → tek dosya). Boyutlar raporlanır.
Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/onnx_quantize.py [embed|rerank|hepsi]
          ek ortam: QUANT_HARIC="dugum1,dugum2" (quantize edilmeyecek düğümler, blokaj yedeği)
"""
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from onnxruntime.quantization import QuantType, quantize_dynamic

from kanun.retrieval.config import ayarlar_oku

KLASORLER = {"embed": "bge-m3", "rerank": "bge-reranker-v2-m3"}


def _boyut(yol):
    return sum(os.path.getsize(p) for p in (yol, yol + ".data") if os.path.exists(p))


def quantize(klasor):
    girdi = os.path.join(klasor, "model.onnx")
    cikti = os.path.join(klasor, "model.int8.onnx")
    haric = [d for d in os.environ.get("QUANT_HARIC", "").split(",") if d]
    print(f"[quant] {girdi} → {cikti}" + (f"  (hariç: {haric})" if haric else ""))
    quantize_dynamic(girdi, cikti, weight_type=QuantType.QInt8, per_channel=True,
                     nodes_to_exclude=haric or None,
                     extra_options={"MatMulConstBOnly": True})
    a, b = _boyut(girdi), _boyut(cikti)
    print(f"  FP32 {a / 1e9:.2f} GB → int8 {b / 1e9:.2f} GB  ({a / b:.1f}× küçük)")


def main():
    hangisi = sys.argv[1] if len(sys.argv) > 1 else "hepsi"
    model_dir = ayarlar_oku().model_dir
    for ad, alt in KLASORLER.items():
        if hangisi in (ad, "hepsi"):
            quantize(os.path.join(model_dir, alt))


if __name__ == "__main__":
    main()
