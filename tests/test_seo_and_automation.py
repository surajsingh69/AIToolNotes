import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import blog_automation as ba
import seo_utils
import setup_blogger_adsense as sba


class TestNicheFilteringAndScoring(unittest.TestCase):
    def test_rejects_off_topic_news(self):
        off_topic = [
            ("3 ways to prep for your next big race with Search", "https://blog.google/products/search/running-race-training-tips/"),
            ("Get ready for the game with new football features in Search", "https://blog.google/products/search/football-features-google-search/"),
            ("Supporting independent journalism in Ukraine", "https://openai.com/index/supporting-independent-journalism-in-ukraine"),
            ("Data center demand drives 66% surge in natural gas power plant costs", "https://techcrunch.com/gas"),
        ]
        for title, url in off_topic:
            with self.subTest(title=title):
                self.assertTrue(seo_utils.is_off_topic_candidate(title, url))

    def test_accepts_ai_tool_topics(self):
        on_topic = [
            ("Notion AI Workflow Automation Pricing Guide", "https://www.notion.so/blog/notion-ai"),
            ("How to Build Coding Agents with Claude API", "https://www.anthropic.com/news/claude-agents"),
            ("Hugging Face Fine-Tuning Guide for Small LLMs", "https://huggingface.co/blog/fine-tuning"),
        ]
        for title, url in on_topic:
            with self.subTest(title=title):
                self.assertFalse(seo_utils.is_off_topic_candidate(title, url))

    def test_pre_score_prefers_high_intent_and_affiliate(self):
        tutorial = {
            "title": "Notion AI Automation Pricing and Workflow Guide",
            "link": "https://www.notion.so/blog/ai-workflow",
            "source": "Notion",
            "published": "",
        }
        vague = {
            "title": "The Work Now Within Reach",
            "link": "https://openai.com/index/the-work-now-within-reach",
            "source": "OpenAI",
            "published": "",
        }
        s_tut = seo_utils.pre_score_candidate(
            tutorial,
            ba.freshness_score,
            {"notion": ["notion", "notion ai"]},
        )
        s_vague = seo_utils.pre_score_candidate(
            vague,
            ba.freshness_score,
            {"notion": ["notion", "notion ai"]},
        )
        self.assertGreater(s_tut, s_vague)

    def test_build_candidate_pool_filters_and_sorts(self):
        topics = [
            {"title": "Get ready for the game with new football features", "link": "https://example.com/1", "source": "Google AI Blog", "published": ""},
            {"title": "The Work Now Within Reach in AI", "link": "https://example.com/2", "source": "OpenAI", "published": ""},
            {"title": "Claude API Pricing and Coding Agent Guide", "link": "https://example.com/3", "source": "Anthropic", "published": ""},
            {"title": "Already Posted AI Tool Review", "link": "https://example.com/posted", "source": "Product Hunt AI", "published": ""},
        ]
        pool = ba.build_candidate_pool(
            topics,
            posted_titles={"Already Posted AI Tool Review"},
            posted_links={"https://example.com/posted"},
        )
        titles = [item["title"] for item in pool]
        self.assertNotIn("Get ready for the game with new football features", titles)
        self.assertNotIn("Already Posted AI Tool Review", titles)
        self.assertEqual(pool[0]["title"], "Claude API Pricing and Coding Agent Guide")


