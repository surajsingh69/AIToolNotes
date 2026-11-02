"""AIToolNotes Traffic Engine - Legitimate Distribution Module"""

import json
import re
import time
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, SAFETY, SITES


class DistributionEngine(BaseModule):
    """Manage legitimate content distribution."""

    module_name = "distribution"
    description = "Draft and track distribution to authorized channels"

    # Platforms that can be reached without login
    PASSIVE_PLATFORMS = [
        {"name": "github_readme", "type": "owned", "requires_auth": False},
        {"name": "github_profile", "type": "owned", "requires_auth": False},
        {"name": "sitemap", "type": "owned", "requires_auth": False},
        {"name": "rss_feed", "type": "owned", "requires_auth": False},
    ]

    # Platforms requiring user authorization
    ACTIVE_PLATFORMS = [
        {"name": "reddit", "type": "community", "requires_auth": True},
        {"name": "quora", "type": "qa", "requires_auth": True},
        {"name": "pinterest", "type": "social", "requires_auth": True},
        {"name": "twitter", "type": "social", "requires_auth": True},
        {"name": "linkedin", "type": "social", "requires_auth": True},
        {"name": "hacker_news", "type": "community", "requires_auth": False},
        {"name": "dev_to", "type": "community", "requires_auth": True},
    ]

    def __init__(self):
        super().__init__()
        self.drafted_posts: List[Dict] = []
        self.pending_approval: List[Dict] = []

    def run(self) -> List[ActionRecord]:
        """Run distribution workflow."""
        self.actions = []
        self.record_action("start", "distribution", "started")

        # 1. Update passive platforms
        self._update_passive_platforms()

        # 2. Draft posts for active platforms
        self._draft_active_posts()

        # 3. Identify backlink opportunities
        self._identify_backlink_opportunities()

        # 4. Save distribution state
        self._save_state()

        self.record_action("complete", "distribution", "completed",
                           {"drafted": len(self.drafted_posts),
                            "pending_approval": len(self.pending_approval)})
        return self.actions

    def _update_passive_platforms(self):
        """Update platforms we control directly."""
        # Update GitHub README with latest articles
        try:
            readme_path = Path(__file__).resolve().parent.parent.parent / "aitoolnotes-github-repo" / "README.md"
            if readme_path.exists():
                content = readme_path.read_text(encoding="utf-8")
                # Check if it needs updating
                if "Last updated:" not in content:
                    updated = content.rstrip() + f"\n\n---\n*Last updated: {datetime.utcnow().strftime('%Y-%m-%d')}*\n"
                    readme_path.write_text(updated, encoding="utf-8")
                    self.record_action("update", str(readme_path), "success",
                                       {"change": "added_timestamp"})
                else:
                    self.record_action("update", str(readme_path), "skipped",
                                       {"reason": "already_current"})
        except Exception as e:
            self.record_action("update", "github_readme", "failed", error=str(e))

    def _draft_active_posts(self):
        """Draft posts for platforms requiring authorization."""
        # These are drafted but NOT published until user approves
        drafts = [
            {
                "platform": "reddit",
                "subreddit": "r/ArtificialIntelligence",
                "title": "I built a free directory of AI tools tested in 2026 — no watermarks, no credit cards",
                "body": "After testing dozens of AI tools, I put together a curated list of the best free ones...\n\nFull comparisons: https://aitoolnotes.blogspot.com/",
                "requires_approval": True,
            },
            {
                "platform": "hacker_news",
                "title": "Show HN: AIToolNotes – Free AI Tools Directory with Honest Reviews",
                "body": "I've been testing free AI tools and publishing honest comparisons...\n\nhttps://aitoolnotes.blogspot.com/",
                "requires_approval": True,
            },
        ]

        for draft in drafts:
            self.drafted_posts.append(draft)
            if draft["requires_approval"]:
                self.pending_approval.append(draft)
                self.record_action("draft", draft["platform"], "pending_approval",
                                   {"title": draft["title"][:60]})
            else:
                self.record_action("draft", draft["platform"], "ready_to_publish",
                                   {"title": draft["title"][:60]})

    def _identify_backlink_opportunities(self):
        """Identify potential backlink sources."""
        opportunities = [
            {"site": "freeaitools directories", "type": "directory_listing", "difficulty": "easy"},
            {"site": "AI tool comparison sites", "type": "review_mention", "difficulty": "medium"},
            {"site": "GitHub trending", "type": "repo_visibility", "difficulty": "easy"},
            {"site": "Dev.to", "type": "article_cross_post", "difficulty": "medium"},
            {"site": "Medium", "type": "article_cross_post", "difficulty": "medium"},
        ]

        for opp in opportunities:
            self.record_action("backlink_opportunity", opp["site"], "identified",
                               {"type": opp["type"], "difficulty": opp["difficulty"]})

    def _save_state(self):
        """Save distribution state."""
        filename = PATHS["reports"] / "distribution_state.json"
        data = {
            "drafted_posts": self.drafted_posts,
            "pending_approval": self.pending_approval,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.record_action("save", str(filename), "success")

    def get_pending_approval(self) -> List[Dict]:
        """Get posts awaiting user approval."""
        return self.pending_approval

    def approve_post(self, index: int) -> bool:
        """Approve a pending post for publication."""
        if 0 <= index < len(self.pending_approval):
            post = self.pending_approval.pop(index)
            self.record_action("approve", post["platform"], "approved",
                               {"title": post["title"][:60]})
            return True
        return False
