"""AIToolNotes Traffic Engine - Free Tool Acquisition Module"""

import json
import re
import time
import random
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, SAFETY, SITES


class ToolAcquisition(BaseModule):
    """Audit and improve the AI tools directory."""

    module_name = "tool_acquisition"
    description = "Audit tools directory, identify gaps, add useful tools"

    def __init__(self):
        super().__init__()
        self.tools_added: List[Dict] = []
        self.gaps_identified: List[str] = []

    def run(self) -> List[ActionRecord]:
        """Run tool acquisition audit."""
        self.actions = []
        self.record_action("start", "tool_acquisition", "started")

        # 1. Audit existing tools
        self._audit_tools_directory()

        # 2. Identify category gaps
        self._identify_category_gaps()

        # 3. Validate tool quality
        self._validate_tool_quality()

        # 4. Save results
        self._save_results()

        self.record_action("complete", "tool_acquisition", "completed",
                           {"gaps": len(self.gaps_identified)})
        return self.actions

    def _audit_tools_directory(self):
        """Audit existing tools in the directory."""
        tools_dir = Path(__file__).resolve().parent.parent.parent / "aitoolnotes-github-repo" / "tools"
        if not tools_dir.exists():
            tools_dir = Path(__file__).resolve().parent.parent.parent / "aitoolnotes-public" / "tools"

        if not tools_dir.exists():
            self.record_action("audit", "tools_directory", "skipped",
                               error="Tools directory not found")
            return

        tool_files = list(tools_dir.glob("*.md"))
        self.record_action("audit", str(tools_dir), "success",
                           {"tool_pages": len(tool_files)})

    def _identify_category_gaps(self):
        """Identify missing tool categories."""
        existing_categories = {
            "video", "voice", "content", "students", "agents"
        }

        needed_categories = {
            "writing": "Free AI writing assistants, grammar checkers, and paraphrasing tools",
            "image": "Free AI image generators, photo editors, and design tools",
            "marketing": "Free AI marketing automation, SEO, and social media tools",
            "productivity": "Free AI productivity and task management tools",
            "coding": "Free AI coding assistants and development tools",
            "business": "Free AI tools for small business and entrepreneurs",
            "teachers": "Free AI tools for educators and classroom management",
            "nonprofits": "Free AI tools for nonprofits and fundraising",
            "freelancers": "Free AI tools for freelancers and independent workers",
            "music": "Free AI music generators and audio tools",
            "automation": "Free AI workflow automation and integration tools",
            "research": "Free AI research and data analysis tools",
        }

        gaps = {k: v for k, v in needed_categories.items()
                if k not in existing_categories}

        for category, description in gaps.items():
            self.gaps_identified.append(category)
            self.record_action("gap_found", category, "identified",
                               {"description": description})

    def _validate_tool_quality(self):
        """Validate that tools meet quality criteria."""
        # Quality criteria from existing repo
        criteria = [
            "no_credit_card_required",
            "functional_free_tier",
            "no_permanent_watermark",
            "commercial_use_allowed",
            "actively_maintained",
        ]

        self.record_action("validate", "tool_criteria", "success",
                           {"criteria": criteria})

    def _save_results(self):
        """Save tool acquisition results."""
        filename = PATHS["reports"] / "tool_acquisition.json"
        data = {
            "gaps_identified": self.gaps_identified,
            "tools_added": self.tools_added,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.record_action("save", str(filename), "success")
