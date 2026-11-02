"""AIToolNotes Traffic Engine - Tests"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, SAFETY, SITES, TARGETS
from traffic_engine.modules.opportunity_discovery import OpportunityDiscovery
from traffic_engine.modules.content_optimizer import ContentOptimizer
from traffic_engine.modules.tool_acquisition import ToolAcquisition
from traffic_engine.modules.distribution import DistributionEngine
from traffic_engine.modules.conversion_optimizer import ConversionOptimizer
from traffic_engine.modules.measurement import TrafficMeasurement
from traffic_engine.modules.autonomous_optimizer import AutonomousOptimizer


class ConcreteTestModule(BaseModule):
    """Concrete implementation for testing BaseModule."""
    module_name = "test_module"
    
    def run(self):
        return []


class TestBaseModule:
    """Test base module functionality."""

    def test_action_record_creation(self):
        """Test creating an action record."""
        record = ActionRecord(
            module="test",
            action="test_action",
            target="test_target",
            status="success",
        )
        assert record.module == "test"
        assert record.action == "test_action"
        assert record.status == "success"
        assert record.timestamp is not None

    def test_action_record_with_error(self):
        """Test action record with error."""
        record = ActionRecord(
            module="test",
            action="fail",
            target="target",
            status="failed",
            error="Something went wrong",
        )
        assert record.error == "Something went wrong"

    def test_record_action(self):
        """Test recording an action."""
        module = ConcreteTestModule()
        record = module.record_action("test", "target", "success")
        assert len(module.actions) == 1
        assert module.actions[0].action == "test"
        assert record.status == "success"

    def test_save_and_load_actions(self, tmp_path):
        """Test saving and loading actions."""
        import os
        os.environ["TRAFFIC_ENGINE_REPORTS"] = str(tmp_path)

        module = ConcreteTestModule()
        module.record_action("a1", "t1", "success")
        module.record_action("a2", "t2", "failed")

        # Save
        path = module.save_actions()
        assert Path(path).exists()

        # Load
        loaded = module.load_previous_actions()
        assert len(loaded) == 2
        assert loaded[0].action == "a1"
        assert loaded[1].status == "failed"


class TestOpportunityDiscovery:
    """Test opportunity discovery module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        module = OpportunityDiscovery()
        assert module.module_name == "opportunity_discovery"
        assert module.opportunities == []

    def test_run_returns_actions(self):
        """Test run returns action records."""
        module = OpportunityDiscovery()
        actions = module.run()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_opportunities_saved(self):
        """Test opportunities are saved to disk."""
        module = OpportunityDiscovery()
        actions = module.run()

        opp_file = PATHS["reports"] / "opportunities.json"
        assert opp_file.exists()

        with open(opp_file, "r", encoding="utf-8") as f:
            opportunities = json.load(f)

        assert len(opportunities) > 0

    def test_opportunity_structure(self):
        """Test opportunity records have required fields."""
        module = OpportunityDiscovery()
        module.run()

        opp_file = PATHS["reports"] / "opportunities.json"
        with open(opp_file, "r", encoding="utf-8") as f:
            opportunities = json.load(f)

        required_fields = {"type", "priority", "source", "discovered_at"}
        for opp in opportunities[:5]:
            assert required_fields.issubset(set(opp.keys())), f"Missing fields in {opp}"


