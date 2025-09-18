"""Model for storing source references in summaries."""

from __future__ import annotations

from typing import Optional
from sqlmodel import SQLModel, Field


class SummaryReference(SQLModel, table=True):
    """Stores references from summary to source transcript segments."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    summary_id: int = Field(index=True, foreign_key="summary.id")
    
    # Reference information
    reference_text: str  # The text being referenced
    start_ms: int  # Start timestamp in milliseconds
    end_ms: int  # End timestamp in milliseconds
    speaker: Optional[str] = None  # Speaker who said this
    
    # Context in summary
    summary_context: Optional[str] = None  # The part of summary that references this
