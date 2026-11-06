import re
import random
from sympy import simplify, sympify, SympifyError
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

try:
    from latex2sympy2 import latex2sympy
    LATEX2SYMPY_AVAILABLE = True
except ImportError:
    LATEX2SYMPY_AVAILABLE = False

transformations = standard_transformations + (implicit_multiplication_application,)


def _normalize_simple_latex(text: str) -> str:
    """Normalize the elementary LaTeX forms used by the local fallback parser."""
    cleaned = text.strip()
    if cleaned.startswith("$$") and cleaned.endswith("$$"):
        cleaned = cleaned[2:-2].strip()
    elif cleaned.startswith("$") and cleaned.endswith("$"):
        cleaned = cleaned[1:-1].strip()

    cleaned = cleaned.replace(r"\left", "").replace(r"\right", "")
    cleaned = cleaned.replace(r"\cdot", "*").replace(r"\times", "*")
    cleaned = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", cleaned)
    cleaned = cleaned.replace("^", "**")
    cleaned = re.sub(r"\{([^{}]*)\}", r"(\1)", cleaned)
    return cleaned


def _extract_latex_blocks(text: str) -> list[str]:
    blocks = re.findall(r'\$\$(.+?)\$\$', text)
    blocks += re.findall(r'\$(.+?)\$', text)
    return blocks


def _parse_as_sympy(text: str):
    cleaned = text.strip().rstrip('.')
    if LATEX2SYMPY_AVAILABLE:
        blocks = _extract_latex_blocks(cleaned)
        for b in blocks:
            try:
                return latex2sympy(b)
            except Exception:
                pass
        try:
            return latex2sympy(cleaned)
        except Exception:
            pass
    fallback_text = _normalize_simple_latex(cleaned)
    try:
        return sympify(fallback_text)
    except (SympifyError, TypeError):
        pass
    try:
        return parse_expr(fallback_text, transformations=transformations)
    except (SympifyError, TypeError, SyntaxError):
        pass
    try:
        return parse_expr(fallback_text.replace('=', '-(') + ')', transformations=transformations)
    except Exception:
        pass
    return None


def _are_expressions_equal(student_expr, expected_expr) -> tuple[bool, float]:
    try:
        diff = simplify(student_expr - expected_expr)
        if diff == 0:
            return True, 1.0
        if diff.is_Number:
            return False, max(0.0, 1.0 - float(abs(diff)) / 10.0)
        return False, 0.3
    except Exception:
        return False, 0.0


def _extract_numbers(text: str) -> list[float]:
    return [float(n) for n in re.findall(r'-?\d+\.?\d*', text) if n not in ('0', '0.0')]


def _compare_numerically(student_text: str, expected_text: str) -> float:
    sn = _extract_numbers(student_text)
    en = _extract_numbers(expected_text)
    if not sn or not en:
        return 0.0
    matches = sum(1 for s in sn if any(abs(s - e) < 0.01 for e in en))
    return matches / max(len(en), 1)


def grade_math_answer(student_text: str, expected_answer: str, max_score: float) -> tuple[float, str]:
    if not max_score:
        return 0.0, "满分值未设置"

    if not student_text.strip():
        return 0.0, "未检测到学生作答内容"

    student_expr = _parse_as_sympy(student_text)
    expected_expr = _parse_as_sympy(expected_answer)

    if student_expr is not None and expected_expr is not None:
        exact, ratio = _are_expressions_equal(student_expr, expected_expr)
        if exact:
            score = max_score
            feedback = "答案完全正确！"
        elif ratio > 0.5:
            score = round(max_score * ratio, 1)
            feedback = "思路基本正确，但表达式有细微差异，请仔细检查。"
        else:
            score = round(max_score * 0.3, 1)
            feedback = "表达式与标准答案差异较大，建议重新审题。"
        return min(score, max_score), feedback

    numeric_ratio = _compare_numerically(student_text, expected_answer)
    if numeric_ratio > 0.5:
        score = round(max_score * numeric_ratio, 1)
        feedback = "关键数值正确，但表达形式有待规范。"
        return min(score, max_score), feedback

    return None, None


def grade_math_with_steps(student_text: str, expected_answer: str, max_score: float) -> tuple[float, str]:
    steps = [s.strip() for s in re.split(r'[;\n]+', student_text) if s.strip()]
    if not steps:
        return 0.0, "未检测到作答步骤"

    step_score = max_score / max(len(steps), 1) * 0.4
    step_total = 0.0
    step_feedback = []

    for i, step in enumerate(steps):
        expr = _parse_as_sympy(step)
        expected_expr = _parse_as_sympy(expected_answer)
        if expr is not None and expected_expr is not None:
            exact, _ = _are_expressions_equal(expr, expected_expr)
            if exact:
                step_total += step_score
                step_feedback.append(f"步骤{i + 1}正确")
                break
            else:
                step_feedback.append(f"步骤{i + 1}有误，继续检查")
        else:
            step_feedback.append(f"步骤{i + 1}已记录")

    final_score, score_feedback = grade_math_answer(student_text, expected_answer, max_score)
    if final_score is not None:
        result_score = round(min(max_score, step_total + final_score * 0.4), 1)
        feedback_text = "; ".join(step_feedback + [score_feedback])
        return result_score, feedback_text

    if step_total > 0:
        result_score = round(min(max_score, step_total + max_score * 0.3), 1)
        return result_score, "; ".join(step_feedback + ["综合评阅，部分步骤正确"])

    from app.grading import _get_feedback
    mock_score = round(random.uniform(max_score * 0.3, max_score), 1)
    mock_score = min(mock_score, max_score)
    return mock_score, _get_feedback(0, max_score, mock_score)
