"""Regression tests: unary minus must be counted by every AST walker.

Reversal-style factors such as ``-TS_SUM(DELAY($return, 1), 5)`` parse to a
``UnaryOpNode`` root. Before the fix, every tree walker returned 0 for that
node, so the complexity regulator rejected the expression with "no nodes".
"""
from quantaalpha.factors.coder import factor_ast as fa


REVERSAL = "-TS_SUM(DELAY($return, 1), 5)"
PLAIN = "TS_SUM(DELAY($return, 1), 5)"
NESTED = "TS_SUM(-$return, 5)"
GROUPED = "-($close/DELAY($close,5)-1)"


def test_leading_unary_minus_counts_root_node():
    assert fa.count_all_nodes(PLAIN) == 5
    assert fa.count_all_nodes(REVERSAL) == fa.count_all_nodes(PLAIN) + 1


def test_unary_minus_preserves_constants_and_variables():
    assert fa.count_free_args(REVERSAL) == 2
    assert fa.count_unique_vars(REVERSAL) == 1
    assert fa.count_base_features(REVERSAL) == 1


def test_nested_unary_minus_is_walked():
    assert fa.count_all_nodes(NESTED) == 4
    assert fa.count_unique_vars(NESTED) == 1
    assert fa.count_base_features(NESTED) == 1


def test_grouped_unary_minus_is_walked():
    assert fa.count_all_nodes(GROUPED) == 8
    assert fa.count_free_args(GROUPED) == 2
    assert fa.count_unique_vars(GROUPED) == 1


def test_unary_subtree_matching():
    match = fa.compare_expressions(REVERSAL, REVERSAL)
    assert match is not None and match.size == 6
    partial = fa.compare_expressions(REVERSAL, PLAIN)
    assert partial is not None and partial.size == 5
