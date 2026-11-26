"""SEO, niche relevance, search intent, and monetization helpers for AIToolNotes."""

from __future__ import annotations

import html
import json
import os
import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup, NavigableString


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
    )
}

# Curated AI tools, developer platforms, and high-RPM SaaS sources.
# Replaces unfocused general news feeds with tool-centric changelogs and blogs.
CURATED_AI_TOOL_SOURCES: list[tuple[str, str]] = [
    ("https://openai.com/news/rss.xml", "OpenAI"),
    ("https://blog.google/technology/ai/rss/", "Google AI Blog"),
    ("https://huggingface.co/blog/feed.xml", "Hugging Face"),
    ("https://techcrunch.com/tag/artificial-intelligence/feed/", "TechCrunch AI"),
    ("https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml", "Anthropic"),
    ("https://github.blog/ai-and-ml/feed/", "GitHub Blog AI"),
    ("https://zapier.com/blog/feeds/latest/", "Zapier AI"),
    ("https://blog.cloudflare.com/rss/", "Cloudflare AI"),
    ("https://simonwillison.net/atom/everything/", "Simon Willison AI"),
]

# Strong positive signals for AI tool tutorials, workflows, pricing, and comparisons.
AI_NICHE_POSITIVE_TERMS: dict[str, float] = {
    "ai": 1.2,
    "llm": 1.4,
    "gpt": 1.3,
    "claude": 1.4,
    "gemini": 1.3,
    "copilot": 1.5,
    "agent": 1.4,
    "agents": 1.4,
    "coding": 1.3,
    "code": 1.1,
    "api": 1.4,
    "sdk": 1.2,
    "workflow": 1.4,
    "automation": 1.5,
    "automate": 1.4,
    "tool": 1.2,
    "tools": 1.2,
    "model": 1.0,
    "benchmark": 1.3,
    "pricing": 1.8,
    "review": 1.6,
    "comparison": 1.6,
    "alternative": 1.6,
    "alternatives": 1.6,
    "tutorial": 1.5,
    "guide": 1.4,
    "prompt": 1.2,
    "rag": 1.4,
    "fine-tuning": 1.4,
    "open-source": 1.3,
    "open source": 1.3,
    "chatbot": 1.2,
    "voice": 1.0,
    "video": 1.0,
    "image": 1.0,
    "workspace": 1.2,
    "notion": 1.3,
    "assistant": 1.2,
    "productivity": 1.3,
    "saas": 1.4,
    "enterprise": 1.1,
}

# Off-topic / low-RPM / non-tool themes that previously leaked from broad RSS feeds.
OFF_TOPIC_PENALTY_TERMS: tuple[str, ...] = (
    "football",
    "soccer",
    "race",
    "marathon",
    "love story",
    "astronaut",
    "ukraine",
    "journalism",
    "natural gas",
    "power plant",
    "election",
    "senate",
    "congress",
    "lawsuit",
    "antitrust",
    "music festival",
    "celebrity",
    "movie trailer",
    "olympics",
    "policy window",
    "societal impact",
    "dialogues",
    "subscribe",
    "newsletter",
    "podcast episode",
    "weekly roundup",
    "job opening",
    "hiring",
)

HIGH_INTENT_TITLE_PATTERNS: tuple[str, ...] = (
    "how to",
    "guide",
    "tutorial",
    "review",
    "pricing",
    "vs",
    "versus",
    "alternative",
    "alternatives",
    "benchmark",
    "workflow",
    "features",
    "explained",
    "what is",
    "best ",
    "for developers",
    "for teams",
)

VAGUE_TITLE_PATTERNS: tuple[str, ...] = (
    "within reach",
    "put data to work",
    "reimagining",
    "the future of",
    "a new era",
    "for everyone",
    "the latest",
    "watch ",
)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_off_topic_candidate(title: str, url: str = "") -> bool:
    """Return True when a candidate clearly falls outside AI tools / software workflows."""
    combined = f"{title} {url}".lower()
    if any(term in combined for term in OFF_TOPIC_PENALTY_TERMS):
        return True

    # Require at least one AI/software/tool indicator in the title or URL.
    words = set(re.findall(r"[a-z0-9\-]+", combined))
    has_ai_signal = any(
        term in combined
        for term in (
            "ai",
            "gpt",
            "llm",
            "claude",
            "gemini",
            "openai",
            "anthropic",
            "huggingface",
            "hugging face",
            "langchain",
            "copilot",
            "codex",
            "agent",
            "model",
            "automation",
            "workflow",
            "api",
            "sdk",
            "software",
            "app",
            "tool",
            "saas",
            "coding",
            "developer",
            "multimodal",
            "vercel",
            "notion",
        )
    )
    if not has_ai_signal and not (words & set(AI_NICHE_POSITIVE_TERMS)):
        return True

    return False