class TestSeoHeadlinesLabelsAndLinks(unittest.TestCase):
    def test_seo_headline_prefers_keyword_intent(self):
        brief = {"primary_keyword": "claude code"}
        good = "Claude Code Review: Pricing, Limits, and Workflow Guide"
        vague = "The Future of Work Is Within Reach!"
        self.assertGreater(
            seo_utils.seo_headline_score(good, brief),
            seo_utils.seo_headline_score(vague, brief),
        )

    def test_build_blogger_labels(self):
        brief = {
            "article_type": "practical_guide",
            "primary_keyword": "langchain agents",
            "secondary_keywords": ["tool calling", "python sdk", "very long keyword phrase with too many words"],
        }
        labels = seo_utils.build_blogger_labels(brief, "LangChain", max_labels=5)
        self.assertIn("AI Tutorials", labels)
        self.assertIn("Langchain Agents", labels)
        self.assertLessEqual(len(labels), 5)

    def test_inbody_internal_linking_does_not_nest_anchors(self):
        html_input = (
            "<h2>Overview</h2>"
            "<p>Teams using LangChain Agents can connect APIs quickly. "
            "Read <a href=\"https://other.com\">LangChain Agents docs</a> too.</p>"
        )
        picks = [
            {
                "title": "LangChain Agents Complete Guide",
                "primary_keyword": "LangChain Agents",
                "post_url": "https://aitoolnotes.blogspot.com/2026/09/langchain-agents.html",
            }
        ]
        out = seo_utils.inject_contextual_inbody_links(html_input, picks, max_inbody=1)
        self.assertIn("https://aitoolnotes.blogspot.com/2026/09/langchain-agents.html", out)
        self.assertNotIn("<a href=\"https://other.com\"><a", out)

    def test_affiliate_injection_adds_disclosure(self):
        content = "<h2>Overview</h2><p>Notion helps teams automate summaries.</p>"
        with patch.dict(ba.AFFILIATE_LINKS, {"notion": "https://partner.example.com/notion"}):
            out = ba.inject_contextual_affiliate_links(content, {})
        self.assertIn('href="https://partner.example.com/notion"', out)
        self.assertIn("affiliate links", out.lower())

    def test_google_autocomplete_handles_network_errors(self):
        with patch("seo_utils.requests.get", side_effect=OSError("offline")):
            self.assertEqual(seo_utils.fetch_google_autocomplete_suggestions("claude ai"), [])

    def test_html_validation_passes_structured_seo_article(self):
        sample_body = " ".join(["word"] * 120)
        html_doc = (
            f"<p>{sample_body}</p>"
            "<h2>Key Takeaways</h2><ul><li>Fast setup</li></ul>"
            "<h2>Comparison Table</h2><table><tr><th>Plan</th><th>Price</th></tr><tr><td>Pro</td><td>$20</td></tr></table>"
        )
        cleaned, issues = ba.validate_and_clean_html(html_doc)
        self.assertEqual(issues, [])
        self.assertIn("<table>", cleaned)

    def test_atom_short_title_merges_summary_for_product_hunt(self):
        atom_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>MemoryWorks</title>
            <link rel="alternate" href="https://www.producthunt.com/products/memoryworks"/>
            <published>2026-11-24T10:00:00Z</published>
            <content type="html">&lt;p&gt;Persistent AI agent memory workspace for coding teams.&lt;/p&gt;</content>
          </entry>
        </feed>"""
        fake_resp = SimpleNamespace(content=atom_xml, raise_for_status=lambda: None)
        with patch("blog_automation.requests.get", return_value=fake_resp):
            items = ba.get_rss_items("https://example.com/feed", "Product Hunt AI", limit=5)
        self.assertEqual(len(items), 1)
        self.assertIn("MemoryWorks", items[0]["title"])
        self.assertIn("Persistent AI agent memory", items[0]["title"])


class TestBloggerAdsenseSetup(unittest.TestCase):
    def test_ensure_trust_pages_is_idempotent(self):
        service = MagicMock()
        service.pages().list().execute.return_value = {
            "items": [{"title": "About"}]
        }
        summary = sba.ensure_trust_pages(service, "blog-123", dry_run=False, contact_email="hi@aitoolnotes.com")
        service.pages().list.assert_called_with(blogId="blog-123", status="LIVE")
        self.assertEqual(summary["skipped"], ["About"])
        self.assertEqual(len(summary["created"]), 3)
        self.assertEqual(service.pages().insert.call_count, 3)

    def test_cleanup_off_topic_posts_reverts_only_offtopic(self):
        service = MagicMock()
        service.posts().list().execute.return_value = {
            "items": [
                {"id": "1", "title": "Get ready for the game with new football features in Search", "url": "https://x/1"},
                {"id": "2", "title": "Claude Code Workflow Automation Guide", "url": "https://x/2"},
            ]
        }
        reverted = sba.cleanup_off_topic_posts(service, "blog-123", dry_run=False)
        service.posts().list.assert_called_with(blogId="blog-123", status="LIVE", maxResults=50)
        self.assertEqual(reverted, ["Get ready for the game with new football features in Search"])
        service.posts().revert.assert_called_once_with(blogId="blog-123", postId="1")


if __name__ == "__main__":
    unittest.main()
