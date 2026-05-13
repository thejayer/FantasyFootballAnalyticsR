"""League scoring configuration.

A ``LeagueConfig`` is a plain data container loaded from a YAML file. The
scoring engine in :mod:`ffa.scoring` is a pure function over a ``LeagueConfig``
and a stats DataFrame, so any league variant (standard, PPR, half-PPR, bonuses,
IDP) is expressed as data rather than code.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, NonNegativeFloat


class YardageBonus(BaseModel):
    """A flat bonus when a stat crosses a threshold (e.g. 100+ rush yards)."""

    threshold: NonNegativeFloat
    points: float


class PassingRules(BaseModel):
    yards_per_point: NonNegativeFloat = 25.0
    td_points: float = 4.0
    int_points: float = -2.0
    two_point_conversion: float = 2.0
    bonuses: list[YardageBonus] = Field(default_factory=list)


class RushingRules(BaseModel):
    yards_per_point: NonNegativeFloat = 10.0
    td_points: float = 6.0
    two_point_conversion: float = 2.0
    bonuses: list[YardageBonus] = Field(default_factory=list)


class ReceivingRules(BaseModel):
    yards_per_point: NonNegativeFloat = 10.0
    td_points: float = 6.0
    reception_points: float = 0.0
    two_point_conversion: float = 2.0
    bonuses: list[YardageBonus] = Field(default_factory=list)


class MiscRules(BaseModel):
    fumble_lost: float = -2.0
    return_td: float = 6.0


class KickingRules(BaseModel):
    pat_made: float = 1.0
    fg_0_39: float = 3.0
    fg_40_49: float = 4.0
    fg_50_plus: float = 5.0
    fg_missed: float = 0.0


class LeagueConfig(BaseModel):
    """Top-level league config.

    All sub-rule blocks have sensible defaults so YAML can stay minimal --
    only override what differs from a standard non-PPR league.
    """

    name: str = "standard"
    passing: PassingRules = Field(default_factory=PassingRules)
    rushing: RushingRules = Field(default_factory=RushingRules)
    receiving: ReceivingRules = Field(default_factory=ReceivingRules)
    misc: MiscRules = Field(default_factory=MiscRules)
    kicking: KickingRules = Field(default_factory=KickingRules)


def load_league(path: str | Path) -> LeagueConfig:
    """Load and validate a league config from a YAML file."""
    raw = yaml.safe_load(Path(path).read_text())
    return LeagueConfig.model_validate(raw or {})
