# ffa: fantasy football analytics, rebuilt

A modern replacement for the R scripts in this repo. Step 1 of the
[proposed rebuild](../README.md): **ingest + scoring engine + tests**. No
projection model or optimizer yet -- those come in later phases.

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
```

## Layout

```
ffa/
  configs/            League scoring YAMLs (standard, ppr, half_ppr, ...)
  src/ffa/
    league.py         Pydantic schema; load_league(path) -> LeagueConfig
    scoring.py        Pure: score_player_weeks(stats_df, league) -> Series
    ingest.py         nfl_data_py -> Parquet; DuckDB views over the Parquet
    cli.py            `ffa ingest` and `ffa score`
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

## Next phases (not yet implemented)

1. Projection model: per-stat distributions from a model trained on PBP.
2. VOR, tiers, and confidence intervals derived from the model's posterior.
3. ILP roster optimizer (PuLP/OR-Tools) and Monte Carlo draft simulator.
4. Streamlit dashboard + nightly GitHub Actions refresh.
