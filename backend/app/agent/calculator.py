import ast
import operator

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def safe_eval(expression: str) -> float:
    """Evaluate plain arithmetic only: numbers, + - * / and brackets. Nothing else can run."""

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        raise ValueError(f"Unsupported expression: {expression}")

    return ev(ast.parse(expression.replace(",", ""), mode="eval"))


CURRENCIES = {"rs.", "rs", "inr", "₹", "usd", "$"}


def is_money(unit: str) -> bool:
    return unit.strip().lower() in CURRENCIES


def format_amount(value: float, unit: str) -> str:
    number = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    unit = unit.strip()
    if not unit:
        return number
    return f"{unit} {number}" if is_money(unit) else f"{number} {unit}"  # Rs. 4,800 / 4 days


def show_working(expression: str) -> str:
    """'400 * 12' -> '400 × 12' so employees can check the maths."""
    return expression.replace("*", " × ").replace("/", " ÷ ").replace("  ", " ").strip()