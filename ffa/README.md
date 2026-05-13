# ffa: fantasy football analytics, rebuilt

A modern replacement for the R scripts in this repo. Phases 1-2 of the
proposed rebuild are in:

1. **Ingest + scoring engine** -- nflverse data and pure-function scoring
   driven by YAML league configs.
2. **Baseline projection model** -- recency-weighted per-game stats with
   optional depth-chart adjustment.

No optimizer or dashboard yet.

## Why this exists

The legacy R pipeline depends on scraping ~15 projection sites whose HTML
shifts every season. This package replaces that with a single ingest from
[nflverse](https://github.com/nflverse) (via `nfl_data_py`) and a pure
scoring engine driven by a YAML league config -- so the data layer stops
breaking and league variants stop being code changes.

## Quick start

```bash
cd ffa
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the test suite (no network required)
pytest

# Pull two seasons of weekly stats
ffa ingest --season 2023 --season 2024

# Score 2024 week 5 under PPR rules, top 25
ffa score --league configs/ppr.yaml --season 2024 --week 5

# Baseline 2025 projection from the last 3 seasons, scored under PPR
ffa project --season 2025 --lookback 3 --league configs/ppr.yaml
```

## Layout

```
ffa/
  configs/            League scoring YAMLs (standard, ppr, half_ppr, ...)
  src/ffa/
    league.py         Pydantic schema; load_league(path) -> LeagueConfig
    scoring.py        Pure: score_player_weeks(stats_df, league) -> Series
    projection.py     project_per_game / project_season + depth-chart helpers
    ingest.py         nfl_data_py -> Parquet; DuckDB views over the Parquet
    cli.py            `ffa ingest`, `ffa score`, `ffa project`
  tests/              Pytest; runs offline on synthetic frames
```

## Design notes

- **Scoring is a pure function.** `score_player_weeks` takes a DataFrame and a
  `LeagueConfig`, returns a Series, and never mutates its input. League
  variants (PPR, half-PPR, bonuses, 6pt pass TDs) are pure data; no `if
  league.name == "ppr"` branches anywhere in the code.
- **Stat column names match `nfl_data_py.import_weekly_data`.** Missing
  columns are silently treated as zero so the same engine scores both
  per-game actuals and projection frames that only carry a subset of stats.
- **Storage is Parquet + DuckDB views.** The `.duckdb` file is tiny; the data
  lives in Parquet on disk, refreshable via `ffa ingest` and inspectable by
  any tool that speaks Parquet.

## Projection model (phase 2)

`project_per_game(weekly_df, target_season, lookback=3, decay=0.5)` returns
recency-weighted per-game stats. The weight for season `s` is
`exp(-decay * (target_season - s))`, applied to both the stat totals and the
game count -- so a player who only suited up for 5 games gets proportionally
less pull than someone who played a full year, but recent seasons still
dominate.

`apply_depth_multiplier(projections, depth_chart)` is an opt-in role shift:
multiply per-game stats by a position/depth-slot factor (e.g. WR4 -> 0.25).
Useful when a player's role is changing for the upcoming season; not a
default, because recency-weighted projections already reflect past roles.

`project_season(per_game, expected_games=17.0)` produces season totals;
`expected_games` may be a Series for per-player injury overrides.

The next phase replaces the recency-weighted mean with a learned per-stat
distribution (trained on PBP) so risk and confidence intervals come out
natively rather than as a hack on top of pundit disagreement.

## Future phases

- Phase 3: learned per-stat model -> stat distributions -> risk/CIs from
  posterior quantiles.
- Phase 4: ILP roster optimizer (PuLP/OR-Tools), Monte Carlo draft sim.
- Phase 5: Streamlit dashboard + nightly GitHub Actions refresh.
