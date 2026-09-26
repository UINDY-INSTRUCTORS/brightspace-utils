"""Data structures for rubric representation."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Level:
    """A performance level (Excellent, Good, Developing, etc.)"""
    name: str
    value: float  # Numeric score (0-3 for Brightspace)
    description: str
    indicators: List[str] = field(default_factory=list)


@dataclass
class Criterion:
    """A grading criterion with multiple performance levels"""
    name: str
    weight: float  # 0.10 for 10%
    weight_pct: str  # "10%" for display
    purpose: Optional[str] = None
    levels: List[Level] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    common_issues: List[str] = field(default_factory=list)


@dataclass
class RubricData:
    """Complete rubric structure, format-agnostic"""
    title: str
    format: str  # 'abet' or 'lab'
    course: Optional[str] = None
    total_points: int = 100
    criteria: List[Criterion] = field(default_factory=list)

    @property
    def num_criteria(self) -> int:
        return len(self.criteria)

    @property
    def total_weight(self) -> float:
        """Sum of all criterion weights (should be ~1.0)"""
        return sum(c.weight for c in self.criteria)
