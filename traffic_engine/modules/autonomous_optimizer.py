"""AIToolNotes Traffic Engine - Autonomous Optimizer"""

import json
import random
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, TARGETS


class AutonomousOptimizer(BaseModule):
    """Select and execute safe optimization actions."""

    module_name = "autonomous_optimization"
    description = "Select high-priority actions and execute safe improvements"

    # Actions safe to execute automatically
    SAFE_ACTIONS = [
        "add_internal_links",
        "update_sitemap",
        "update_github_readme",
        "add_faq_section",
        "optimize_meta_description",
    ]

    # Actions requiring user approval
    APPROVAL_ACTIONS = [
        "publish_new_article",
        "delete_duplicate_post",
        "submit_to_directory",
        "post_to_social",
        "modify_existing_article_content",
    ]

    def __init__(self):
        super().__init__()
        self.selected_actions: List[Dict] = []
        self.executed_actions: List[Dict] = []

    def run(self) -> List[ActionRecord]:
        """Run autonomous optimization."""
        self.actions = []
        self.record_action("start", "autonomous_optimization", "started")

        # 1. Load previous state
        self._load_state()

        # 2. Load module outputs
        opportunities = self._load_opportunities()
        audit_results = self._load_audit_results()
        metrics = self._load_metrics()

        # 3. Select actions based on priority
        self._select_actions(opportunities, audit_results, metrics)

        # 4. Execute safe actions
        self._execute_safe_actions()

        # 5. Queue approval actions
        self._queue_approval_actions()

        # 6. Save state
        self._save_state()

        self.record_action("complete", "autonomous_optimization", "completed",
                           {"selected": len(self.selected_actions),
                            "executed": len(self.executed_actions)})
        return self.actions

    def _load_state(self) -> Dict:
        """Load previous optimizer state."""
        state_file = PATHS["reports"] / "optimizer_state.json"
        if state_file.exists():
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"last_run": None, "executed_actions": []}

    def _load_opportunities(self) -> List[Dict]:
        """Load opportunities from discovery module."""
        opp_file = PATHS["reports"] / "opportunities.json"
        if opp_file.exists():
            with open(opp_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _load_audit_results(self) -> List[Dict]:
        """Load audit results from content optimizer."""
        audit_file = PATHS["reports"] / "content_audit.json"
        if audit_file.exists():
            with open(audit_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _load_metrics(self) -> Dict:
        """Load latest metrics from measurement module."""
        metrics_file = PATHS["reports"] / "metrics_history.json"
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                if history:
                    return history[-1]
        return {}

    def _select_actions(self, opportunities: List[Dict], audit_results: List[Dict], metrics: Dict):
        """Select high-priority actions."""
        # Priority 1: Fix content issues
        for article in audit_results:
            if article.get("issues") and len(self.selected_actions) < 5:
                for issue in article["issues"]:
                    if issue == "missing_related_articles":
                        self.selected_actions.append({
                            "action": "add_internal_links",
                            "target": article["path"],
                            "priority": "high",
                            "requires_approval": False,
                        })
                    elif issue == "missing_faq":
                        self.selected_actions.append({
                            "action": "add_faq_section",
                            "target": article["path"],
                            "priority": "medium",
                            "requires_approval": False,
                        })

        # Priority 2: Update sitemap if needed
        sitemap_urls = metrics.get("sitemap_urls", 0)
        published_posts = metrics.get("published_posts", 0)
        if sitemap_urls != published_posts and published_posts > 0:
            self.selected_actions.append({
                "action": "update_sitemap",
                "target": "sitemap.xml",
                "priority": "high",
                "requires_approval": False,
            })

        # Priority 3: Update GitHub README
        self.selected_actions.append({
            "action": "update_github_readme",
            "target": "README.md",
            "priority": "medium",
            "requires_approval": False,
        })

        # Limit to daily budget
        daily_limit = TARGETS.get("daily_actions_max", 3)
        self.selected_actions = self.selected_actions[:daily_limit]

        for action in self.selected_actions:
            self.record_action("select", action["target"], action["action"],
                               {"priority": action["priority"],
                                "requires_approval": action["requires_approval"]})

    def _execute_safe_actions(self):
        """Execute actions that don't require approval."""
        for action in self.selected_actions:
            if not action.get("requires_approval") and action["action"] in self.SAFE_ACTIONS:
                try:
                    result = self._execute_action(action)
                    action["result"] = result
                    action["executed"] = True
                    self.executed_actions.append(action)
                    self.record_action("execute", action["target"], "success",
                                       {"action": action["action"]})
                except Exception as e:
                    action["result"] = str(e)
                    action["executed"] = False
                    self.record_action("execute", action["target"], "failed",
                                       {"action": action["action"], "error": str(e)})

    def _queue_approval_actions(self):
        """Queue actions requiring user approval."""
        for action in self.selected_actions:
            if action.get("requires_approval"):
                self.record_action("queue", action["target"], "pending_approval",
                                   {"action": action["action"],
                                    "priority": action["priority"]})

    def _execute_action(self, action: Dict) -> str:
        """Execute a single safe action."""
        action_type = action["action"]
        target = action["target"]

        if action_type == "update_sitemap":
            return self._update_sitemap()
        elif action_type == "update_github_readme":
            return self._update_github_readme()
        elif action_type == "add_internal_links":
            return f"Queued internal links for {target}"
        elif action_type == "add_faq_section":
            return f"Queued FAQ section for {target}"
        elif action_type == "optimize_meta_description":
            return f"Queued meta optimization for {target}"
        else:
            return f"Unknown action: {action_type}"

    def _update_sitemap(self) -> str:
        """Update sitemap with current posts."""
        try:
            import os
            os.environ.setdefault("GROQ_API_KEY", "dummy")
            os.environ.setdefault("BLOG_ID", "7352205941047679763")
            from blog_automation import get_blogger_service

            service = get_blogger_service()
            posts = service.posts().list(blogId="7352205941047679763", maxResults=500).execute()

            sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            for p in posts.get("items", []):
                url = p["url"]
                lastmod = p.get("published", "2026-11-02")[:10]
                sitemap += f'  <url><loc>{url}</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>\n'
            sitemap += "</urlset>\n"

            sitemap_path = Path(__file__).resolve().parent.parent.parent / "sitemap.xml"
            sitemap_path.write_text(sitemap, encoding="utf-8")
            return f"Updated sitemap with {len(posts.get('items', []))} URLs"
        except Exception as e:
            return f"Failed: {str(e)}"

    def _update_github_readme(self) -> str:
        """Update GitHub README with timestamp."""
        try:
            readme_path = Path(__file__).resolve().parent.parent.parent / "aitoolnotes-github-repo" / "README.md"
            if readme_path.exists():
                content = readme_path.read_text(encoding="utf-8")
                if "Last updated:" not in content:
                    updated = content.rstrip() + f"\n\n---\n*Last updated: {datetime.utcnow().strftime('%Y-%m-%d')}*\n"
                    readme_path.write_text(updated, encoding="utf-8")
                    return "Updated README timestamp"
            return "README already current"
        except Exception as e:
            return f"Failed: {str(e)}"

    def _save_state(self):
        """Save optimizer state."""
        state_file = PATHS["reports"] / "optimizer_state.json"
        data = {
            "last_run": datetime.utcnow().isoformat() + "Z",
            "selected_actions": self.selected_actions,
            "executed_actions": self.executed_actions,
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.record_action("save", str(state_file), "success")
