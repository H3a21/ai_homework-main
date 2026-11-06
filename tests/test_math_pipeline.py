"""Test Math Grading Pipeline with SymPy comparison."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.math_pipeline import (
    _parse_as_sympy,
    _are_expressions_equal,
    _compare_numerically,
    _extract_numbers,
    grade_math_answer,
    grade_math_with_steps,
)


def test_extract_latex_blocks():
    from app.math_pipeline import _extract_latex_blocks
    blocks = _extract_latex_blocks('$x^{2} + 1$')
    assert 'x^{2} + 1' in blocks
    blocks = _extract_latex_blocks('$$x^{2}$$')
    assert 'x^{2}' in blocks
    assert _extract_latex_blocks('no math') == []


def test_parse_latex():
    expr = _parse_as_sympy('$x^{2} + 2x + 1$')
    assert expr is not None, "Should parse LaTeX expression"
    from sympy import symbols, simplify
    x = symbols('x')
    assert simplify(expr - (x**2 + 2*x + 1)) == 0, f"Expression mismatch: {expr}"


def test_parse_plain():
    expr = _parse_as_sympy('2 + 3')
    assert expr is not None
    from sympy import simplify
    assert simplify(expr - 5) == 0, f"Expected 5, got {expr}"


def test_parse_numeric():
    expr = _parse_as_sympy('42')
    assert expr is not None
    assert expr == 42


def test_expressions_equal():
    s = _parse_as_sympy('$x^{2} + 2x + 1$')
    e = _parse_as_sympy('$(x+1)^{2}$')
    assert s is not None and e is not None
    exact, ratio = _are_expressions_equal(s, e)
    assert exact, f"Expected exact match, got ratio={ratio}"


def test_expressions_partial():
    s = _parse_as_sympy('$x^{2} + 2x + 1$')
    e = _parse_as_sympy('$x^{2} + x + 1$')
    assert s is not None and e is not None
    exact, ratio = _are_expressions_equal(s, e)
    assert not exact, "Should not be exact"
    assert ratio < 1.0, f"Expected partial ratio < 1.0, got {ratio}"


def test_grade_exact_match():
    score, feedback = grade_math_answer(
        '$x^{2} + 2x + 1$', '$(x+1)^{2}$', 10.0
    )
    assert score == 10.0, f"Expected 10.0, got {score}"


def test_grade_empty():
    score, feedback = grade_math_answer('', '42', 10.0)
    assert score == 0.0


def test_grade_multi_step():
    score, feedback = grade_math_with_steps(
        'x+1=3;\nx=2', 'x=2', 10.0
    )
    assert score > 0, f"Expected positive score, got {score}"


def test_extract_numbers():
    assert _extract_numbers('x^{2} + 3x + 1') == [2.0, 3.0, 1.0]


def test_compare_numerically():
    r = _compare_numerically('x=42', '42')
    assert r > 0.5, f"Expected match ratio > 0.5, got {r}"


if __name__ == '__main__':
    test_extract_latex_blocks()
    print("PASS: test_extract_latex_blocks")
    test_parse_latex()
    print("PASS: test_parse_latex")
    test_parse_plain()
    print("PASS: test_parse_plain")
    test_parse_numeric()
    print("PASS: test_parse_numeric")
    test_expressions_equal()
    print("PASS: test_expressions_equal")
    test_expressions_partial()
    print("PASS: test_expressions_partial")
    test_grade_exact_match()
    print("PASS: test_grade_exact_match")
    test_grade_empty()
    print("PASS: test_grade_empty")
    test_grade_multi_step()
    print("PASS: test_grade_multi_step")
    test_extract_numbers()
    print("PASS: test_extract_numbers")
    test_compare_numerically()
    print("PASS: test_compare_numerically")
    print("\nAll tests passed!")
