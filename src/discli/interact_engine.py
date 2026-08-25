"""Interactive Engine — interaction router, workflows, and dashboards."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable

import discord


class InteractError(Exception):
    """Raised for interaction engine failures."""


# ---------------------------------------------------------------------------
# Prefix routing map
# ---------------------------------------------------------------------------

_PREFIX_MAP: dict[str, str] = {
    "modal:": "modal",
    "wf:": "workflow",
    "dash:": "dashboard",
    "voice:": "voice",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WorkflowStep:
    """A single step within a workflow."""

    step_id: str
    step_type: str  # "message" | "select" | "modal" | "confirm"
    content: str = ""
    components: list[dict[str, Any]] = field(default_factory=list)
    fields: list[dict[str, Any]] = field(default_factory=list)
    next: dict[str, Any] | str | None = None
    timeout: int = 300


@dataclass
class WorkflowDefinition:
    """A collection of ordered steps forming a workflow."""

    workflow_id: str
    steps: list[WorkflowStep]

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Return the step with matching step_id, or None."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


@dataclass
class WorkflowState:
    """Runtime state for an in-progress workflow instance."""

    workflow_id: str
    user_id: str
    channel_id: int
    current_step: str
    collected_data: dict[str, Any] = field(default_factory=dict)
    message_id: int | None = None


@dataclass
class DashboardPage:
    """A single page of a dashboard.

    Two layouts. The default builds an embed plus a row of buttons, which is
    what every existing spec file describes. Setting ``layout="v2"`` instead
    renders Discord's Components v2 (containers, sections, media galleries,
    separators) from ``blocks``.

    The choice is per page and opt-in: a page without ``layout`` renders
    exactly as it always has, so existing specs and `serve` consumers are
    untouched. The two cannot be mixed on one page -- Discord rejects a
    Components v2 message that also carries content or embeds.
    """

    embed: dict[str, Any] = field(default_factory=dict)
    components: list[dict[str, Any]] = field(default_factory=list)
    layout: str = "embed"
    blocks: list[dict[str, Any]] = field(default_factory=list)

    def is_v2(self) -> bool:
        return self.layout == "v2"


@dataclass
class DashboardDefinition:
    """A multi-page dashboard with optional auto-refresh."""

    dashboard_id: str
    pages: list[DashboardPage]
    refresh_interval: int = 0  # seconds; 0 = no auto-refresh
    components: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Discord stamps IS_COMPONENTS_V2 on a message when it is sent and the
        # flag cannot be toggled afterwards, so a dashboard cannot page from an
        # embed layout into a v2 one. Catch that here rather than at the edit
        # that fails halfway through a user's navigation.
        layouts = {page.layout for page in self.pages}
        if len(layouts) > 1:
            raise InteractError(
                "All pages of a dashboard must use the same layout; got "
                f"{', '.join(sorted(layouts))}. Discord fixes the Components v2 "
                "flag when the message is created, so pages cannot switch."
            )

    def is_v2(self) -> bool:
        return bool(self.pages) and self.pages[0].is_v2()


@dataclass
class DashboardState:
    """Runtime state for an active dashboard."""

    dashboard_id: str
    channel_id: int
    message_id: int | None = None
    current_page: int = 0
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Components v2 block rendering
# ---------------------------------------------------------------------------

V2_BLOCK_TYPES = ("container", "text", "section", "separator", "gallery", "buttons")

_BUTTON_STYLES = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
    "link": discord.ButtonStyle.link,
}

_SEPARATOR_SPACING = {
    "small": discord.SeparatorSpacing.small,
    "large": discord.SeparatorSpacing.large,
}


def _v2_button(spec: dict[str, Any], dashboard_id: str) -> discord.ui.Button:
    """Build a button, routing its custom_id the same way the embed layout does.

    Keeping the ``dash:<id>:<key>`` prefix means handle_dashboard_interaction
    works identically for both layouts -- v2 changes how a page looks, not how
    its interactions are routed.
    """
    style = _BUTTON_STYLES.get(spec.get("style", "primary"), discord.ButtonStyle.primary)
    if style is discord.ButtonStyle.link:
        url = spec.get("url")
        if not url:
            raise InteractError("A link button needs a 'url'.")
        return discord.ui.Button(label=spec.get("label", "Open"), style=style, url=url)
    key = spec.get("custom_id", spec.get("label", "btn"))
    return discord.ui.Button(
        label=spec.get("label", "Button"),
        style=style,
        custom_id=f"dash:{dashboard_id}:{key}",
        disabled=bool(spec.get("disabled", False)),
    )


def build_v2_block(spec: dict[str, Any], dashboard_id: str):
    """Turn one spec block into a discord.ui item."""
    kind = spec.get("type")
    if kind == "text":
        content = spec.get("content")
        if not content:
            raise InteractError("A 'text' block needs 'content'.")
        return discord.ui.TextDisplay(content)

    if kind == "separator":
        return discord.ui.Separator(
            visible=bool(spec.get("visible", True)),
            spacing=_SEPARATOR_SPACING.get(spec.get("spacing", "small"), discord.SeparatorSpacing.small),
        )

    if kind == "gallery":
        items = spec.get("items") or []
        if not items:
            raise InteractError("A 'gallery' block needs at least one item in 'items'.")
        return discord.ui.MediaGallery(*[
            discord.MediaGalleryItem(
                item["url"] if isinstance(item, dict) else item,
                description=(item.get("description") if isinstance(item, dict) else None),
            )
            for item in items
        ])

    if kind == "section":
        content = spec.get("content")
        if not content:
            raise InteractError("A 'section' block needs 'content'.")
        # Section requires an accessory; a thumbnail is the natural default,
        # and a button is the other thing Discord allows there.
        if spec.get("button"):
            accessory = _v2_button(spec["button"], dashboard_id)
        elif spec.get("thumbnail"):
            accessory = discord.ui.Thumbnail(spec["thumbnail"])
        else:
            raise InteractError("A 'section' block needs either 'thumbnail' or 'button'.")
        lines = content if isinstance(content, list) else [content]
        return discord.ui.Section(*lines, accessory=accessory)

    if kind == "buttons":
        buttons = spec.get("items") or []
        if not buttons:
            raise InteractError("A 'buttons' block needs at least one item in 'items'.")
        return discord.ui.ActionRow(*[_v2_button(b, dashboard_id) for b in buttons])

    if kind == "container":
        children = [build_v2_block(child, dashboard_id) for child in spec.get("children") or []]
        if not children:
            raise InteractError("A 'container' block needs at least one child.")
        kwargs: dict[str, Any] = {"spoiler": bool(spec.get("spoiler", False))}
        accent = spec.get("accent")
        if accent is not None:
            try:
                kwargs["accent_colour"] = discord.Colour(int(str(accent).lstrip("#"), 16))
            except ValueError:
                raise InteractError(f"Invalid container accent colour: {accent!r} (use hex like 5865f2)")
        return discord.ui.Container(*children, **kwargs)

    raise InteractError(
        f"Unknown v2 block type: {kind!r}. Supported: {', '.join(V2_BLOCK_TYPES)}"
    )


def build_v2_view(page: "DashboardPage", dashboard_id: str, *, nav: list | None = None) -> discord.ui.LayoutView:
    """Assemble a LayoutView for one v2 page."""
    view = discord.ui.LayoutView(timeout=None)
    if not page.blocks:
        raise InteractError("A page with layout 'v2' needs at least one entry in 'blocks'.")
    for block in page.blocks:
        view.add_item(build_v2_block(block, dashboard_id))
    if nav:
        view.add_item(discord.ui.ActionRow(*nav))
    return view


# ---------------------------------------------------------------------------
# InteractEngine
# ---------------------------------------------------------------------------


class InteractEngine:
    """Manages stateful interactive Discord components (workflows, dashboards)."""

    def __init__(self) -> None:
        # Active runtime state keyed by "user_id:workflow_id" or dashboard_id
        self.workflows: dict[str, WorkflowState] = {}
        self.dashboards: dict[str, DashboardState] = {}

        # Stored definitions
        self._workflow_defs: dict[str, WorkflowDefinition] = {}
        self._dashboard_defs: dict[str, DashboardDefinition] = {}

        # Background tasks
        self._timeout_tasks: dict[str, asyncio.Task] = {}
        self._refresh_tasks: dict[str, asyncio.Task] = {}

        self._on_event: Callable[[dict[str, Any]], None] | None = None

    # ------------------------------------------------------------------ events

    def set_event_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback that receives engine events."""
        self._on_event = handler

    def _emit(self, event: dict[str, Any]) -> None:
        """Fire the registered event handler, if any."""
        if self._on_event is not None:
            self._on_event(event)

    # ----------------------------------------------------------------- routing

    @staticmethod
    def route_custom_id(custom_id: str) -> str | None:
        """Match a Discord component custom_id to a handler type via prefix map.

        Returns the handler type string (e.g. "modal", "workflow", "dashboard",
        "voice") or None if no prefix matches.
        """
        for prefix, handler in _PREFIX_MAP.items():
            if custom_id.startswith(prefix):
                return handler
        return None

    # --------------------------------------------------------------- modal builder

    @staticmethod
    def build_modal(
        title: str,
        custom_id: str,
        fields: list[dict[str, Any]],
    ) -> discord.ui.Modal:
        """Build a discord.ui.Modal with TextInput children.

        custom_id is prefixed with "modal:" if not already prefixed.
        Each field dict may have: label, style (short/paragraph), required,
        placeholder, default, max_length, custom_id.
        """
        if not custom_id.startswith("modal:"):
            custom_id = f"modal:{custom_id}"

        modal = discord.ui.Modal(title=title, custom_id=custom_id)

        for f in fields:
            style_raw = f.get("style", "short")
            style = (
                discord.TextStyle.paragraph
                if style_raw == "paragraph"
                else discord.TextStyle.short
            )

            item_kwargs: dict[str, Any] = {
                "label": f["label"],
                "style": style,
                "required": f.get("required", True),
            }
            if "placeholder" in f:
                item_kwargs["placeholder"] = f["placeholder"]
            if "default" in f:
                item_kwargs["default"] = f["default"]
            if "max_length" in f:
                item_kwargs["max_length"] = f["max_length"]
            if "custom_id" in f:
                item_kwargs["custom_id"] = f["custom_id"]

            modal.add_item(discord.ui.TextInput(**item_kwargs))

        return modal

    # --------------------------------------------------------------- workflow

    async def workflow_start(
        self,
        channel: discord.TextChannel,
        user_id: str,
        definition: WorkflowDefinition,
    ) -> str:
        """Start a workflow for a user. Returns the state key."""
        self._workflow_defs[definition.workflow_id] = definition

        if not definition.steps:
            raise InteractError("Workflow has no steps")

        first_step = definition.steps[0]
        state = WorkflowState(
            workflow_id=definition.workflow_id,
            user_id=user_id,
            channel_id=channel.id,
            current_step=first_step.step_id,
        )
        key = f"{user_id}:{definition.workflow_id}"
        self.workflows[key] = state

        await self._send_workflow_step(channel, state, first_step)
        self._start_timeout(key, first_step.timeout)
        return key

    async def _send_workflow_step(
        self,
        channel: discord.TextChannel,
        state: WorkflowState,
        step: WorkflowStep,
    ) -> None:
        """Send the appropriate Discord message for the given workflow step."""
        wf_id = state.workflow_id
        step_id = step.step_id

        view = discord.ui.View(timeout=float(step.timeout))

        if step.step_type == "confirm":
            yes_btn = discord.ui.Button(
                label="Yes",
                style=discord.ButtonStyle.success,
                custom_id=f"wf:{wf_id}:{step_id}:yes",
            )
            no_btn = discord.ui.Button(
                label="No",
                style=discord.ButtonStyle.danger,
                custom_id=f"wf:{wf_id}:{step_id}:no",
            )
            view.add_item(yes_btn)
            view.add_item(no_btn)

        elif step.step_type == "select":
            options = [
                discord.SelectOption(
                    label=opt.get("label", opt.get("value", str(i))),
                    value=opt.get("value", str(i)),
                    description=opt.get("description"),
                )
                for i, opt in enumerate(step.components)
            ]
            if options:
                select = discord.ui.Select(
                    placeholder=step.content or "Select an option",
                    custom_id=f"wf:{wf_id}:{step_id}:select",
                    options=options,
                )
                view.add_item(select)

        else:
            # "message" or "modal" — add generic buttons from step.components
            for comp in step.components:
                if comp.get("type") == "button":
                    comp_custom_id = comp.get("custom_id", comp.get("label", "btn"))
                    btn = discord.ui.Button(
                        label=comp.get("label", "Button"),
                        style=discord.ButtonStyle.primary,
                        custom_id=f"wf:{wf_id}:{step_id}:{comp_custom_id}",
                    )
                    view.add_item(btn)

        msg = await channel.send(content=step.content or None, view=view)
        state.message_id = msg.id

    def _start_timeout(self, key: str, timeout: int) -> None:
        """Cancel any existing timeout for key and start a new async timeout task."""
        existing = self._timeout_tasks.pop(key, None)
        if existing is not None:
            existing.cancel()

        async def _timeout_coro() -> None:
            await asyncio.sleep(timeout)
            self.workflows.pop(key, None)
            self._emit({"event": "workflow_timeout", "key": key})

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_timeout_coro())
        except RuntimeError:
            # No running loop (e.g. during tests without async context) — skip
            return
        self._timeout_tasks[key] = task

    async def handle_workflow_interaction(
        self,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        """Handle a workflow button/select interaction.

        Parses wf:{wf_id}:{step_id}:{action}, records input, advances to next
        step or completes the workflow.
        """
        # custom_id format: wf:{wf_id}:{step_id}:{action}
        parts = custom_id.split(":", 3)
        if len(parts) < 4:
            return
        _, wf_id, step_id, action = parts

        user_id = str(interaction.user.id)
        key = f"{user_id}:{wf_id}"

        state = self.workflows.get(key)
        if state is None:
            await interaction.response.send_message(
                "No active workflow found.", ephemeral=True
            )
            return

        # Record the user's response
        state.collected_data[step_id] = action

        self._emit(
            {
                "event": "workflow_step_completed",
                "key": key,
                "step_id": step_id,
                "action": action,
                "collected_data": dict(state.collected_data),
            }
        )

        # Determine next step
        definition = self._workflow_defs.get(wf_id)
        if definition is None:
            return

        current_step_obj = definition.get_step(step_id)
        if current_step_obj is None:
            return

        next_step_id: str | None = None
        if isinstance(current_step_obj.next, dict):
            # Conditional routing: maps action -> step_id
            next_step_id = current_step_obj.next.get(action)
        elif isinstance(current_step_obj.next, str):
            next_step_id = current_step_obj.next
        else:
            # Auto-advance to next step in list
            idx = definition.steps.index(current_step_obj)
            if idx + 1 < len(definition.steps):
                next_step_id = definition.steps[idx + 1].step_id

        # Cancel timeout before advancing
        old_task = self._timeout_tasks.pop(key, None)
        if old_task is not None:
            old_task.cancel()

        if next_step_id is None:
            # Workflow finished
            self.workflows.pop(key, None)
            self._emit(
                {
                    "event": "workflow_finished",
                    "key": key,
                    "collected_data": dict(state.collected_data),
                }
            )
            await interaction.response.send_message(
                "Workflow complete!", ephemeral=True
            )
            return

        next_step = definition.get_step(next_step_id)
        if next_step is None:
            return

        state.current_step = next_step_id
        await interaction.response.defer()
        await self._send_workflow_step(interaction.channel, state, next_step)
        self._start_timeout(key, next_step.timeout)

    async def workflow_cancel(self, user_id: str, workflow_id: str) -> None:
        """Cancel and clean up a workflow for a user."""
        key = f"{user_id}:{workflow_id}"
        self.workflows.pop(key, None)
        task = self._timeout_tasks.pop(key, None)
        if task is not None:
            task.cancel()

    # --------------------------------------------------------------- dashboard

    async def dashboard_create(
        self,
        channel: discord.TextChannel,
        definition: DashboardDefinition,
    ) -> str:
        """Create and display a dashboard. Returns dashboard_id."""
        self._dashboard_defs[definition.dashboard_id] = definition

        state = DashboardState(
            dashboard_id=definition.dashboard_id,
            channel_id=channel.id,
        )
        self.dashboards[definition.dashboard_id] = state

        await self._render_dashboard(channel, definition, state)

        if definition.refresh_interval > 0:
            self._start_refresh(definition.dashboard_id, definition.refresh_interval, channel)

        return definition.dashboard_id

    async def _render_dashboard(
        self,
        channel: discord.TextChannel,
        definition: DashboardDefinition,
        state: DashboardState,
    ) -> None:
        """Render the current page of the dashboard, editing existing or sending new."""
        page = definition.pages[state.current_page]
        nav = self._nav_buttons(definition, state)

        if page.is_v2():
            view = build_v2_view(page, definition.dashboard_id, nav=nav)
            # A Components v2 message carries no content and no embeds;
            # Discord rejects the message outright if it does.
            payload = {"view": view}
        else:
            payload = {"embed": self._page_embed(page), "view": self._page_view(definition, page, nav)}

        if state.message_id is not None:
            try:
                msg = await channel.fetch_message(state.message_id)
                await msg.edit(**payload)
                return
            except discord.NotFound:
                pass

        msg = await channel.send(**payload)
        state.message_id = msg.id

    @staticmethod
    def _page_embed(page: DashboardPage) -> discord.Embed:
        page_data = page.embed or {}
        embed = discord.Embed(
            title=page_data.get("title"),
            description=page_data.get("description"),
            color=page_data.get("color", discord.Color.blurple().value),
        )
        for k, v in page_data.items():
            if k not in ("title", "description", "color"):
                embed.set_footer(text=str(v))
                break
        return embed

    def _nav_buttons(
        self, definition: DashboardDefinition, state: DashboardState
    ) -> list[discord.ui.Button]:
        """Previous/counter/next, shared by both layouts."""
        if len(definition.pages) <= 1:
            return []
        return [
            discord.ui.Button(
                label="Previous",
                style=discord.ButtonStyle.secondary,
                custom_id=f"dash:{definition.dashboard_id}:prev",
                disabled=state.current_page == 0,
            ),
            discord.ui.Button(
                label=f"{state.current_page + 1}/{len(definition.pages)}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"dash:{definition.dashboard_id}:counter",
                disabled=True,
            ),
            discord.ui.Button(
                label="Next",
                style=discord.ButtonStyle.secondary,
                custom_id=f"dash:{definition.dashboard_id}:next",
                disabled=state.current_page >= len(definition.pages) - 1,
            ),
        ]

    @staticmethod
    def _page_view(
        definition: DashboardDefinition,
        page: DashboardPage,
        nav: list[discord.ui.Button],
    ) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        for button in nav:
            view.add_item(button)
        for comp in list(page.components) + list(definition.components):
            if comp.get("type") == "button":
                cid = comp.get("custom_id", comp.get("label", "btn"))
                view.add_item(discord.ui.Button(
                    label=comp.get("label", "Button"),
                    style=discord.ButtonStyle.primary,
                    custom_id=f"dash:{definition.dashboard_id}:{cid}",
                ))
        return view

    def _start_refresh(
        self,
        dashboard_id: str,
        interval: int,
        channel: discord.TextChannel,
    ) -> None:
        """Create a periodic re-render task for a dashboard."""
        existing = self._refresh_tasks.pop(dashboard_id, None)
        if existing is not None:
            existing.cancel()

        async def _refresh_coro() -> None:
            while True:
                await asyncio.sleep(interval)
                state = self.dashboards.get(dashboard_id)
                definition = self._dashboard_defs.get(dashboard_id)
                if state is None or definition is None:
                    break
                await self._render_dashboard(channel, definition, state)

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_refresh_coro())
        except RuntimeError:
            return
        self._refresh_tasks[dashboard_id] = task

    async def handle_dashboard_interaction(
        self,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        """Handle a dashboard button interaction.

        Parses dash:{id}:{action}, handles prev/next pagination, emits
        dashboard_interaction for all other custom actions.
        """
        # custom_id format: dash:{dashboard_id}:{action}
        parts = custom_id.split(":", 2)
        if len(parts) < 3:
            return
        _, dashboard_id, action = parts

        state = self.dashboards.get(dashboard_id)
        definition = self._dashboard_defs.get(dashboard_id)
        if state is None or definition is None:
            await interaction.response.send_message(
                "Dashboard not found.", ephemeral=True
            )
            return

        if action == "prev":
            state.current_page = max(0, state.current_page - 1)
            await interaction.response.defer()
            await self._render_dashboard(interaction.channel, definition, state)
        elif action == "next":
            state.current_page = min(
                len(definition.pages) - 1, state.current_page + 1
            )
            await interaction.response.defer()
            await self._render_dashboard(interaction.channel, definition, state)
        elif action == "counter":
            await interaction.response.defer()
        else:
            self._emit(
                {
                    "event": "dashboard_interaction",
                    "dashboard_id": dashboard_id,
                    "action": action,
                    "user_id": str(interaction.user.id),
                    "data": dict(state.data),
                }
            )
            await interaction.response.defer()

    async def dashboard_update(
        self,
        dashboard_id: str,
        updates: dict[str, Any],
        channel: discord.TextChannel,
    ) -> None:
        """Merge data updates into a dashboard and re-render it."""
        state = self.dashboards.get(dashboard_id)
        definition = self._dashboard_defs.get(dashboard_id)
        if state is None or definition is None:
            raise InteractError(f"Dashboard '{dashboard_id}' not found")

        state.data.update(updates)
        await self._render_dashboard(channel, definition, state)

    async def dashboard_delete(
        self,
        dashboard_id: str,
        channel: discord.TextChannel,
    ) -> None:
        """Delete a dashboard message and clean up state."""
        state = self.dashboards.pop(dashboard_id, None)
        self._dashboard_defs.pop(dashboard_id, None)

        task = self._refresh_tasks.pop(dashboard_id, None)
        if task is not None:
            task.cancel()

        if state is not None and state.message_id is not None:
            try:
                msg = await channel.fetch_message(state.message_id)
                await msg.delete()
            except discord.NotFound:
                pass

    # -------------------------------------------------------------------- close

    async def close(self) -> None:
        """Cancel all background tasks and clear all state."""
        for task in list(self._timeout_tasks.values()):
            task.cancel()
        for task in list(self._refresh_tasks.values()):
            task.cancel()
        self._timeout_tasks.clear()
        self._refresh_tasks.clear()
        self.workflows.clear()
        self.dashboards.clear()
        self._workflow_defs.clear()
        self._dashboard_defs.clear()
