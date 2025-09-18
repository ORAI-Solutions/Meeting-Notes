from __future__ import annotations

from typing import Optional
from sqlmodel import SQLModel, Field


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value_json: Optional[str] = None