def pre_score_candidate(
    topic: dict,
    freshness_fn,
    affiliate_aliases: dict[str, list[str]] | None = None,
) -> float:
    """
    Deterministically rank RSS candidates before making LLM calls.

    Prioritizes fresh AI-tool, developer, workflow, and high-commercial-intent topics
    so LLM budget focuses on rankable, monetizable candidates.
    """
    title = _clean_text(topic.get("title", ""))
    url = _clean_text(topic.get("link", ""))
    source = _clean_text(topic.get("source", ""))
    published = _clean_text(topic.get("published", ""))

    if is_off_topic_candidate(title, url):
        return -100.0

    combined = f"{title} {url}".lower()
    score = 0.0

    for term, weight in AI_NICHE_POSITIVE_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", combined):
            score += weight

    for pattern in HIGH_INTENT_TITLE_PATTERNS:
        if pattern in combined:
            score += 1.5

    for pattern in VAGUE_TITLE_PATTERNS:
        if pattern in combined:
            score -= 1.5

    # Prefer buyer-intent and actionable SaaS/tool blogs over pure research news.
    source_boost = {
        "Zapier AI": 1.9,
        "Anthropic": 1.4,
        "OpenAI": 1.3,
        "GitHub Blog AI": 1.3,
        "Hugging Face": 1.1,
        "Cloudflare AI": 1.1,
        "Simon Willison AI": 1.0,
        "Google AI Blog": 1.0,
        "TechCrunch AI": 0.7,
    }
    score += source_boost.get(source, 0.5)

    # Extra high-CPC commercial intent bonus for comparisons, pricing, and "best" roundups.
    commercial_patterns = (
        "vs",
        "versus",
        "pricing",
        "review",
        "best ",
        "alternative",
        "alternatives",
        "comparison",
        "for teams",
        "for business",
    )
    if any(p in combined for p in commercial_patterns):
        score += 2.2

    # Freshness carries meaningful weight for news-assisted evergreen guides.
    score += freshness_fn(published) * 0.4

    # Boost if a configured affiliate tool is directly mentioned.
    if affiliate_aliases:
        for aliases in affiliate_aliases.values():
            if any(re.search(rf"\b{re.escape(a.lower())}\b", combined) for a in aliases):
                score += 2.5
                break

    return round(score, 3)


def fetch_google_autocomplete_suggestions(
    seed_query: str,
    max_results: int = 6,
    timeout: int = 5,
) -> list[str]:
    """
    Query Google Suggest for real user search phrasing around a topic/tool.
    Returns [] safely on network errors or unexpected responses.
    """
    seed = _clean_text(seed_query)
    if not seed or len(seed) < 3:
        return []

    url = (
        "https://suggestqueries.google.com/complete/search"
        f"?client=firefox&hl=en&q={quote_plus(seed)}"
    )
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list) and len(payload) >= 2 and isinstance(payload[1], list):
            suggestions = [
                _clean_text(str(item))
                for item in payload[1]
                if _clean_text(str(item)) and _clean_text(str(item)).lower() != seed.lower()
            ]
            return suggestions[:max_results]
    except Exception:
        return []

    return []


def collect_keyword_suggestions(
    topic_title: str,
    primary_keyword: str = "",
    enable_network: bool = True,
) -> list[str]:
    """Gather real Google search autocomplete variations for SEO heading alignment."""
    if not enable_network:
        return []

    seeds: list[str] = []
    if primary_keyword:
        seeds.append(primary_keyword)
    else:
        # Take leading meaningful phrase from title (up to 5 words).
        words = re.findall(r"[A-Za-z0-9\-\.+]+", topic_title or "")
        if words:
            seeds.append(" ".join(words[:4]))

    collected: list[str] = []
    for seed in seeds[:2]:
        for item in fetch_google_autocomplete_suggestions(seed):
            if item.lower() not in {x.lower() for x in collected}:
                collected.append(item)

    return collected[:8]


def seo_headline_score(headline: str, brief: dict) -> float:
    """Score headline options for Google SERP CTR and search-intent clarity."""
    headline = _clean_text(headline)
    if not headline:
        return -999.0

    score = 0.0
    length = len(headline)
    if 42 <= length <= 62:
        score += 2.5
    elif length <= 70:
        score += 1.5
    elif length <= 82:
        score += 0.5
    elif length > 95:
        score -= 3.0

    lowered = headline.lower()
    primary = _clean_text(brief.get("primary_keyword", "")).lower()
    if primary:
        if lowered.startswith(primary):
            score += 2.5
        elif primary in lowered:
            score += 2.0

    if any(p in lowered for p in HIGH_INTENT_TITLE_PATTERNS):
        score += 1.5

    if any(p in lowered for p in VAGUE_TITLE_PATTERNS):
        score -= 2.5

    # Numbers or concrete years/versions increase SERP specificity when truthful.
    if re.search(r"\b(202[5-9]|[0-9]+)\b", headline):
        score += 0.5

    banned = (
        "shocking",
        "you won't believe",
        "insane",
        "game-changing",
        "revolutionary",
        "guaranteed",
        "secret",
        "destroy",
        "finally!",
    )
    for phrase in banned:
        if phrase in lowered:
            score -= 3.5

    if "!" in headline:
        score -= 1.0

    return score


