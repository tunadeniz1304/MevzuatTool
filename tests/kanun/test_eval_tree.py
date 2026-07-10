from kanun.eval_tree import count_tree_articles


def test_counts_madde_nodes():
    tree = "- BİRİNCİ KİTAP - x\n  - Madde No: 1 - a\n  - Madde No: 2 - b\n"
    assert count_tree_articles(tree) == 2
