"""Faz B: 4 kanunun ham HTML'ini get_document_content ile çek + cp1254-güvenli cache.

bedesten_client paket olarak import edilir (MCP server çalıştırılmaz; public metod).
Çıktı: data/kanun/raw/html_<id>.html (UTF-8). mevcut content_<id>.md deseni gibi.

Çalıştırma: .venv/Scripts/python.exe scripts/fetch_html.py
NOT: bedesten_client mevzuat-mcp venv'inde; bu script onun python'uyla VEYA bedesten_client
PATH'e eklenerek çalıştırılır. Detay: sys.path'e mevzuat-mcp site-packages eklenir.
"""
import asyncio
import os
import sys

# mevzuat-mcp paketinin client'ına eriş (kurulu uv tool site-packages).
_MCP_SP = os.path.expandvars(r"%APPDATA%\uv\tools\mevzuat-mcp\Lib\site-packages")
if os.path.isdir(_MCP_SP):
    sys.path.insert(0, _MCP_SP)

from bedesten_client import BedestenClient  # noqa: E402

OUT_DIR = os.path.join("data", "raw")
LAWS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}


def _ensure_utf8(html: str) -> str:
    """cp1254 mojibake kontrolü: 'Ã'/'Â' veya replacement char varsa cp1254 decode dene.
    bedesten_client base64->utf-8 decode ediyor; çoğu durumda HTML zaten UTF-8.
    Mojibake işareti yoksa olduğu gibi döndür."""
    if "�" in html or "Ã" in html[:2000]:
        try:
            return html.encode("latin-1").decode("cp1254")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return html
    return html


async def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    client = BedestenClient()
    for label, mid in LAWS.items():
        doc = await client.get_document_content(mid)
        html = _ensure_utf8(doc.content or "")
        path = os.path.join(OUT_DIR, f"html_{mid}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[OK] {label} ({mid}): {len(html)} krk -> {path}")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