def build_blogger_labels(brief: dict, source_name: str, max_labels: int = 5) -> list[str]:
    """
    Generate clean Blogger taxonomy labels for topic clustering and crawlable label pages.
    Blogger rejects labels > 200 chars and dislikes noisy punctuation.
    """
    labels: list[str] = []
    seen: set[str] = set()

    def add_label(raw: str) -> None:
        cleaned = re.sub(r"[,#&]+", " ", _clean_text(raw))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned or len(cleaned) < 2 or len(cleaned) > 40:
            return
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            labels.append(cleaned)

    article_type_map = {
        "practical_guide": "AI Tutorials",
        "tool_review": "AI Tool Reviews",
        "comparison": "AI Comparisons",
        "roundup": "AI Tool Roundups",
        "analysis": "AI Analysis",
        "news_explainer": "AI Updates",
    }
    article_type = _clean_text(brief.get("article_type", ""))
    add_label(article_type_map.get(article_type, "AI Tools"))

    primary_kw = _clean_text(brief.get("primary_keyword", ""))
    if primary_kw:
        add_label(primary_kw.title() if primary_kw.islower() else primary_kw)

    for kw in brief.get("secondary_keywords", [])[:3]:
        if len(labels) >= max_labels:
            break
        kw_clean = _clean_text(str(kw))
        if len(kw_clean.split()) <= 3:
            add_label(kw_clean.title() if kw_clean.islower() else kw_clean)

    if source_name and len(labels) < max_labels:
        add_label(source_name)

    return labels[:max_labels]


def inject_contextual_inbody_links(
    content: str,
    picks: list[dict],
    max_inbody: int = 1,
) -> str:
    """
    Safely insert up to `max_inbody` contextual internal links inside existing <p> text
    when an anchor keyword from a prior article appears naturally, avoiding headings/links.
    """
    if not content or not picks or max_inbody <= 0:
        return content

    soup = BeautifulSoup(content, "html.parser")
    inserted = 0

    for candidate in picks:
        if inserted >= max_inbody:
            break
        post_url = _clean_text(candidate.get("post_url", ""))
        anchor_kw = _clean_text(candidate.get("primary_keyword", ""))
        if not post_url or not anchor_kw or len(anchor_kw) < 4:
            continue

        # Skip if already linked.
        if any((a.get("href") or "").strip() == post_url for a in soup.find_all("a")):
            continue

        pattern = re.compile(rf"\b{re.escape(anchor_kw)}\b", re.I)

        for p_tag in soup.find_all("p"):
            did_replace = False
            for text_node in list(p_tag.find_all(string=True)):
                if not isinstance(text_node, NavigableString):
                    continue
                if text_node.parent and text_node.parent.name == "a":
                    continue
                node_str = str(text_node)
                match = pattern.search(node_str)
                if not match:
                    continue

                start, end = match.span()
                before, matched, after = node_str[:start], node_str[start:end], node_str[end:]
                parts = []
                if before:
                    parts.append(NavigableString(before))
                a_tag = soup.new_tag(
                    "a",
                    href=post_url,
                    title=_clean_text(candidate.get("title", "")),
                )
                a_tag["rel"] = ["noopener"]
                a_tag.string = matched
                parts.append(a_tag)
                if after:
                    parts.append(NavigableString(after))

                for item in reversed(parts):
                    text_node.insert_after(item)
                text_node.extract()
                inserted += 1
                did_replace = True
                break

            if did_replace:
                break

    return str(soup)


def load_affiliate_config(base_dir: str, env_links: dict[str, str], env_aliases: dict[str, list[str]]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """
    Merge environment-configured affiliate URLs with optional local `affiliates.json`.
    Expected JSON format: {"tool_key": {"url": "https://...", "aliases": ["Tool", "Tool AI"]}}
    """
    links = dict(env_links)
    aliases = {k: list(v) for k, v in env_aliases.items()}

    config_path = os.path.join(base_dir, "affiliates.json")
    if not os.path.exists(config_path):
        return links, aliases

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                url = _clean_text(entry.get("url", ""))
                if url and not links.get(key):
                    links[key] = url
                extra_aliases = entry.get("aliases", [])
                if isinstance(extra_aliases, list) and extra_aliases:
                    aliases[key] = [
                        _clean_text(str(a))
                        for a in extra_aliases
                        if _clean_text(str(a))
                    ]
    except Exception:
        pass

    return links, aliases


def append_affiliate_disclosure(content: str, has_affiliate_link: bool) -> str:
    """Prepend a concise FTC/AdSense-compliant affiliate disclosure when affiliate links exist."""
    if not has_affiliate_link or not content:
        return content

    disclosure = (
        '<p><em>Disclosure: Some links in this guide are affiliate links, '
        'meaning AIToolNotes may earn a commission at no extra cost to you.</em></p>'
    )
    if "affiliate links" in content.lower():
        return content
    return disclosure + content
