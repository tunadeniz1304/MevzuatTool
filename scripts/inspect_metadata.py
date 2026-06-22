"""Bir mevzuatın metadata manzarasını incele (Faz 3 girdisi).

search_mevzuat (ham sonuç = liste-seviyesi metadata) + get_mevzuat_madde_tree
(hiyerarşi) + get_mevzuat_content başlığı (Kanun No/Kabul/RG/Düstur). UTF-8 dosyaya yazar.

Çalıştırma:  .venv/Scripts/python.exe scripts/inspect_metadata.py 193
"""
import asyncio
import os
import re
import shutil
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_CMD = "mevzuat-mcp"
NO = sys.argv[1] if len(sys.argv) > 1 else "193"
OUT = os.path.join("data", "raw", f"metadata_{NO}.md")


def _text(result) -> str:
    return "\n".join(getattr(c, "text", None) or str(c) for c in getattr(result, "content", []) or [])


async def main() -> None:
    cmd = shutil.which(SERVER_CMD)
    if not cmd:
        print("HATA: mevzuat-mcp PATH'te yok.")
        sys.exit(1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = [f"# Kanun {NO} — metadata manzarası\n"]

    params = StdioServerParameters(command=cmd, args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            search = _text(await session.call_tool(
                "search_mevzuat", {"mevzuat_no": NO, "mevzuat_tur": "KANUN", "page_size": 5}))
            out.append(f"\n## 1) search_mevzuat — ham sonuç (liste-seviyesi metadata)\n```\n{search}\n```\n")

            m = re.search(r"mevzuatId:\s*(\d+)", search)
            if m:
                mid = m.group(1)
                tree = _text(await session.call_tool("get_mevzuat_madde_tree", {"mevzuat_id": mid}))
                content = _text(await session.call_tool("get_mevzuat_content", {"mevzuat_id": mid}))
                out.append(f"\n## 2) get_mevzuat_madde_tree — hiyerarşi metadata (ilk 1800 karakter)\n```\n{tree[:1800]}\n```\n")
                out.append(f"\n## 3) get_mevzuat_content — başlık (header metadata: Kanun No / Kabul / RG / Düstur) (ilk 1200)\n```\n{content[:1200]}\n```\n")
                out.append(f"\n## Sayılar\n- content uzunluğu: {len(content)} karakter\n- ağaç uzunluğu: {len(tree)} karakter\n")
            else:
                out.append("\n(search sonucundan mevzuatId çıkarılamadı)\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(out))
    print(f"Yazıldı: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
