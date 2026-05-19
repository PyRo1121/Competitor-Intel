"""Command-line interface for competitor intelligence."""

import asyncio

import structlog
import typer
from rich.console import Console
from rich.table import Table

from competitor_intel.collectors import (
    CompanyDiscoveryCollector,
    GitHubCollector,
    JobTrackingCollector,
    RSSCollector,
    SECCollector,
    WebsiteCollector,
)
from competitor_intel.core.alerts import AlertEngine
from competitor_intel.core.ingest import IngestionService
from competitor_intel.core.pipeline import PipelineRunner
from competitor_intel.core.scoring import ScoringEngine
from competitor_intel.db.session import init_db
from competitor_intel.reports import DailyBriefReporter, DiscordReporter, ObsidianReporter
from competitor_intel.settings import get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

app = typer.Typer(
    name="competitor-intel",
    help="Enterprise-grade competitive intelligence pipeline",
)
console = Console()


@app.command()
def init(
    _force: bool = typer.Option(False, "--force", help="Recreate database tables"),
):
    """Initialize the database."""
    console.print("[bold blue]Initializing database...[/]")
    engine = init_db()
    console.print(f"[bold green]Database initialized at {engine.url}[/]")


@app.command()
def collect(
    collectors: list[str] = typer.Option([], "--collector", "-c", help="Specific collectors to run"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without storing data"),
):
    """Run signal collectors."""
    console.print("[bold blue]Running signal collectors...[/]")
    
    async def _run():
        runner = PipelineRunner()
        
        all_collectors = [
            ("rss", RSSCollector),
            ("github", GitHubCollector),
            ("website", WebsiteCollector),
            ("sec", SECCollector),
            ("discovery", CompanyDiscoveryCollector),
            ("jobs", JobTrackingCollector),
        ]
        
        for name, collector_class in all_collectors:
            if not collectors or name in collectors:
                runner.register_collector(collector_class())
        
        results = await runner.run_collection()
        
        if not dry_run:
            ingest = IngestionService()
            for result in results:
                if result.status.value in ("success", "partial"):
                    pass
        
        return results
    
    results = asyncio.run(_run())
    
    table = Table(title="Collection Results")
    table.add_column("Collector", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Signals", style="yellow")
    table.add_column("Duration", style="blue")
    table.add_column("Errors", style="red")
    
    for result in results:
        table.add_row(
            result.collector_name,
            result.status.value,
            str(result.signals_collected),
            f"{result.duration_seconds:.1f}s",
            str(len(result.errors)),
        )
    
    console.print(table)


@app.command()
def report(
    type: str = typer.Option("daily", "--type", "-t", help="Report type: daily, discord, obsidian, all"),
    output: str = typer.Option("./exports", "--output", "-o", help="Output directory"),
):
    """Generate intelligence reports."""
    console.print(f"[bold blue]Generating {type} report...[/]")
    
    if type in ("daily", "all"):
        reporter = DailyBriefReporter()
        paths = reporter.generate_and_export()
        console.print(f"[green]Daily brief exported: {', '.join(str(p) for p in paths)}[/]")
    
    if type in ("discord", "all"):
        reporter = DiscordReporter()
        brief = reporter.generate_brief()
        console.print(f"[green]Discord brief generated ({len(brief['fields'])} fields)[/]")
    
    if type in ("obsidian", "all"):
        reporter = ObsidianReporter()
        paths = reporter.generate_all_notes()
        console.print(f"[green]Generated {len(paths)} Obsidian notes[/]")
    
    if type == "all":
        console.print(f"[bold green]All reports generated successfully[/]")


@app.command()
def score(
    company_id: int = typer.Option(None, "--company", "-c", help="Score specific company"),
    all_companies: bool = typer.Option(False, "--all", "-a", help="Score all companies"),
):
    """Score companies by intelligence metrics."""
    engine = ScoringEngine()
    
    if company_id:
        score = engine.score_company(company_id)
        console.print(f"\n[bold]Score for {score.get('company_name')}:[/bold]")
        console.print(f"  Composite: [green]{score.get('composite_score', 'N/A')}[/green]")
        console.print(f"  Funding: {score.get('funding_momentum', 'N/A')}")
        console.print(f"  Engineering: {score.get('engineering_velocity', 'N/A')}")
        console.print(f"  Social: {score.get('social_momentum', 'N/A')}")
        console.print(f"  Hiring: {score.get('hiring_velocity', 'N/A')}")
        console.print(f"  Market: {score.get('market_presence', 'N/A')}")
        console.print(f"  Team: {score.get('team_strength', 'N/A')}")
    elif all_companies:
        results = engine.score_all_companies()
        table = Table(title="Company Intelligence Scores")
        table.add_column("Rank", style="cyan")
        table.add_column("Company", style="green")
        table.add_column("Score", style="yellow")
        table.add_column("Funding", style="blue")
        table.add_column("Engineering", style="blue")
        table.add_column("Hiring", style="blue")
        
        for i, r in enumerate(results, 1):
            table.add_row(
                str(i),
                r.get("company_name", ""),
                f"{r.get('composite_score', 0):.1f}",
                f"{r.get('funding_momentum', 0):.1f}",
                f"{r.get('engineering_velocity', 0):.1f}",
                f"{r.get('hiring_velocity', 0):.1f}",
            )
        
        console.print(table)


@app.command()
def alerts(
    action: str = typer.Option("check", "--action", help="Action: check, create, list"),
    name: str = typer.Option(None, "--name", help="Rule name (for create)"),
    events: str = typer.Option(None, "--events", help="Event types comma-separated (for create)"),
    channel: str = typer.Option("discord", "--channel", help="Alert channel"),
):
    """Manage alert rules and check for alerts."""
    engine = AlertEngine()
    
    if action == "check":
        alerts = engine.process_unalerted_events()
        if alerts:
            console.print(f"\n[bold red]{len(alerts)} alert(s) fired:[/bold red]")
            for alert in alerts:
                console.print(f"  [{alert['channel']}] {alert['message']}")
        else:
            console.print("[green]No new alerts[/green]")
    
    elif action == "create" and name and events:
        event_list = [e.strip() for e in events.split(",")]
        rule = engine.create_rule(name, event_list, channel)
        console.print(f"[green]Alert rule created: {rule.name}[/green]")
    
    elif action == "list":
        console.print("[yellow]Alert listing not yet implemented[/yellow]")


@app.command()
def status():
    """Show pipeline status."""
    settings = get_settings()
    
    table = Table(title="Competitor Intelligence Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Database", str(settings.db.path))
    table.add_row("Log Level", settings.log_level)
    table.add_row("Max Concurrent", str(settings.collector.max_concurrent))
    table.add_row("Discord Webhook", "Configured" if settings.discord.webhook_url else "Not configured")
    table.add_row("Ollama Model", settings.ollama.model)
    table.add_row("Collectors", "6 (rss, github, website, sec, discovery, jobs)")
    
    console.print(table)


@app.command()
def pipeline():
    """Run the full pipeline."""
    console.print("[bold blue]Running full competitor intelligence pipeline...[/]")
    
    async def _run():
        runner = PipelineRunner()
        
        runner.register_collector(RSSCollector())
        runner.register_collector(GitHubCollector())
        runner.register_collector(WebsiteCollector())
        runner.register_collector(SECCollector())
        runner.register_collector(CompanyDiscoveryCollector())
        runner.register_collector(JobTrackingCollector())
        
        results = await runner.run_collection()
        return runner.get_summary()
    
    summary = asyncio.run(_run())
    
    console.print("\n[bold green]Pipeline Complete[/]")
    for key, value in summary.items():
        console.print(f"  {key}: {value}")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
