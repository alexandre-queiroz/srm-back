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
