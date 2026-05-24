#!/usr/bin/env python3
"""
Hermes Competitor Intelligence Discord Bot
Provides slash commands for on-demand intelligence operations.

Setup:
1. Create a Discord bot at https://discord.com/developers/applications
2. Enable "Message Content Intent" and "Slash Commands"
3. Invite bot with scopes: bot, applications.commands
4. Set DISCORD_BOT_TOKEN env var
5. Run: python3 discord_bot.py

Commands:
    /intel daily      — Generate and post daily brief
    /intel status     — Show pipeline status
    /intel collect    — Run all collectors now
    /intel companies  — List tracked companies
    /intel signals    — Show recent signals
    /intel search <query> — Search intelligence database
"""

import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

from ci_paths import MONOREPO_ROOT, ensure_app_paths

ensure_app_paths()

logger = logging.getLogger("discord_bot")

from db.connection import get_conn

# discord.py is optional — graceful degradation if not installed
try:
    import discord
    from discord import app_commands
    from discord.ext import commands

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    logger.warning("discord.py not installed. Bot commands unavailable.")
    logger.warning("Install: pip install discord.py")

# Bot configuration
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
COMMAND_GUILD_ID = os.getenv("DISCORD_GUILD_ID")  # Optional: restrict to one guild for faster sync

if COMMAND_GUILD_ID:
    try:
        COMMAND_GUILD_ID = int(COMMAND_GUILD_ID)
    except ValueError:
        COMMAND_GUILD_ID = None


