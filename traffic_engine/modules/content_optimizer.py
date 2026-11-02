"""AIToolNotes Traffic Engine - Content Optimization Module"""

import re
import json
import hashlib
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, SITES


class ContentOptimizer(BaseModule):
    """Audit and optimize existing content for SEO and engagement."""

    module_name = "content_optimization"
    description = "Audit articles, improve titles/descriptions, add internal links"

    # Minimum content thresholds
    MIN_WORD_COUNT = 800
    MIN_HEADINGS = 3
    MIN_INTERNAL_LINKS = 2

    def __init__(self):
        super().__init__()
        self.audit_results: List[Dict] = []

    def run(self) -> List[ActionRecord]:
        """Run content audit and optimization."""
        self.actions = []
        self.record_action("start", "content_optimization", "started")

        # 1. Audit existing articles
        self._audit_articles()

        # 2. Identify optimization opportunities
        self._identify_optimizations()

        # 3. Save audit results
        self._save_audit()

        self.record_action("complete", "content_optimization", "completed",
                           {"articles_audited": len(self.audit_results)})
        return self.actions

    def _audit_articles(self):
        """Audit all existing markdown articles."""
        articles_dir = Path(__file__).resolve().parent.parent.parent / "articles"
        if not articles_dir.exists():
            self.record_action("audit", str(articles_dir), "skipped",
                               error="Articles directory not found")
            return

        article_files = list(articles_dir.glob("*.md"))
        self.record_action("audit_start", str(articles_dir), "started",
                           {"article_count": len(article_files)})

        for article_path in article_files:
            try:
                content = article_path.read_text(encoding="utf-8")
                result = self._audit_single_article(article_path, content)
                self.audit_results.append(result)
            except Exception as e:
                self.record_action("audit_article", str(article_path), "failed",
                                   error=str(e))

    def _audit_single_article(self, path: Path, content: str) -> Dict:
        """Audit a single article."""
        lines = content.split("\n")
        words = len(content.split())

        # Extract title
        title = ""
        for line in lines:
            if line.startswith("# "):
                title = line.replace("# ", "").strip()
                break

        # Count headings
        headings = [l for l in lines if l.startswith("#")]

        # Count internal links
        internal_links = re.findall(r'\[.*?\]\((.*?)\)', content)
        internal_count = sum(1 for link in internal_links
                            if "aitoolnotes.blogspot.com" in link or
                               "surajsingh69.github.io" in link)

        # Check for related articles section
        has_related = "## Related Articles" in content or "## Related" in content

        # Check for FAQ section
        has_faq = "## Frequently Asked Questions" in content or "## FAQ" in content

        # Calculate quality score (0-10)
        score = 0
        if words >= 1000:
            score += 3
        elif words >= 500:
            score += 2
        elif words >= 300:
            score += 1

        if len(headings) >= 5:
            score += 2
        elif len(headings) >= 3:
            score += 1

        if internal_count >= 3:
            score += 2
        elif internal_count >= 1:
            score += 1

        if has_related:
            score += 1
        if has_faq:
            score += 1
        if title and len(title) > 20:
            score += 1

        # Identify issues
        issues = []
        if words < self.MIN_WORD_COUNT:
            issues.append(f"thin_content ({words} words, min {self.MIN_WORD_COUNT})")
        if len(headings) < self.MIN_HEADINGS:
            issues.append(f"few_headings ({len(headings)}, min {self.MIN_HEADINGS})")
        if internal_count < self.MIN_INTERNAL_LINKS:
            issues.append(f"few_internal_links ({internal_count}, min {self.MIN_INTERNAL_LINKS})")
        if not title:
            issues.append("missing_title")
        if not has_related:
            issues.append("missing_related_articles")
        if not has_faq:
            issues.append("missing_faq")

        return {
            "path": str(path.name),
            "title": title,
            "word_count": words,
            "headings": len(headings),
            "internal_links": internal_count,
            "has_related": has_related,
            "has_faq": has_faq,
            "score": score,
            "issues": issues,
            "optimized": False,
        }

    def _identify_optimizations(self):
        """Identify which articles need optimization."""
        for article in self.audit_results:
            if article["issues"]:
                self.record_action(
                    "identify_optimization",
                    article["path"],
                    "needs_work",
                    {"score": article["score"], "issues": article["issues"]}
                )

    def _save_audit(self):
        """Save audit results to disk."""
        filename = PATHS["reports"] / "content_audit.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.audit_results, f, indent=2)
        self.record_action("save", str(filename), "success",
                           {"count": len(self.audit_results)})

    def get_low_scoring_articles(self, max_score: int = 5) -> List[Dict]:
        """Get articles that need optimization."""
        return [a for a in self.audit_results if a["score"] <= max_score]

    def get_optimization_candidates(self) -> List[Dict]:
        """Get articles ready for safe optimization."""
        return [a for a in self.audit_results
                if not a["optimized"] and a["score"] < 8 and a["word_count"] >= 300]
