"""Adım 9-12: seçilen örneklerin get_mevzuat_content metnini çek + kaydet.

Her belge için get_mevzuat_content(mevzuat_id) → Markdown metni → data/raw/content_<id>.md.
Özet (uzunluk + ilk parça) → data/raw/content_summary.md (Read ile UTF-8 okunacak).

Çalıştırma:
    .venv/Scripts/python.exe scripts/fetch_content.py
"""
import asyncio
import os
import shutil
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_CMD = "mevzuat-mcp"
OUT_DIR = os.path.join("data", "raw")

# Kanun-only set (ADR-0013) — (etiket, mevzuatId). Hepsi mevzuat_tur=KANUN.
DOCS = [
    ("Türk Ceza Kanunu 5237 (derin)", "103228"),
    ("Vergi Usul Kanunu 213 (karışık/çok-değişiklikli)", "103006"),
    ("KVKK 6698 (düz kanun)", "104383"),
    ("Gelir Vergisi Kanunu 193 (eski; '1.' fıkra stili)", "103111"),
]


def _text(result) -> str:
    return "\n".join(getattr(c, "text", None) or str(c) for c in getattr(result, "content", []) or [])


async def main() -> None:
    cmd = shutil.which(SERVER_CMD)
    if not cmd:
        print("HATA: mevzuat-mcp PATH'te yok.")
        sys.exit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    summary = ["# Content Keşfi (Adım 9-12)\n"]

    params = StdioServerParameters(command=cmd, args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for label, mid in DOCS:
                summary.append(f"\n## {label} — id {mid}\n")
                try:
                    content = _text(await session.call_tool("get_mevzuat_content", {"mevzuat_id": mid}))
                except Exception as e:  # noqa: BLE001
                    summary.append(f"- HATA: {e!r}\n")
                    continue
                path = os.path.join(OUT_DIR, f"content_{mid}.md")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                summary.append(f"- uzunluk: {len(content)} karakter → {path}\n")
                summary.append("- ilk 900 karakter:\n```\n" + content[:900] + "\n```\n")

    out = os.path.join(OUT_DIR, "content_summary.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(summary))
    print(f"Yazıldı: {out}")
    print(f"Kaydedilen metinler: {OUT_DIR}/content_<id>.md")


if __name__ == "__main__":
    asyncio.run(main())