def get_db_stats() -> dict:
    """Get current database statistics."""
    conn = get_conn()
    cursor = conn.cursor()
    stats = {}

    cursor.execute("SELECT COUNT(*) FROM companies")
    stats["companies"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM intelligence_events")
    stats["events"] = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM raw_signals WHERE detected_at >= datetime('now', '-24 hours')"
    )
    stats["signals_24h"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM funding_rounds")
    stats["funding_rounds"] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM intelligence_events
        WHERE created_at >= datetime('now', '-24 hours')
    """)
    stats["events_24h"] = cursor.fetchone()[0]

    conn.close()
    return stats


def get_recent_signals(limit: int = 10) -> list:
    """Get recent intelligence signals."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.name, ie.event_type, ie.amount_usd, ie.source, ie.created_at
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        ORDER BY ie.created_at DESC
        LIMIT ?
    """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_companies_list(limit: int = 20) -> list:
    """Get list of tracked companies."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name, industry, github_stars, score, status
        FROM companies
        ORDER BY score DESC NULLS LAST, github_stars DESC
        LIMIT ?
    """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def run_collector_script(script_name: str) -> tuple[bool, str]:
    """Run a collector script and return success + output."""
    script_path = MONOREPO_ROOT / "collectors" / script_name
    if not script_path.exists():
        # Try root directory
        script_path = MONOREPO_ROOT / script_name

    if not script_path.exists():
        return False, f"Script not found: {script_name}"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(MONOREPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, result.stdout[-500:] if result.stdout else "Completed successfully"
        else:
            return False, result.stderr[-500:] if result.stderr else "Unknown error"
    except subprocess.TimeoutExpired:
        return False, "Timeout after 120s"
    except Exception as e:
        return False, str(e)


def generate_daily_brief_embed() -> dict[str, Any]:
    """Generate a Discord embed for the daily brief."""
    stats = get_db_stats()
    signals = get_recent_signals(5)

    embed: dict[str, Any] = {
        "title": "📡 Daily Competitor Intelligence Brief",
        "description": f"Database: {stats['companies']} companies, {stats['events']} events",
        "color": 0x00D4AA,
        "timestamp": datetime.now(UTC).isoformat(),
        "fields": [],
    }

    # Recent events
    events_text = []
    for row in signals:
        company, event_type, amount, source, created = row
        company = company or "Unknown"
        amt_str = f"${amount / 1_000_000:.1f}M" if amount else "Undisclosed"
        events_text.append(f"**{company}**: {event_type} ({amt_str})")

    if events_text:
        embed["fields"].append(
            {"name": "Recent Events", "value": "\n".join(events_text[:5]), "inline": False}
        )

    embed["fields"].append(
        {
            "name": "Stats (24h)",
            "value": f"Signals: {stats['signals_24h']}\nEvents: {stats['events_24h']}",
            "inline": True,
        }
    )

    embed["footer"] = {"text": "Hermes Competitor Intel • Use /intel for commands"}
    return embed


class IntelBot(commands.Bot):
    """Discord bot for competitor intelligence."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        """Register slash commands."""
        # Create command group
        self.intel_group = app_commands.Group(
            name="intel",
            description="Competitor intelligence commands",
        )

        @self.intel_group.command(
            name="daily", description="Generate and post daily intelligence brief"
        )
        async def intel_daily(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)

            embed_data = generate_daily_brief_embed()
            embed = discord.Embed.from_dict(embed_data)

            await interaction.followup.send(embed=embed)

        @self.intel_group.command(name="status", description="Show pipeline and database status")
        async def intel_status(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)

            stats = get_db_stats()

            embed = discord.Embed(
                title="📊 Competitor Intelligence Status",
                color=0x5865F2,
                timestamp=datetime.now(UTC),
            )

            embed.add_field(
                name="Database",
                value=(
                    f"Companies: {stats['companies']}\n"
                    f"Events: {stats['events']}\n"
                    f"Funding rounds: {stats['funding_rounds']}"
                ),
                inline=True,
            )
            embed.add_field(
                name="Last 24h",
                value=f"Signals: {stats['signals_24h']}\nEvents: {stats['events_24h']}",
                inline=True,
            )
            embed.add_field(
                name="Commands",
                value="""`/intel daily` — Daily brief
`/intel collect` — Run collectors
`/intel companies` — List companies
`/intel signals` — Recent signals
`/intel search <query>` — Search DB""",
                inline=False,
            )
            embed.set_footer(text="Hermes Competitor Intel")

            await interaction.followup.send(embed=embed)

        @self.intel_group.command(name="collect", description="Run all signal collectors now")
        async def intel_collect(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)

            collectors = [
                "rss_collector.py",
                "github_signals.py",
                "website_monitor.py",
                "funding_collector.py",
                "big_deals_collector.py",
            ]

            results = []
            for script in collectors:
                success, output = run_collector_script(script)
                status = "✅" if success else "❌"
                results.append(f"{status} {script}")

            embed = discord.Embed(
                title="🔄 Collector Run Complete",
                description="\n".join(results),
                color=0x00D4AA,
                timestamp=datetime.now(UTC),
            )
            embed.set_footer(text="Hermes Competitor Intel")

            await interaction.followup.send(embed=embed)

        @self.intel_group.command(name="companies", description="List tracked companies")
        async def intel_companies(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)

            companies = get_companies_list(15)

            lines = []
            for name, _industry, stars, score, _status in companies:
                score_str = f" ({score:.1f})" if score else ""
                stars_str = f" ⭐{stars:,}" if stars else ""
                lines.append(f"• **{name}**{score_str}{stars_str}")

            embed = discord.Embed(
                title="🏢 Tracked Companies",
                description="\n".join(lines) if lines else "No companies found.",
                color=0x5865F2,
                timestamp=datetime.now(UTC),
            )
            embed.set_footer(text=f"Top 15 of {get_db_stats()['companies']} total")

            await interaction.followup.send(embed=embed)

        @self.intel_group.command(name="signals", description="Show recent intelligence signals")
        async def intel_signals(interaction: discord.Interaction, limit: int = 5):
            await interaction.response.defer(thinking=True)

            signals = get_recent_signals(min(limit, 10))

            lines = []
            for company, event_type, amount, source, created in signals:
                company = company or "Unknown"
                amt_str = f"${amount / 1_000_000:.1f}M" if amount else "Undisclosed"
                created[:10] if created else "recent"
                lines.append(f"• **{company}**: {event_type} — {amt_str} ({source or 'unknown'})")

            embed = discord.Embed(
                title="📡 Recent Signals",
                description="\n".join(lines) if lines else "No recent signals.",
                color=0x00D4AA,
                timestamp=datetime.now(UTC),
            )
            embed.set_footer(text="Hermes Competitor Intel")

            await interaction.followup.send(embed=embed)

        @self.intel_group.command(name="search", description="Search the intelligence database")
        async def intel_search(interaction: discord.Interaction, query: str):
            await interaction.response.defer(thinking=True)

            conn = get_conn()
            cursor = conn.cursor()

            # Search companies
            cursor.execute(
                """
                SELECT name, description, industry FROM companies
                WHERE name LIKE ? OR description LIKE ?
                LIMIT 5
            """,
                (f"%{query}%", f"%{query}%"),
            )
            companies = cursor.fetchall()

            # Search events
            cursor.execute(
                """
                SELECT c.name, ie.event_type, ie.amount_usd, ie.source
                FROM intelligence_events ie
                LEFT JOIN companies c ON c.id = ie.company_id
                WHERE ie.event_type LIKE ? OR c.name LIKE ?
                ORDER BY ie.created_at DESC
                LIMIT 5
            """,
                (f"%{query}%", f"%{query}%"),
            )
            events = cursor.fetchall()
            conn.close()

            embed = discord.Embed(
                title=f"🔍 Search: '{query}'", color=0x5865F2, timestamp=datetime.now(UTC)
            )

            if companies:
                company_lines = [f"• **{c[0]}** ({c[2] or 'Unknown'})" for c in companies]
                embed.add_field(name="Companies", value="\n".join(company_lines), inline=False)

            if events:
                event_lines = []
                for company, event_type, amount, _source in events:
                    company = company or "Unknown"
                    amt_str = f"${amount / 1_000_000:.1f}M" if amount else "Undisclosed"
                    event_lines.append(f"• **{company}**: {event_type} ({amt_str})")
                embed.add_field(name="Events", value="\n".join(event_lines), inline=False)

            if not companies and not events:
                embed.description = "No results found."

            embed.set_footer(text="Hermes Competitor Intel")
            await interaction.followup.send(embed=embed)

        # Register the command group
        if COMMAND_GUILD_ID:
            self.tree.add_command(self.intel_group, guild=discord.Object(id=COMMAND_GUILD_ID))
        else:
            self.tree.add_command(self.intel_group)

        await self.tree.sync()

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info("Bot logged in as %s (ID: %s)", self.user.name, self.user.id)
        logger.info("Guilds: %s", len(self.guilds))
        logger.info(
            "Commands: /intel daily | /intel status | /intel collect | "
            "/intel companies | /intel signals | /intel search"
        )


def main():
    """Run the Discord bot."""
    if not DISCORD_AVAILABLE:
        logger.error("discord.py not installed. Run: pip install discord.py")
        return 1

    if not BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not set in environment")
        logger.error("Get one at: https://discord.com/developers/applications")
        return 1

    bot = IntelBot()
    bot.run(BOT_TOKEN)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    sys.exit(main())
