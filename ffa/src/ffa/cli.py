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
from ffa.projection import project_per_game, project_season
from ffa.scoring import score_player_weeks
from ffa.simulation import simulate_seasons, summarize_seasons

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


@app.command()
def project(
    season: int = typer.Option(..., "--season", help="Season to project."),
    lookback: int = typer.Option(3, "--lookback", help="Prior seasons to use."),
    decay: float = typer.Option(0.5, "--decay", help="Exponential recency decay."),
    expected_games: float = typer.Option(17.0, "--expected-games"),
    league: Path | None = typer.Option(None, "--league", help="If given, also score the projection."),
    limit: int = typer.Option(25, "--limit"),
    out: Path | None = typer.Option(None, "--out", help="Optional Parquet path to write the projection."),
    db: Path = typer.Option(Path("data/ffa.duckdb"), "--db"),
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir"),
) -> None:
    """Recency-weighted baseline projection from ingested weekly history."""
    con = open_warehouse(db_path=db, raw_dir=raw_dir)
    seasons = list(range(season - lookback, season))
    placeholders = ",".join("?" for _ in seasons)
    weekly = con.execute(
        f"SELECT * FROM weekly WHERE season IN ({placeholders})", seasons
    ).df()
    if weekly.empty:
        typer.echo(
            f"No weekly history found for seasons {seasons}. Run `ffa ingest` first."
        )
        raise typer.Exit(code=1)

    per_game = project_per_game(weekly, target_season=season, lookback=lookback, decay=decay)
    season_df = project_season(per_game, expected_games=expected_games)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        season_df.to_parquet(out, index=False)
        typer.echo(f"Wrote {len(season_df):,} rows -> {out}")

    if league is not None:
        cfg = load_league(league)
        season_df["fantasy_points"] = score_player_weeks(season_df, cfg)
        cols = [c for c in ("player_display_name", "position", "recent_team") if c in season_df.columns]
        out_df = (
            season_df[[*cols, "fantasy_points"]]
            .sort_values("fantasy_points", ascending=False)
            .head(limit)
        )
        typer.echo(out_df.to_string(index=False))


@app.command()
def simulate(
    league: Path = typer.Option(..., "--league", help="Path to a league YAML."),
    season: int = typer.Option(..., "--season"),
    samples: int = typer.Option(1000, "--samples", help="Bootstrap samples per player."),
    lookback: int = typer.Option(3, "--lookback"),
    decay: float = typer.Option(0.5, "--decay"),
    expected_games: float = typer.Option(17.0, "--expected-games"),
    seed: int = typer.Option(0, "--seed"),
    limit: int = typer.Option(25, "--limit"),
    out: Path | None = typer.Option(None, "--out", help="Optional Parquet path for the summary."),
    db: Path = typer.Option(Path("data/ffa.duckdb"), "--db"),
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir"),
) -> None:
    """Bootstrap distributional projections; print mean / sd / 5-95 quantiles."""
    cfg = load_league(league)
    con = open_warehouse(db_path=db, raw_dir=raw_dir)
    seasons = list(range(season - lookback, season))
    placeholders = ",".join("?" for _ in seasons)
    weekly = con.execute(
        f"SELECT * FROM weekly WHERE season IN ({placeholders})", seasons
    ).df()
    if weekly.empty:
        typer.echo(
            f"No weekly history found for seasons {seasons}. Run `ffa ingest` first."
        )
        raise typer.Exit(code=1)

    samples_df = simulate_seasons(
        weekly,
        target_season=season,
        n_samples=samples,
        lookback=lookback,
        decay=decay,
        expected_games=expected_games,
        seed=seed,
    )
    summary = summarize_seasons(samples_df, cfg)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        summary.to_parquet(out, index=False)
        typer.echo(f"Wrote {len(summary):,} rows -> {out}")

    cols = [c for c in ("player_display_name", "position", "recent_team") if c in summary.columns]
    show = [*cols, "points_mean", "points_sd", "q05", "q50", "q95"]
    show = [c for c in show if c in summary.columns]
    typer.echo(summary[show].head(limit).round(1).to_string(index=False))


if __name__ == "__main__":
    app()
