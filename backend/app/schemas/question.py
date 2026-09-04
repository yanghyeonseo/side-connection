from typing import Literal

from .common import CamelModel


class Question(CamelModel):
    id: str
    title: str
    description: str | None = None
    options: list[str] | None = None
    multiple: bool = False
    input: Literal["text", "number"] | None = None
