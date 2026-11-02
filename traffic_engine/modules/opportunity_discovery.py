"""AIToolNotes Traffic Engine - Opportunity Discovery Module"""

import re
import json
import time
import random
from typing import List, Dict, Set
from datetime import datetime
from pathlib import Path

from traffic_engine.core.base import BaseModule, ActionRecord
from traffic_engine.config.settings import PATHS, SAFETY, SITES


class OpportunityDiscovery(BaseModule):
    """Discover high-potential traffic opportunities."""

    module_name = "opportunity_discovery"
    description = "Discover low-competition search queries and content gaps"

    def __init__(self):
        super().__init__()
        self.seen_queries: Set[str] = set()
        self.opportunities: List[Dict] = []

    def run(self) -> List[ActionRecord]:
        """Run opportunity discovery."""
        self.actions = []
        self.record_action("start", "opportunity_discovery", "started")

        # 1. Analyze existing content for gaps
        self._analyze_content_gaps()

        # 2. Discover related queries from sitemap
        self._discover_from_sitemap()

        # 3. Identify commercial-intent patterns
        self._discover_commercial_queries()

        # 4. Identify comparison/tutorial patterns
        self._discover_comparison_queries()

        # 5. Save opportunities
        self._save_opportunities()

        self.record_action("complete", "opportunity_discovery", "completed",
                           {"opportunities_found": len(self.opportunities)})
        return self.actions

    def _analyze_content_gaps(self):
        """Analyze existing articles for topic gaps."""
        try:
            from blog_automation import get_blogger_service
            import os
            os.environ.setdefault("GROQ_API_KEY", "dummy")
            os.environ.setdefault("BLOG_ID", "7352205941047679763")

            service = get_blogger_service()
            posts = service.posts().list(blogId="7352205941047679763", maxResults=500).execute()

            titles = [p["title"].lower() for p in posts.get("items", []) if p.get("title")]

            # Identify covered categories
            categories = set()
            for title in titles:
                if "video" in title:
                    categories.add("video")
                if "voice" in title or "audio" in title:
                    categories.add("voice")
                if "writing" in title:
                    categories.add("writing")
                if "marketing" in title:
                    categories.add("marketing")
                if "student" in title or "study" in title:
                    categories.add("students")
                if "teacher" in title or "education" in title:
                    categories.add("teachers")
                if "coding" in title or "developer" in title:
                    categories.add("coding")
                if "small business" in title or "entrepreneur" in title:
                    categories.add("business")
                if "productivity" in title:
                    categories.add("productivity")
                if "remote work" in title:
                    categories.add("remote_work")
                if "image" in title or "design" in title:
                    categories.add("image")
                if "music" in title:
                    categories.add("music")

            # Identify gaps
            all_categories = {
                "video", "voice", "writing", "marketing", "students", "teachers",
                "coding", "business", "productivity", "remote_work", "image",
                "music", "automation", "data", "research", "nonprofit"
            }
            gaps = all_categories - categories

            for gap in gaps:
                opportunity = {
                    "type": "content_gap",
                    "category": gap,
                    "title_suggestion": f"Best Free AI {gap.title()} Tools 2026",
                    "priority": "high" if gap in {"automation", "data", "research"} else "medium",
                    "source": "content_gap_analysis",
                    "discovered_at": datetime.utcnow().isoformat() + "Z",
                }
                self.opportunities.append(opportunity)

            self.record_action("analyze_gaps", "existing_content", "success",
                               {"categories_covered": len(categories), "gaps": len(gaps)})

        except Exception as e:
            self.record_action("analyze_gaps", "existing_content", "failed",
                               error=str(e))

    def _discover_from_sitemap(self):
        """Discover query patterns from existing sitemap URLs."""
        try:
            sitemap_path = Path(__file__).resolve().parent.parent / "sitemap.xml"
            if not sitemap_path.exists():
                return

            content = sitemap_path.read_text(encoding="utf-8")
            urls = re.findall(r'<loc>(.*?)</loc>', content)

            # Extract potential query terms from slugs
            query_terms: Set[str] = set()
            for url in urls:
                slug = url.split("/")[-1].replace(".html", "")
                # Remove numeric suffixes
                slug = re.sub(r'_[a-z0-9]+$', '', slug)
                # Convert dashes to spaces
                words = slug.replace("-", " ").split()
                # Extract meaningful terms
                for word in words:
                    if len(word) > 3 and word not in {"best", "free", "tools", "2026", "with", "what", "how", "for"}:
                        query_terms.add(word)

            for term in list(query_terms)[:20]:
                if term not in self.seen_queries:
                    self.seen_queries.add(term)
                    opportunity = {
                        "type": "sitemap_discovery",
                        "query_term": term,
                        "priority": "low",
                        "source": "sitemap_analysis",
                        "discovered_at": datetime.utcnow().isoformat() + "Z",
                    }
                    self.opportunities.append(opportunity)

            self.record_action("sitemap_analysis", "sitemap.xml", "success",
                               {"terms_found": len(query_terms)})

        except Exception as e:
            self.record_action("sitemap_analysis", "sitemap.xml", "failed",
                               error=str(e))

    def _discover_commercial_queries(self):
        """Identify commercial-intent search queries."""
        commercial_patterns = [
            "vs", "alternative", "pricing", "free tier", "review", "comparison",
            "best", "top", "which", "for beginners", "for students", "for business",
            "for marketing", "for content creators", "for teachers"
        ]

        base_topics = [
            "AI video generator", "AI voice generator", "AI writing tool",
            "AI image generator", "AI automation tool", "AI coding assistant",
            "AI presentation tool", "AI music generator", "AI resume builder",
            "AI chatbot", "AI agent", "AI productivity tool"
        ]

        for topic in base_topics:
            for pattern in commercial_patterns:
                query = f"{topic} {pattern}"
                if query not in self.seen_queries:
                    self.seen_queries.add(query)
                    opportunity = {
                        "type": "commercial_query",
                        "query": query,
                        "priority": "medium",
                        "source": "commercial_pattern_discovery",
                        "discovered_at": datetime.utcnow().isoformat() + "Z",
                    }
                    self.opportunities.append(opportunity)

        self.record_action("commercial_discovery", "query_patterns", "success",
                           {"queries_generated": len(base_topics) * len(commercial_patterns)})

    def _discover_comparison_queries(self):
        """Identify comparison and tutorial queries."""
        comparison_templates = [
            "{tool_a} vs {tool_b}",
            "how to use {tool}",
            "{tool} tutorial",
            "{tool} for {use_case}",
            "is {tool} free",
            "{tool} free tier",
        ]

        tools = [
            "CapCut", "Canva AI", "Grammarly", "Notion AI", "Runway ML",
            "ElevenLabs", "HeyGen", "Synthesia", "Midjourney", "DALL-E",
            "Stable Diffusion", "GitHub Copilot", "Claude", "ChatGPT",
            "n8n", "Make", "Zapier", "Buffer", "Mailchimp", "Tidio"
        ]

        use_cases = [
            "beginners", "students", "teachers", "small business",
            "content creators", "YouTube", "podcasts", "marketing",
            "freelancers", "nonprofits", "entrepreneurs"
        ]

        count = 0
        for template in comparison_templates:
            if "{tool_a}" in template and "{tool_b}" in template:
                for i, tool_a in enumerate(tools[:10]):
                    for tool_b in tools[i+1:i+3]:
                        query = template.format(tool_a=tool_a, tool_b=tool_b)
                        if query not in self.seen_queries:
                            self.seen_queries.add(query)
                            self.opportunities.append({
                                "type": "comparison_query",
                                "query": query,
                                "priority": "high",
                                "source": "comparison_templates",
                                "discovered_at": datetime.utcnow().isoformat() + "Z",
                            })
                            count += 1
            elif "{tool}" in template and "{use_case}" in template:
                for tool in tools[:8]:
                    for use_case in use_cases[:4]:
                        query = template.format(tool=tool, use_case=use_case)
                        if query not in self.seen_queries:
                            self.seen_queries.add(query)
                            self.opportunities.append({
                                "type": "tutorial_query",
                                "query": query,
                                "priority": "medium",
                                "source": "tutorial_templates",
                                "discovered_at": datetime.utcnow().isoformat() + "Z",
                            })
                            count += 1
            elif "{tool}" in template:
                for tool in tools[:10]:
                    query = template.format(tool=tool)
                    if query not in self.seen_queries:
                        self.seen_queries.add(query)
                        self.opportunities.append({
                            "type": "tutorial_query",
                            "query": query,
                            "priority": "medium",
                            "source": "tutorial_templates",
                            "discovered_at": datetime.utcnow().isoformat() + "Z",
                        })
                        count += 1

        self.record_action("comparison_discovery", "query_templates", "success",
                           {"queries_generated": count})

    def _save_opportunities(self):
        """Save opportunities to disk."""
        filename = PATHS["reports"] / "opportunities.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.opportunities, f, indent=2)
        self.record_action("save", str(filename), "success",
                           {"count": len(self.opportunities)})

    def get_top_opportunities(self, limit: int = 20) -> List[Dict]:
        """Get top-priority opportunities."""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_opps = sorted(
            self.opportunities,
            key=lambda x: (priority_order.get(x.get("priority", "low"), 3),
                          x.get("type", ""))
        )
        return sorted_opps[:limit]