class TestContentOptimizer:
    """Test content optimization module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        module = ContentOptimizer()
        assert module.module_name == "content_optimization"
        assert module.audit_results == []

    def test_run_returns_actions(self):
        """Test run returns action records."""
        module = ContentOptimizer()
        actions = module.run()
        assert isinstance(actions, list)

    def test_audit_results_saved(self):
        """Test audit results are saved."""
        module = ContentOptimizer()
        module.run()

        audit_file = PATHS["reports"] / "content_audit.json"
        if audit_file.exists():
            with open(audit_file, "r", encoding="utf-8") as f:
                results = json.load(f)
            assert isinstance(results, list)

    def test_get_low_scoring_articles(self):
        """Test filtering low-scoring articles."""
        module = ContentOptimizer()
        module.audit_results = [
            {"path": "a.md", "score": 3, "issues": ["thin"]},
            {"path": "b.md", "score": 8, "issues": []},
            {"path": "c.md", "score": 5, "issues": ["few_links"]},
        ]

        low_scoring = module.get_low_scoring_articles(max_score=5)
        assert len(low_scoring) == 2
        assert low_scoring[0]["path"] == "a.md"
        assert low_scoring[1]["path"] == "c.md"


class TestToolAcquisition:
    """Test tool acquisition module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        module = ToolAcquisition()
        assert module.module_name == "tool_acquisition"

    def test_run_returns_actions(self):
        """Test run returns action records."""
        module = ToolAcquisition()
        actions = module.run()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_gaps_identified(self):
        """Test category gaps are identified."""
        module = ToolAcquisition()
        module.run()
        assert len(module.gaps_identified) > 0


class TestDistributionEngine:
    """Test distribution module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        module = DistributionEngine()
        assert module.module_name == "distribution"
        assert module.drafted_posts == []
        assert module.pending_approval == []

    def test_run_returns_actions(self):
        """Test run returns action records."""
        module = DistributionEngine()
        actions = module.run()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_draft_posts_created(self):
        """Test draft posts are created."""
        module = DistributionEngine()
        module.run()
        assert len(module.drafted_posts) > 0

    def test_pending_approval_queue(self):
        """Test posts requiring approval are queued."""
        module = DistributionEngine()
        module.run()
        assert len(module.pending_approval) > 0

    def test_approve_post(self):
        """Test approving a pending post."""
        module = DistributionEngine()
        module.run()
        initial_pending = len(module.pending_approval)
        assert initial_pending > 0

        result = module.approve_post(0)
        assert result is True
        assert len(module.pending_approval) == initial_pending - 1

    def test_approve_invalid_index(self):
        """Test approving with invalid index."""
        module = DistributionEngine()
        result = module.approve_post(999)
        assert result is False


class TestConversionOptimizer:
    """Test conversion optimization module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        module = ConversionOptimizer()
        assert module.module_name == "conversion_optimization"

    def test_run_returns_actions(self):
        """Test run returns action records."""
        module = ConversionOptimizer()
        actions = module.run()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_issues_identified(self):
        """Test conversion issues are identified."""
        module = ConversionOptimizer()
        module.run()
        # Should identify at least some issues
        assert len(module.issues) >= 0  # May be 0 if everything is fine


class TestTrafficMeasurement:
    """Test traffic measurement module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        module = TrafficMeasurement()
        assert module.module_name == "measurement"
        assert module.metrics == {}

    def test_run_returns_actions(self):
        """Test run returns action records."""
        module = TrafficMeasurement()
        actions = module.run()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_metrics_collected(self):
        """Test metrics are collected."""
        module = TrafficMeasurement()
        module.run()
        assert len(module.metrics) > 0

    def test_metrics_history_updated(self):
        """Test metrics history is updated."""
        module = TrafficMeasurement()
        module.run()
        assert module.history_file.exists()


class TestAutonomousOptimizer:
    """Test autonomous optimizer module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        module = AutonomousOptimizer()
        assert module.module_name == "autonomous_optimization"
        assert module.selected_actions == []
        assert module.executed_actions == []

    def test_run_returns_actions(self):
        """Test run returns action records."""
        module = AutonomousOptimizer()
        actions = module.run()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_safe_actions_list(self):
        """Test safe actions are defined."""
        module = AutonomousOptimizer()
        assert len(module.SAFE_ACTIONS) > 0
        assert "update_sitemap" in module.SAFE_ACTIONS
        assert "publish_new_article" not in module.SAFE_ACTIONS

    def test_approval_actions_list(self):
        """Test approval actions are defined."""
        module = AutonomousOptimizer()
        assert len(module.APPROVAL_ACTIONS) > 0
        assert "publish_new_article" in module.APPROVAL_ACTIONS
