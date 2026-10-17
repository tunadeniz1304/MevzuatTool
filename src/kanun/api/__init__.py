"""Retrieval servis katmanı (Faz 6, ADR-0017): FastAPI ile `/ara` ve `/saglik`.

`/ara` iki modlu: atıf modu (kanun/madde/fıkra/bent → kesin getirme, ADR-0019) ve doğal dil modu
(3-bacak hybrid). İstek `mod` alanı: otomatik (varsayılan) | atif | dogal.
Yalnız sıralı madde döner — generation/LLM endpoint'i YOK (ADR-0001).
Çalıştır: .venv/Scripts/python.exe -m uvicorn kanun.api.app:app --app-dir src --host 127.0.0.1 --port 8000
"""
