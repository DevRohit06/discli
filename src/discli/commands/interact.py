import json
import re

import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_channel


@click.group("interact")
def interact_group():
    """Interactive components — modals, workflows, dashboards."""


# ---------------------------------------------------------------------------
# interact modal
# ---------------------------------------------------------------------------


@interact_group.command("modal")
@click.argument("title")
@click.option(
    "--field", "-f",
    "fields",
    multiple=True,
    help='Field spec: "Label:style:required" (style=short|paragraph, required=required|optional).',
)
@click.option("--channel", required=True, help="Channel name or ID to send the button.")
@click.option("--server", default=None, help="Server name or ID (optional).")
@click.pass_context
def interact_modal(ctx, title, fields, channel, server):
    """Send a button that triggers a modal form."""

    def action(client):
        async def _action(client):
            from discli.interact_engine import InteractEngine

            ch = resolve_channel(client, channel)

            # Parse field specs
            parsed_fields = []
            for spec in fields:
                parts = spec.split(":")
                label = parts[0]
                style = parts[1] if len(parts) > 1 else "short"
                required = (parts[2].lower() == "required") if len(parts) > 2 else True
                parsed_fields.append({
                    "label": label,
                    "style": style,
                    "required": required,
                })

            title_slug = re.sub(r"[^a-z0-9_]", "_", title.lower())
            custom_id = f"modal:cli_{title_slug}"

            modal = InteractEngine.build_modal(
                title=title,
                custom_id=custom_id,
                fields=parsed_fields,
            )

            # Create a view with a button that triggers the modal
            view = discord.ui.View(timeout=None)
            btn = discord.ui.Button(
                label=title,
                style=discord.ButtonStyle.primary,
                custom_id=custom_id,
            )
            view.add_item(btn)

            msg = await ch.send(
                content=f"Click the button below to open the **{title}** form.",
                view=view,
            )

            data = {
                "message_id": str(msg.id),
                "channel_id": str(ch.id),
                "title": title,
                "fields": parsed_fields,
            }
            output(
                ctx,
                data,
                plain_text=(
                    f"Modal button sent (message_id={msg.id}, channel={ch.name})\n"
                    f"Title: {title}\n"
                    f"Fields: {', '.join(f['label'] for f in parsed_fields)}"
                ),
            )

        return _action(client)

    run_discord(ctx, action)


# ---------------------------------------------------------------------------
# interact workflow
# ---------------------------------------------------------------------------


@interact_group.group("workflow")
def workflow_group():
    """Manage interactive workflows."""


@workflow_group.command("start")
@click.argument("definition_file", type=click.Path(exists=True))
@click.option("--channel", required=True, help="Channel name or ID.")
@click.option("--user", "user_id", required=True, help="Target user ID.")
@click.pass_context
def workflow_start(ctx, definition_file, channel, user_id):
    """Start a workflow from a JSON definition file."""

    def action(client):
        async def _action(client):
            from discli.interact_engine import (
                InteractEngine,
                WorkflowDefinition,
                WorkflowStep,
            )

            with open(definition_file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)

            steps = [
                WorkflowStep(
                    step_id=s["step_id"],
                    step_type=s["step_type"],
                    content=s.get("content", ""),
                    components=s.get("components", []),
                    fields=s.get("fields", []),
                    next=s.get("next"),
                    timeout=s.get("timeout", 300),
                )
                for s in raw.get("steps", [])
            ]
            definition = WorkflowDefinition(
                workflow_id=raw["workflow_id"],
                steps=steps,
            )

            ch = resolve_channel(client, channel)
            engine = InteractEngine()
            workflow_key = await engine.workflow_start(ch, user_id, definition)

            data = {"workflow_key": workflow_key}
            output(
                ctx,
                data,
                plain_text=f"Workflow started (key={workflow_key})",
            )

        return _action(client)

    run_discord(ctx, action)


# ---------------------------------------------------------------------------
# interact dashboard
# ---------------------------------------------------------------------------


@interact_group.group("dashboard")
def dashboard_group():
    """Manage interactive dashboards."""


@dashboard_group.command("create")
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("--channel", required=True, help="Channel name or ID.")
@click.pass_context
def dashboard_create(ctx, spec_file, channel):
    """Create a dashboard from a JSON spec file."""

    def action(client):
        async def _action(client):
            from discli.interact_engine import (
                InteractEngine,
                DashboardDefinition,
                DashboardPage,
            )

            with open(spec_file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)

            pages = [
                DashboardPage(
                    embed=p.get("embed", {}),
                    components=p.get("components", []),
                )
                for p in raw.get("pages", [])
            ]
            definition = DashboardDefinition(
                dashboard_id=raw["dashboard_id"],
                pages=pages,
                refresh_interval=raw.get("refresh_interval", 0),
            )

            ch = resolve_channel(client, channel)
            engine = InteractEngine()
            dashboard_id = await engine.dashboard_create(ch, definition)

            data = {"dashboard_id": dashboard_id}
            output(
                ctx,
                data,
                plain_text=f"Dashboard created (id={dashboard_id})",
            )

        return _action(client)

    run_discord(ctx, action)


@dashboard_group.command("delete")
@click.argument("dashboard_id")
@click.option("--channel", required=True, help="Channel name or ID.")
@click.pass_context
def dashboard_delete(ctx, dashboard_id, channel):
    """Delete a dashboard by ID."""

    def action(client):
        async def _action(client):
            from discli.interact_engine import InteractEngine

            ch = resolve_channel(client, channel)
            engine = InteractEngine()
            await engine.dashboard_delete(dashboard_id, ch)

            data = {"dashboard_id": dashboard_id, "deleted": True}
            output(
                ctx,
                data,
                plain_text=f"Dashboard deleted (id={dashboard_id})",
            )

        return _action(client)

    run_discord(ctx, action)
