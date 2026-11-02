"""AIToolNotes Traffic Engine - Scheduler and Runner"""

import json
import sys
import time
import random
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from traffic_engine.config.settings import PATHS, MODULES, SAFETY, TARGETS
from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.modules.opportunity_discovery import OpportunityDiscovery
from traffic_engine.modules.content_optimizer import ContentOptimizer
from traffic_engine.modules.tool_acquisition import ToolAcquisition
from traffic_engine.modules.distribution import DistributionEngine
from traffic_engine.modules.conversion_optimizer import ConversionOptimizer
from traffic_engine.modules.measurement import TrafficMeasurement
from traffic_engine.modules.autonomous_optimizer import AutonomousOptimizer


class TrafficEngine:
    """Main traffic engine orchestrator."""

    def __init__(self):
        self.modules: Dict[str, BaseModule] = {}
        self.run_log: List[ActionRecord] = []
        self.start_time = datetime.utcnow()

    def register_module(self, name: str, module: BaseModule):
        """Register a module."""
        self.modules[name] = module

    def run_all(self) -> Dict[str, any]:
        """Run all enabled modules in dependency order."""
        results = {}

        # Module execution order
        execution_order = [
            "opportunity_discovery",
            "content_optimization",
            "tool_acquisition",
            "distribution",
            "conversion_optimization",
            "measurement",
            "autonomous_optimization",
        ]

        for module_name in execution_order:
            if not MODULES.get(module_name, False):
                continue

            if module_name not in self.modules:
                continue

            module = self.modules[module_name]
            try:
                actions = module.run()
                results[module_name] = {
                    "status": "success",
                    "actions": len(actions),
                    "action_records": [
                        {
                            "timestamp": a.timestamp,
                            "module": a.module,
                            "action": a.action,
                            "target": a.target,
                            "status": a.status,
                            "error": a.error,
                        }
                        for a in actions
                    ],
                }
                self.run_log.extend(actions)
            except Exception as e:
                results[module_name] = {
                    "status": "failed",
                    "error": str(e),
                }

        return results

    def run_single(self, module_name: str) -> Dict[str, any]:
        """Run a single module by name."""
        if module_name not in self.modules:
            return {"status": "error", "error": f"Module {module_name} not found"}

        module = self.modules[module_name]
        try:
            actions = module.run()
            self.run_log.extend(actions)
            return {
                "status": "success",
                "actions": len(actions),
                "records": [
                    {
                        "action": a.action,
                        "target": a.target,
                        "status": a.status,
                        "error": a.error,
                    }
                    for a in actions
                ],
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def save_run_log(self):
        """Save complete run log."""
        filename = PATHS["reports"] / "run_log.json"
        data = {
            "run_id": self.start_time.isoformat() + "Z",
            "start_time": self.start_time.isoformat() + "Z",
            "end_time": datetime.utcnow().isoformat() + "Z",
            "modules_run": list(self.modules.keys()),
            "total_actions": len(self.run_log),
            "actions": [
                {
                    "timestamp": a.timestamp,
                    "module": a.module,
                    "action": a.action,
                    "target": a.target,
                    "status": a.status,
                    "details": a.details,
                    "error": a.error,
                }
                for a in self.run_log
            ],
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(filename)

    def get_status(self) -> Dict[str, any]:
        """Get current engine status."""
        return {
            "modules_registered": list(self.modules.keys()),
            "modules_enabled": [k for k, v in MODULES.items() if v],
            "last_run": self.start_time.isoformat() + "Z",
            "total_actions": len(self.run_log),
        }


def main():
    """Main entry point."""
    print("=" * 60)
    print("AIToolNotes Traffic Engine")
    print("=" * 60)

    engine = TrafficEngine()

    # Register modules
    engine.register_module("opportunity_discovery", OpportunityDiscovery())
    engine.register_module("content_optimization", ContentOptimizer())
    engine.register_module("tool_acquisition", ToolAcquisition())
    engine.register_module("distribution", DistributionEngine())
    engine.register_module("conversion_optimization", ConversionOptimizer())
    engine.register_module("measurement", TrafficMeasurement())
    engine.register_module("autonomous_optimization", AutonomousOptimizer())

    # Run all enabled modules
    results = engine.run_all()

    # Save run log
    log_path = engine.save_run_log()

    # Print summary
    print("\nRun Summary:")
    print("-" * 40)
    for module_name, result in results.items():
        status = result.get("status", "unknown")
        actions = result.get("actions", 0)
        print(f"  {module_name}: {status} ({actions} actions)")

    print(f"\nRun log saved: {log_path}")
    print(f"Total actions: {len(engine.run_log)}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    main()
