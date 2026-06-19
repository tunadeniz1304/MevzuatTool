import re
from dataclasses import dataclass

_MADDE = re.compile(r"(?i)\bmadde\s+(\d+)\s*-\s*")


@dataclass
class Article:
    no: str
    body: str


def split_articles(text: str) -> list[Article]:
    matches = list(_MADDE.finditer(text))
    out: list[Article] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append(Article(no=m.group(1), body=text[start:end].strip()))
    return out


def split_fikralar(body: str) -> list[str]:
    parts = re.split(r"(?=\(\d+\)\s)", body.strip())
    return [p.strip() for p in parts if p.strip()]


def extract_status(body: str) -> str:
    return "mülga" if re.search(r"(?i)\(\s*mülga", body) else "yürürlükte"
