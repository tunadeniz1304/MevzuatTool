import re


def count_tree_articles(tree_text: str) -> int:
    return len(re.findall(r"(?m)^\s*-\s*Madde No:\s*\d+", tree_text))
