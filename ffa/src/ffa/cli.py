"""Command line entrypoints.

Examples:
    ffa ingest --season 2023 --season 2024
    ffa score --league configs/ppr.yaml --season 2024 --week 5 --limit 25
"""

from __future__ import annotations

from pathlib import Path

import typer

from ffa.ingest import ingest_seasons, open_warehouse
from ffa.league import load_league
from ffa.scoring import score_player_weeks

app = typer.Typer(add_completion=False, help="Fantasy football analytics pipeline.")


@app.command()
def ingest(
    season: list[int] = typer.Option(..., "--season", help="Repeatable: --season 2023 --season 2024"),
    out_dir: Path = typer.Option(Path("data/raw"), "--out-dir"),
) -> None:
    """Pull weekly stats, rosters, and schedules from nflverse to Parquet."""
    result = ingest_seasons(seasons=season, out_dir=out_dir)
    for table, n in result.rows.items():
        typer.echo(f"{table}: {n:,} rows -> {out_dir / (table + '.parquet')}")


@app.command()
def score(
    league: Path = typer.Option(..., "--league", help="Path to a league YAML"),
    season: int = typer.Option(..., "--season"),
    week: int | None = typer.Option(None, "--week", help="Restrict to one week"),
    limit: int = typer.Option(25, "--limit"),
    db: Path = typer.Option(Path("data/ffa.duckdb"), "--db"),
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir"),
) -> None:
    """Apply a league config to ingested weekly stats and print top scorers."""
    cfg = load_league(league)
    con = open_warehouse(db_path=db, raw_dir=raw_dir)
    query = "SELECT * FROM weekly WHERE season = ?"
    params: list[object] = [season]
    if week is not None:
        query += " AND week = ?"
        params.append(week)
    weekly = con.execute(query, params).df()

    if weekly.empty:
        typer.echo("No rows found. Have you run `ffa ingest` for that season?")
        raise typer.Exit(code=1)

    weekly["fantasy_points"] = score_player_weeks(weekly, cfg)
    cols = [c for c in ("player_display_name", "position", "recent_team", "week") if c in weekly.columns]
    out = weekly[[*cols, "fantasy_points"]].sort_values("fantasy_points", ascending=False).head(limit)
    typer.echo(out.to_string(index=False))


if __name__ == "__main__":
    app()
