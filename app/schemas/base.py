from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class AppSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(AppSchema, Generic[T]):  # noqa: UP046
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
