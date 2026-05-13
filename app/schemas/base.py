from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# Use this type for all monetary and rate values.
# Mirrors the Numeric(20, 8) DB constraint and validates at the API boundary.
FinancialDecimal = Annotated[Decimal, Field(max_digits=20, decimal_places=8)]

T = TypeVar("T")


class AppSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(AppSchema, Generic[T]):  # noqa: UP046
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class CursorPage(AppSchema, Generic[T]):  # noqa: UP046
    """
    Keyset-based pagination response.

    Use ``next_cursor`` as the ``after`` query parameter in the next request.
    When ``next_cursor`` is None the caller has reached the last page.
    Unlike OFFSET pagination, this stays O(K) regardless of how deep into the
    table you paginate.
    """

    items: list[T]
    next_cursor: str | None  # opaque base64-encoded composite key
