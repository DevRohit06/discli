import pytest
from discli.interact_engine import (
    InteractEngine,
    InteractError,
    WorkflowDefinition,
    WorkflowStep,
    DashboardDefinition,
    DashboardPage,
)


def test_interact_engine_instantiates():
    engine = InteractEngine()
    assert engine.workflows == {}
    assert engine.dashboards == {}


def test_workflow_definition():
    steps = [
        WorkflowStep(
            step_id="intro",
            step_type="message",
            content="Welcome!",
            components=[{"type": "button", "label": "Next", "custom_id": "next"}],
        ),
        WorkflowStep(
            step_id="name",
            step_type="modal",
            content="Enter your name",
            fields=[{"label": "Name", "style": "short", "required": True}],
        ),
    ]
    wf = WorkflowDefinition(workflow_id="onboard", steps=steps)
    assert wf.workflow_id == "onboard"
    assert len(wf.steps) == 2
    assert wf.steps[0].step_type == "message"


def test_dashboard_definition():
    pages = [
        DashboardPage(embed={"title": "Page 1", "description": "First page"}),
        DashboardPage(embed={"title": "Page 2", "description": "Second page"}),
    ]
    dash = DashboardDefinition(dashboard_id="stats", pages=pages, refresh_interval=60)
    assert dash.dashboard_id == "stats"
    assert len(dash.pages) == 2
    assert dash.refresh_interval == 60


def test_interaction_router_prefix_routing():
    engine = InteractEngine()
    assert engine.route_custom_id("modal:signup") == "modal"
    assert engine.route_custom_id("wf:step1:next") == "workflow"
    assert engine.route_custom_id("dash:stats:page") == "dashboard"
    assert engine.route_custom_id("unknown:thing") is None
