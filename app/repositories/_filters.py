from sqlalchemy import or_


def str_filter(col, value: str, op: str | None):
    """Generic string filter with operator dispatch. Default: contains (ilike)."""
    match op:
        case "startswith":
            return col.ilike(f"{value}%")
        case "endswith":
            return col.ilike(f"%{value}")
        case "equal":
            return col == value
        case "different":
            return col != value
        case _:
            return col.ilike(f"%{value}%")


def multi_col_str_filter(cols: list, value: str, op: str | None):
    """Apply str_filter across multiple columns with OR logic."""
    return or_(*[str_filter(col, value, op) for col in cols])
