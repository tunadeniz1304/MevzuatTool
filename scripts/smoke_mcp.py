"""Smoke test — yerel mevzuat-mcp MCP server'ına bağlan, araçları listele, bir arama dene.

Amaç (ADR-0012): "veri çekebiliyoruz" kanıtı. Server stdio ile spawn edilir;
araç listesi + ilgilendiğimiz araçların input şeması (canlı server'dan kesin doğru
parametreler) yazdırılır; sonra search_mevzuat denenir.

Çalıştırma:
    .venv/Scripts/python.exe scripts/smoke_mcp.py
Önkoşul:
    uv tool install git+https://github.com/saidsurucu/mevzuat-mcp
"""
import asyncio
import json
import shutil
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_CMD = "mevzuat-mcp"
WANTED_TOOLS = ("search_mevzuat", "get_mevzuat_madde_tree", "get_mevzuat_content")


def _text(result) -> str:
    """CallToolResult içeriğini düz metne çevir."""
    parts = []
    for c in getattr(result, "content", []) or []:
        parts.append(getattr(c, "text", None) or str(c))
    return "\n".join(parts)


async def main() -> None:
    cmd = shutil.which(SERVER_CMD)
    if not cmd:
        print(f"HATA: '{SERVER_CMD}' PATH'te yok. Önce: uv tool install git+https://github.com/saidsurucu/mevzuat-mcp")
        sys.exit(1)
    print(f"Server komutu: {cmd}\n")

    params = StdioServerParameters(command=cmd, args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) Araç listesi — bağlantı kanıtı + ground truth
            tools = (await session.list_tools()).tools
            print(f"=== {len(tools)} araç bulundu ===")
            for t in tools:
                print("  -", t.name)
            print()

            # 2) İlgilendiğimiz araçların input şeması
            by_name = {t.name: t for t in tools}
            for name in WANTED_TOOLS:
                t = by_name.get(name)
                if t is None:
                    print(f"(UYARI: '{name}' listede yok — isim değişmiş olabilir)\n")
                    continue
                print(f"--- {name} inputSchema ---")
                print(json.dumps(t.inputSchema, ensure_ascii=False, indent=2))
                print()

            # 3) search_mevzuat smoke call (argüman tahmini; hata olursa şemadan düzeltiriz)
            print("=== search_mevzuat denemesi (phrase) ===")
            try:
                res = await session.call_tool(
                    "search_mevzuat",
                    {"phrase": "kişisel verilerin korunması", "page_size": 5},
                )
                print(_text(res)[:2000])
            except Exception as e:  # noqa: BLE001 — smoke test, hatayı görmek istiyoruz
                print("search_mevzuat hatası (argümanı şemaya göre düzelteceğiz):", repr(e))


if __name__ == "__main__":
    asyncio.run(main())
