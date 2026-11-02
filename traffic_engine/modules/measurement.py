"""AIToolNotes Traffic Engine - Traffic Measurement Module"""

import json
import re
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, SITES


class TrafficMeasurement(BaseModule):
    """Track and report traffic metrics."""

    module_name = "measurement"
    description = "Track organic clicks, impressions, referrals, and engagement"

    def __init__(self):
        super().__init__()
        self.metrics: Dict[str, any] = {}
        self.history_file = PATHS["reports"] / "metrics_history.json"

    def run(self) -> List[ActionRecord]:
        """Collect and report metrics."""
        self.actions = []
        self.record_action("start", "measurement", "started")

        # 1. Count published articles
        self._count_articles()

        # 2. Check sitemap status
        self._check_sitemap()

        # 3. Check robots.txt
        self._check_robots()

        # 4. Estimate traffic potential
        self._estimate_traffic_potential()

        # 5. Save metrics
        self._save_metrics()

        # 6. Generate report
        self._generate_report()

        self.record_action("complete", "measurement", "completed",
                           {"metrics_collected": len(self.metrics)})
        return self.actions

    def _count_articles(self):
        """Count published and draft articles."""
        try:
            import os
            os.environ.setdefault("GROQ_API_KEY", "dummy")
            os.environ.setdefault("BLOG_ID", "7352205941047679763")
            from blog_automation import get_blogger_service

            service = get_blogger_service()
            posts = service.posts().list(blogId="7352205941047679763", maxResults=500).execute()
            items = posts.get("items", [])

            total = len(items)
            published = sum(1 for p in items if p.get("published"))
            drafts = total - published

            self.metrics["total_posts"] = total
            self.metrics["published_posts"] = published
            self.metrics["draft_posts"] = drafts

            self.record_action("count_articles", "blogger", "success",
                               {"total": total, "published": published, "drafts": drafts})

        except Exception as e:
            self.record_action("count_articles", "blogger", "failed", error=str(e))
            # Fallback: count from sitemap
            try:
                sitemap_path = Path(__file__).resolve().parent.parent.parent / "sitemap.xml"
                if sitemap_path.exists():
                    content = sitemap_path.read_text(encoding="utf-8")
                    url_count = content.count("<url>")
                    self.metrics["sitemap_urls"] = url_count
                    self.record_action("count_articles", "sitemap", "success",
                                       {"urls": url_count})
            except Exception as e2:
                self.record_action("count_articles", "sitemap", "failed", error=str(e2))

    def _check_sitemap(self):
        """Check sitemap status."""
        try:
            sitemap_path = Path(__file__).resolve().parent.parent.parent / "sitemap.xml"
            if sitemap_path.exists():
                content = sitemap_path.read_text(encoding="utf-8")
                url_count = content.count("<url>")
                self.metrics["sitemap_urls"] = url_count
                self.record_action("check_sitemap", "sitemap.xml", "success",
                                   {"urls": url_count})
            else:
                self.record_action("check_sitemap", "sitemap.xml", "failed",
                                   error="File not found")
        except Exception as e:
            self.record_action("check_sitemap", "sitemap.xml", "failed", error=str(e))

    def _check_robots(self):
        """Check robots.txt status."""
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://aitoolnotes.blogspot.com/robots.txt",
                headers={"User-Agent": SAFETY["user_agent"]}
            )
            with urllib.request.urlopen(req, timeout=SAFETY["request_timeout"]) as resp:
                content = resp.read().decode("utf-8")
                has_sitemap = "sitemap" in content.lower()
                self.metrics["robots_txt_valid"] = True
                self.metrics["robots_has_sitemap"] = has_sitemap
                self.record_action("check_robots", "robots.txt", "success",
                                   {"has_sitemap": has_sitemap})
        except Exception as e:
            self.metrics["robots_txt_valid"] = False
            self.record_action("check_robots", "robots.txt", "failed", error=str(e))

    def _estimate_traffic_potential(self):
        """Estimate traffic potential based on current state."""
        article_count = self.metrics.get("published_posts", 0) or self.metrics.get("sitemap_urls", 0)

        # Conservative estimate: 10-50 views/article/day at 100 articles
        if article_count >= 100:
            estimated_daily = article_count * 15
        elif article_count >= 50:
            estimated_daily = article_count * 10
        else:
            estimated_daily = article_count * 5

        estimated_monthly = estimated_daily * 30

        self.metrics["estimated_daily_views"] = estimated_daily
        self.metrics["estimated_monthly_views"] = estimated_monthly
        self.metrics["target_gap"] = max(0, 50000 - estimated_monthly)

        self.record_action("estimate_traffic", "potential", "success",
                           {"daily": estimated_daily, "monthly": estimated_monthly,
                            "target_gap": self.metrics["target_gap"]})

    def _save_metrics(self):
        """Save metrics to disk."""
        self.metrics["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Update history
        history = []
        if self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                history = json.load(f)

        history.append(self.metrics)
        # Keep last 90 days
        cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"
        history = [h for h in history if h.get("timestamp", "") >= cutoff]

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        self.record_action("save", str(self.history_file), "success",
                           {"history_days": len(history)})

    def _generate_report(self):
        """Generate human-readable report."""
        report_lines = [
            "=" * 60,
            "AIToolNotes Traffic Report",
            f"Generated: {datetime.utcnow().isoformat()}Z",
            "=" * 60,
            f"Published posts: {self.metrics.get('published_posts', 'N/A')}",
            f"Sitemap URLs: {self.metrics.get('sitemap_urls', 'N/A')}",
            f"Estimated daily views: {self.metrics.get('estimated_daily_views', 'N/A')}",
            f"Estimated monthly views: {self.metrics.get('estimated_monthly_views', 'N/A')}",
            f"Target gap: {self.metrics.get('target_gap', 'N/A')} monthly views",
            "=" * 60,
        ]

        report = "\n".join(report_lines)
        report_path = PATHS["reports"] / "latest_report.txt"
        report_path.write_text(report, encoding="utf-8")

        self.record_action("report", str(report_path), "success")

    def get_metrics_summary(self) -> Dict:
        """Get current metrics summary."""
        return self.metrics
