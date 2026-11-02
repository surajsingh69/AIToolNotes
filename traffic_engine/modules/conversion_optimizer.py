"""AIToolNotes Traffic Engine - Conversion Optimization Module"""

import json
import re
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, SITES


class ConversionOptimizer(BaseModule):
    """Audit and improve conversion paths."""

    module_name = "conversion_optimization"
    description = "Audit navigation, CTAs, and user journeys"

    def __init__(self):
        super().__init__()
        self.issues: List[Dict] = []
        self.recommendations: List[str] = []

    def run(self) -> List[ActionRecord]:
        """Run conversion audit."""
        self.actions = []
        self.record_action("start", "conversion_optimization", "started")

        # 1. Audit landing page
        self._audit_landing_page()

        # 2. Audit tools page
        self._audit_tools_page()

        # 3. Audit blog feed page
        self._audit_blog_page()

        # 4. Generate recommendations
        self._generate_recommendations()

        # 5. Save results
        self._save_results()

        self.record_action("complete", "conversion_optimization", "completed",
                           {"issues_found": len(self.issues)})
        return self.actions

    def _audit_landing_page(self):
        """Audit the main landing page."""
        try:
            index_path = Path(__file__).resolve().parent.parent.parent / "github-io" / "index.html"
            if not index_path.exists():
                self.record_action("audit", "index.html", "skipped",
                                   error="File not found")
                return

            content = index_path.read_text(encoding="utf-8")

            # Check for key elements
            has_clear_headline = "<h1" in content and len(re.findall(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)[0]) > 20
            has_cta = "Read Full Article" in content or "View Tools" in content or "Get Started" in content
            has_blog_link = "aitoolnotes.blogspot.com" in content
            has_tools_link = "tools.html" in content
            has_blog_feed_link = "blog.html" in content

            score = 0
            if has_clear_headline:
                score += 2
            if has_cta:
                score += 2
            if has_blog_link:
                score += 1
            if has_tools_link:
                score += 1
            if has_blog_feed_link:
                score += 1

            if not has_cta:
                self.issues.append({"page": "index.html", "issue": "missing_clear_cta"})
            if not has_tools_link:
                self.issues.append({"page": "index.html", "issue": "missing_tools_link"})

            self.record_action("audit", "index.html", "success",
                               {"score": score, "has_cta": has_cta})

        except Exception as e:
            self.record_action("audit", "index.html", "failed", error=str(e))

    def _audit_tools_page(self):
        """Audit the tools directory page."""
        try:
            tools_path = Path(__file__).resolve().parent.parent.parent / "github-io" / "tools.html"
            if not tools_path.exists():
                self.record_action("audit", "tools.html", "skipped",
                                   error="File not found")
                return

            content = tools_path.read_text(encoding="utf-8")

            # Check for search/filter functionality
            has_search = "search" in content.lower() or "filter" in content.lower()
            has_tool_cards = "tool-card" in content or "tool-item" in content
            has_external_links = "aitoolnotes.blogspot.com" in content

            score = 0
            if has_search:
                score += 2
            if has_tool_cards:
                score += 2
            if has_external_links:
                score += 1

            if not has_search:
                self.issues.append({"page": "tools.html", "issue": "missing_search"})
            if not has_external_links:
                self.issues.append({"page": "tools.html", "issue": "missing_blog_links"})

            self.record_action("audit", "tools.html", "success",
                               {"score": score, "has_search": has_search})

        except Exception as e:
            self.record_action("audit", "tools.html", "failed", error=str(e))

    def _audit_blog_page(self):
        """Audit the blog feed page."""
        try:
            blog_path = Path(__file__).resolve().parent.parent.parent / "github-io" / "blog.html"
            if not blog_path.exists():
                self.record_action("audit", "blog.html", "skipped",
                                   error="File not found")
                return

            content = blog_path.read_text(encoding="utf-8")

            # Check for RSS feed integration
            has_rss = "rss" in content.lower() or "feed" in content.lower()
            has_external_links = "aitoolnotes.blogspot.com" in content

            score = 0
            if has_rss:
                score += 2
            if has_external_links:
                score += 1

            if not has_rss:
                self.issues.append({"page": "blog.html", "issue": "missing_rss_feed"})

            self.record_action("audit", "blog.html", "success",
                               {"score": score, "has_rss": has_rss})

        except Exception as e:
            self.record_action("audit", "blog.html", "failed", error=str(e))

    def _generate_recommendations(self):
        """Generate optimization recommendations."""
        recommendations = []

        if any(i["issue"] == "missing_clear_cta" for i in self.issues):
            recommendations.append("Add a clear call-to-action button on the landing page directing users to the blog or tools directory")

        if any(i["issue"] == "missing_search" for i in self.issues):
            recommendations.append("Add search/filter functionality to the tools directory page")

        if any(i["issue"] == "missing_blog_links" for i in self.issues):
            recommendations.append("Add contextual links from tools directory to relevant blog articles")

        if any(i["issue"] == "missing_rss_feed" for i in self.issues):
            recommendations.append("Ensure blog.html properly fetches and displays RSS feed from Blogger")

        if any(i["issue"] == "missing_related_articles" for i in self.issues):
            recommendations.append("Add 'Related Articles' sections to all blog posts")

        self.recommendations = recommendations

        for rec in recommendations:
            self.record_action("recommendation", "conversion", "identified",
                               {"recommendation": rec[:100]})

    def _save_results(self):
        """Save optimization results."""
        filename = PATHS["reports"] / "conversion_audit.json"
        data = {
            "issues": self.issues,
            "recommendations": self.recommendations,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.record_action("save", str(filename), "success")
