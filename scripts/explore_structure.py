"""Adım 7-8 yardımcısı: aday mevzuatların YAPISINI keşfet (ADR-0011 eksen kapsaması).

Her aday için: search_mevzuat → mevzuatId → get_mevzuat_madde_tree.
Sonuçları UTF-8 bir dosyaya yazar (terminal Türkçe bozulmasını aşmak için),
ham ağaçları ayrıca kaydeder. Yapısal eksen ipuçlarını ham ağaç metninden sayar.

Çalıştırma:
    .venv/Scripts/python.exe scripts/explore_structure.py
Çıktı:
    data/raw/exploration.md           (özet — Read ile okunacak)
    data/raw/tree_<mevzuatId>.txt      (ham madde ağaçları)
"""
import asyncio
import os
import re
import shutil
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_CMD = "mevzuat-mcp"
OUT_DIR = os.path.join("data", "raw")

# (etiket, search_mevzuat argümanları) — yapısal çeşitliliği hedefleyen KANUN adayları.
# Kapsam yalnız KANUN (ADR-0013): tüm adaylarda mevzuat_tur="KANUN".
CANDIDATES = [
    ("Türk Ceza Kanunu 5237 (büyük kodifikasyon)", {"mevzuat_no": "5237", "mevzuat_tur": "KANUN", "page_size": 5}),
    ("Vergi Usul Kanunu 213 (çok değişiklikli/mülga)", {"mevzuat_no": "213", "mevzuat_tur": "KANUN", "page_size": 5}),
    ("KVKK 6698 (modern, orta boy)", {"mevzuat_no": "6698", "mevzuat_tur": "KANUN", "page_size": 5}),
    ("Gelir Vergisi Kanunu 193 (eski; '1.' fıkra stili)", {"mevzuat_no": "193", "mevzuat_tur": "KANUN", "page_size": 5}),
]

# Yapısal eksen ipuçları (ham ağaç metninde, büyük harf Türkçe biçimde aranır)
AXIS_KEYWORDS = ["KİTAP", "KISIM", "BÖLÜM", "AYIRIM", "GEÇİCİ", "EK MADDE", "MÜLGA", "MÜKERRER"]


def _text(result) -> str:
    return "\n".join(getattr(c, "text", None) or str(c) for c in getattr(result, "content", []) or [])


def _first_result_line(search_text: str) -> str:
    for ln in search_text.splitlines():
        if "mevzuatId:" in ln:
            return ln.strip()
    return ""


def _mevzuat_id(line: str):
    m = re.search(r"mevzuatId:\s*(\d+)", line)
    return m.group(1) if m else None


async def main() -> None:
    cmd = shutil.which(SERVER_CMD)
    if not cmd:
        print("HATA: mevzuat-mcp PATH'te yok. uv tool install yaptın mı?")
        sys.exit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = ["# Aday Mevzuat Yapı Keşfi (Adım 7-8)\n"]

    params = StdioServerParameters(command=cmd, args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for label, args in CANDIDATES:
                lines.append(f"\n## {label}\n")
                try:
                    search_text = _text(await session.call_tool("search_mevzuat", args))
                except Exception as e:  # noqa: BLE001
                    lines.append(f"- search HATASI: {e!r}\n")
                    continue
                hit = _first_result_line(search_text)
                mid = _mevzuat_id(hit)
                lines.append(f"- bulunan: {hit or '(sonuç yok)'}\n")
                if not mid:
                    continue
                try:
                    tree = _text(await session.call_tool("get_mevzuat_madde_tree", {"mevzuat_id": mid}))
                except Exception as e:  # noqa: BLE001
                    lines.append(f"- madde_tree HATASI: {e!r}\n")
                    continue
                counts = {k: tree.count(k) for k in AXIS_KEYWORDS}
                hits = {k: v for k, v in counts.items() if v}
                has_slash = bool(re.search(r"MADDE\s*\d+\s*/\s*[A-ZÇĞİÖŞÜ]", tree))
                lines.append(f"- mevzuatId: {mid} | ağaç uzunluğu: {len(tree)} karakter\n")
                lines.append(f"- eksen ipuçları: {hits or '—'} | 5/A tipi numara: {has_slash}\n")
                lines.append("- ağaç ilk 1200 karakter:\n")
                lines.append("```\n" + tree[:1200] + "\n```\n")
                with open(os.path.join(OUT_DIR, f"tree_{mid}.txt"), "w", encoding="utf-8") as f:
                    f.write(tree)

    out_path = os.path.join(OUT_DIR, "exploration.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    print(f"Yazıldı: {out_path}")
    print(f"Kaydedilen ham ağaçlar: {OUT_DIR}/tree_*.txt")


if __name__ == "__main__":
    asyncio.run(main())
