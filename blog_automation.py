# AIToolNotes Intelligent Blog Automation v4
# RSS -> source extraction -> editorial intelligence -> evidence ledger
# -> headline/SEO/engagement -> writer -> deterministic HTML checks
# -> fact/quality gate -> one revision -> contextual links -> Blogger
#
# Notes:
# - Keeps the evidence-first architecture from v3.
# - Adds topic scoring, headline generation, SEO intent, hook strategy,
#   engagement checks, source attribution, contextual affiliate placement,
#   and smarter internal-link selection.
# - Does NOT use outside facts when writing an article.
#
# Required environment variables:
#   GROQ_API_KEY
#   BLOG_ID
#
# Google Blogger OAuth files:
#   credentials.json in this script directory.
#
# Optional:
#   AFFILIATE_NOTION_URL, AFFILIATE_JASPER_URL, AFFILIATE_MURF_URL,
#   AFFILIATE_SYNTHESIA_URL, AFFILIATE_CUSTOMGPT_URL

import os
import json
import requests
import time
import re
import difflib
import html
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Comment
from groq import Groq
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
BLOG_ID = os.environ["BLOG_ID"]

SCOPES = ["https://www.googleapis.com/auth/blogger"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTED_FILE = os.path.join(BASE_DIR, "posted_titles.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")

MAX_POSTS_PER_RUN = 2
CANDIDATE_BUFFER_MULTIPLIER = 4

INTERNAL_LINKS_PER_POST = 2
SOURCE_MAX_CHARS = 12000
MIN_SOURCE_CHARS = 900

MIN_QUALITY_SCORE = 8
MIN_ENGAGEMENT_SCORE = 7
MIN_EDITORIAL_SCORE = 6.5

MAX_REWRITE_ATTEMPTS = 1
MAX_SOURCE_FACTS = 12
MAX_EVIDENCE_CHARS_PER_FACT = 300

MAX_ARTICLE_WORDS = 1100
MIN_ARTICLE_WORDS = 500

AFFILIATE_LINKS = {
    "notion": os.getenv("AFFILIATE_NOTION_URL", "").strip(),
    "jasper": os.getenv("AFFILIATE_JASPER_URL", "").strip(),
    "murf": os.getenv("AFFILIATE_MURF_URL", "").strip(),
    "synthesia": os.getenv("AFFILIATE_SYNTHESIA_URL", "").strip(),
    "customgpt": os.getenv("AFFILIATE_CUSTOMGPT_URL", "").strip(),
}

AI_TOOL_SOURCES = [
    (
        "https://www.producthunt.com/feed?category=artificial-intelligence",
        "Product Hunt AI",
    ),
    ("https://openai.com/news/rss.xml", "OpenAI"),
    ("https://blog.google/technology/ai/rss/", "Google AI Blog"),
    ("https://huggingface.co/blog/feed.xml", "Hugging Face"),
    (
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "TechCrunch AI",
    ),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
    )
}

client = Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------------------------
# BLOGGER
# ---------------------------------------------------------------------------

def get_blogger_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=8080, open_browser=True)

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("blogger", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# SOURCE COLLECTION
# ---------------------------------------------------------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_rss_items(url, source, limit=5):
    out = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)

        items = root.findall(".//item")

        if items:
            for item in items[:limit]:
                title = clean_text(item.findtext("title", ""))
                link = clean_text(item.findtext("link", ""))

                published = (
                    clean_text(item.findtext("pubDate", ""))
                    or clean_text(item.findtext("published", ""))
                    or clean_text(item.findtext("updated", ""))
                )

                if len(title) > 15 and link:
                    out.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": published,
                    })
        else:
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall(".//atom:entry", ns)[:limit]:
                title = clean_text(
                    entry.findtext("atom:title", "", ns)
                )

                published = (
                    clean_text(
                        entry.findtext("atom:published", "", ns)
                    )
                    or clean_text(
                        entry.findtext("atom:updated", "", ns)
                    )
                )

                link = ""
                for link_el in entry.findall("atom:link", ns):
                    href = clean_text(link_el.attrib.get("href", ""))
                    rel = link_el.attrib.get("rel", "alternate")

                    if href and rel == "alternate":
                        link = href
                        break

                if not link:
                    link_el = entry.find("atom:link", ns)
                    if link_el is not None:
                        link = clean_text(link_el.attrib.get("href", ""))

                if len(title) > 15 and link:
                    out.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": published,
                    })

        print(f"  Got {len(out)} from {source}")

    except Exception as e:
        print(f"  {source} RSS failed: {e}")

    return out


def fetch_source_article_text(url, max_chars=SOURCE_MAX_CHARS):
    if not url:
        return ""

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup([
            "script", "style", "nav", "footer", "header", "aside",
            "form", "noscript", "svg", "button", "input", "select",
            "textarea", "iframe", "object", "embed"
        ]):
            tag.decompose()

        candidates = [
            soup.find("article"),
            soup.find("main"),
            soup.find(attrs={"role": "main"}),
        ]

        container = next((x for x in candidates if x), soup.body)

        if not container:
            return ""

        text = clean_text(container.get_text(" ", strip=True))

        print(f"  Extracted {len(text)} source characters")
        return text[:max_chars]

    except Exception as e:
        print(f"  Could not fetch source body: {e}")
        return ""


def collect_topics():
    print("Collecting AI topics from configured sources...")

    topics = []

    for url, source in AI_TOOL_SOURCES:
        topics.extend(get_rss_items(url, source, limit=5))

    print(f"\nTotal raw topics: {len(topics)}")
    return topics


# ---------------------------------------------------------------------------
# DUPLICATE CONTROL
# ---------------------------------------------------------------------------

def normalize_title(title):
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^a-z0-9\s]", " ", (title or "").lower()),
    ).strip()


def title_similarity(a, b):
    return difflib.SequenceMatcher(
        None,
        normalize_title(a),
        normalize_title(b),
    ).ratio()


def is_obvious_duplicate(title, existing_titles, threshold=0.88):
    normalized = normalize_title(title)

    for old in existing_titles:
        if normalized and normalized == normalize_title(old):
            return True

        if title_similarity(title, old) >= threshold:
            return True

    return False


# ---------------------------------------------------------------------------
# AI HELPERS
# ---------------------------------------------------------------------------

def extract_json_object(text):
    if not text:
        raise ValueError("Empty AI response")

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.I,
    )

    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end <= start:
        raise ValueError("No JSON object found in AI response")

    return json.loads(cleaned[start:end + 1])


def call_ai(messages, max_tokens):
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=max_tokens,
        messages=messages,
    )

    choice = response.choices[0]
    content = choice.message.content or ""

    if choice.finish_reason == "length":
        print("  WARNING: AI response reached token limit")

    return content.strip()


# ---------------------------------------------------------------------------
# EDITORIAL INTELLIGENCE + EVIDENCE LEDGER
# ---------------------------------------------------------------------------

def analyze_story(topic_title, source_name, source_text, published=""):
    if len(source_text) < MIN_SOURCE_CHARS:
        return {
            "publish_decision": False,
            "story_summary": "",
            "important_facts": [],
            "evidence_ledger": [],
            "reader_problem_or_interest": "",
            "why_it_matters": "",
            "who_should_care": "",
            "missing_context": [
                "The source page did not provide enough extractable text."
            ],
            "unsupported_claims_to_avoid": [],
            "useful_angle": "",
            "article_type": "news_explainer",
            "search_intent": "",
            "primary_keyword": "",
            "secondary_keywords": [],
            "content_gap": "",
            "hook_strategy": "",
            "reader_questions": [],
            "engagement_strategy": "",
            "headline_options": [],
            "commercial_intent": "low",
            "evergreen_potential": 0,
            "topic_score": 0,
            "reason_if_rejected": "Insufficient source material.",
        }

    prompt = f"""
You are the editorial intelligence layer for AIToolNotes.

Your job is to decide whether this source contains a useful story and create
a factual, reader-focused editorial brief for a later writer.

Do NOT write the article.

SOURCE NAME:
{source_name}

RSS TITLE:
{topic_title}

PUBLISHED DATE:
{published or "unknown"}

SOURCE TEXT:
<BEGIN_SOURCE>
{source_text}
<END_SOURCE>

Return ONLY valid JSON with exactly these keys:

{{
  "publish_decision": true,
  "story_summary": "",
  "important_facts": [],
  "evidence_ledger": [
    {{
      "fact": "",
      "evidence": "",
      "confidence": "high"
    }}
  ],
  "reader_problem_or_interest": "",
  "why_it_matters": "",
  "who_should_care": "",
  "missing_context": [],
  "unsupported_claims_to_avoid": [],
  "useful_angle": "",
  "article_type": "news_explainer",
  "search_intent": "",
  "primary_keyword": "",
  "secondary_keywords": [],
  "content_gap": "",
  "hook_strategy": "",
  "reader_questions": [],
  "engagement_strategy": "",
  "headline_options": [],
  "commercial_intent": "low",
  "evergreen_potential": 0,
  "topic_score": 0,
  "reason_if_rejected": ""
}}

Allowed article_type:
news_explainer, practical_guide, tool_review, comparison, roundup, analysis

Allowed commercial_intent:
low, medium, high

Rules:

1. Every factual item must be directly supported by the supplied source.
2. Every evidence_ledger item must contain a concise excerpt from the source.
3. Do not invent evidence.
4. Do not turn the headline into a fact unless the body supports it.
5. Never invent product names, models, APIs, pricing, dates, statistics,
   benchmarks, hardware requirements, integrations, partnerships, quotes,
   user counts, availability, or technical capabilities.
6. Treat company promotional claims as claims by the company, not independent
   verification.
7. Do not use outside knowledge to fill missing information.
8. Reject thin, contradictory, inaccessible, navigation-heavy, or useless
   sources.
9. A useful story should answer what happened and why a reader should care.
10. search_intent should describe the likely user intent, such as:
    informational, navigational, commercial_investigation, transactional,
    or mixed.
11. primary_keyword must be a natural search phrase supported by the story.
12. secondary_keywords should be closely related phrases, not keyword spam.
13. content_gap should describe what a useful article can clarify beyond a
    basic source announcement, without inventing facts.
14. hook_strategy should describe how the first paragraph should earn attention.
15. reader_questions should contain 2-5 questions the article should answer
    when the source supports them.
16. engagement_strategy should describe useful ways to keep the reader engaged.
17. headline_options must contain 3-5 accurate, curiosity-driven headlines.
    Do not use clickbait, fake urgency, or unsupported claims.
18. Headlines should generally be under 70 characters when possible.
19. evergreen_potential is 0-10.
20. topic_score is 0-10 and should reflect reader value, novelty, search
    usefulness, commercial relevance, source strength, and content depth.
21. Do not publish simply because a company announced something.
22. Keep the evidence ledger to at most {MAX_SOURCE_FACTS} facts.
"""

    result = extract_json_object(call_ai([
        {
            "role": "system",
            "content": (
                "You are a strict evidence editor and digital publisher. "
                "Accuracy and reader value are more important than volume."
            ),
        },
        {"role": "user", "content": prompt},
    ], 5000))

    defaults = {
        "important_facts": [],
        "evidence_ledger": [],
        "missing_context": [],
        "unsupported_claims_to_avoid": [],
        "secondary_keywords": [],
        "reader_questions": [],
        "headline_options": [],
    }

    for key, default in defaults.items():
        result.setdefault(key, default)

    result["important_facts"] = result["important_facts"][:MAX_SOURCE_FACTS]
    result["evidence_ledger"] = result["evidence_ledger"][:MAX_SOURCE_FACTS]
    result["secondary_keywords"] = result["secondary_keywords"][:8]
    result["reader_questions"] = result["reader_questions"][:5]
    result["headline_options"] = result["headline_options"][:5]

    valid_ledger = []

    for item in result["evidence_ledger"]:
        if not isinstance(item, dict):
            continue

        fact = clean_text(item.get("fact"))
        evidence = clean_text(item.get("evidence"))
        confidence = clean_text(item.get("confidence")) or "medium"

        if fact and evidence:
            valid_ledger.append({
                "fact": fact[:500],
                "evidence": evidence[:MAX_EVIDENCE_CHARS_PER_FACT],
                "confidence": (
                    confidence
                    if confidence in {"high", "medium", "low"}
                    else "medium"
                ),
            })

    result["evidence_ledger"] = valid_ledger

    try:
        result["topic_score"] = float(result.get("topic_score", 0))
    except (TypeError, ValueError):
        result["topic_score"] = 0

    try:
        result["evergreen_potential"] = int(
            float(result.get("evergreen_potential", 0))
        )
    except (TypeError, ValueError):
        result["evergreen_potential"] = 0

    if len(result["evidence_ledger"]) < 2:
        result["publish_decision"] = False
        result["reason_if_rejected"] = (
            "The source did not yield enough traceable facts."
        )

    if result["topic_score"] < MIN_EDITORIAL_SCORE:
        result["publish_decision"] = False
        result["reason_if_rejected"] = (
            result.get("reason_if_rejected")
            or "Editorial value score is below the publishing threshold."
        )

    return result


# ---------------------------------------------------------------------------
# WRITER CONTEXT
# ---------------------------------------------------------------------------

def compact_writer_context(
    source_text,
    editorial_brief,
    max_source_chars=5500,
    max_facts=9,
):
    ledger = editorial_brief.get("evidence_ledger", [])

    compact_ledger = []

    for item in ledger[:max_facts]:
        if not isinstance(item, dict):
            continue

        fact = clean_text(item.get("fact"))
        evidence = clean_text(item.get("evidence"))
        confidence = clean_text(item.get("confidence")) or "medium"

        if fact and evidence:
            compact_ledger.append({
                "fact": fact[:350],
                "evidence": evidence[:300],
                "confidence": confidence[:20],
            })

    compact_brief = {
        "story_summary": editorial_brief.get("story_summary", ""),
        "reader_problem_or_interest": editorial_brief.get(
            "reader_problem_or_interest", ""
        ),
        "why_it_matters": editorial_brief.get("why_it_matters", ""),
        "who_should_care": editorial_brief.get("who_should_care", ""),
        "useful_angle": editorial_brief.get("useful_angle", ""),
        "article_type": editorial_brief.get(
            "article_type",
            "news_explainer",
        ),
        "search_intent": editorial_brief.get("search_intent", ""),
        "primary_keyword": editorial_brief.get("primary_keyword", ""),
        "secondary_keywords": editorial_brief.get(
            "secondary_keywords",
            [],
        )[:8],
        "content_gap": editorial_brief.get("content_gap", ""),
        "hook_strategy": editorial_brief.get("hook_strategy", ""),
        "reader_questions": editorial_brief.get(
            "reader_questions",
            [],
        )[:5],
        "engagement_strategy": editorial_brief.get(
            "engagement_strategy",
            "",
        ),
        "headline_options": editorial_brief.get(
            "headline_options",
            [],
        )[:5],
        "missing_context": editorial_brief.get(
            "missing_context",
            [],
        )[:4],
        "unsupported_claims_to_avoid": editorial_brief.get(
            "unsupported_claims_to_avoid",
            [],
        )[:6],
        "evidence_ledger": compact_ledger,
    }

    source_excerpt = clean_text(source_text or "")[:max_source_chars]

    return compact_brief, source_excerpt


# ---------------------------------------------------------------------------
# ARTICLE GENERATION
# ---------------------------------------------------------------------------

def generate_article(
    topic_title,
    source_name,
    source_url,
    source_text,
    editorial_brief,
    revision_feedback="",
):
    compact_brief, source_excerpt = compact_writer_context(
        source_text,
        editorial_brief,
    )

    feedback = ""

    if revision_feedback:
        feedback = f"""
Previous quality feedback. Fix these issues without introducing any new facts:

{revision_feedback[:2600]}
"""

    selected_headline = (
        editorial_brief.get("headline_options") or [topic_title]
    )[0]

    prompt = f"""
Write a genuinely useful AIToolNotes article using ONLY the supplied evidence.

The evidence ledger is the factual boundary.

ORIGINAL RSS TITLE:
{topic_title}

PREFERRED EDITORIAL HEADLINE:
{selected_headline}

SOURCE:
{source_name}

SOURCE URL:
{source_url}

EDITORIAL BRIEF:
{json.dumps(compact_brief, ensure_ascii=False, separators=(",", ":"))}

SOURCE EXCERPT:
<BEGIN_SOURCE>
{source_excerpt}
<END_SOURCE>

{feedback}

ARTICLE REQUIREMENTS:

1. Output RAW HTML ONLY. No Markdown, no code fences, no H1.
2. Use H2 and H3 headings where useful.
3. The first paragraph must immediately tell the reader what changed and
   why the story deserves attention.
4. Do NOT start with generic phrases such as:
   "In today's rapidly evolving AI landscape..."
   "Artificial intelligence is changing..."
   "As technology continues to advance..."
5. Do not merely rewrite the source chronologically.
6. Explain unfamiliar terms plainly.
7. Prioritize reader questions and practical understanding.
8. Use short paragraphs, bullets, numbered steps, or tables only when they
   genuinely improve comprehension.
9. Do not invent instructions for a product unless supported by the source.
10. Do not claim personal testing or personal experience.
11. Do not fabricate quotes.
12. Do not repeat the same fact unnecessarily.
13. Do not pad the article to reach a word count.
14. Aim for {MIN_ARTICLE_WORDS}-{MAX_ARTICLE_WORDS} words only when the
    evidence supports that length.
15. End with a concrete, useful takeaway rather than generic filler.
16. Naturally use the primary keyword and related terms where appropriate.
    Never keyword-stuff.
17. The article should answer the reader's likely search intent.
18. If the source contains promotional claims, attribute them appropriately.
19. Do not state that something is "the best", "revolutionary", "game-changing",
    "guaranteed", or similar unless the supplied evidence directly supports
    that wording and attribution is clear.
20. Do not include a fabricated FAQ section. Only answer questions that the
    source supports.
"""

    raw = call_ai([
        {
            "role": "system",
            "content": (
                "You are the senior writer of a trustworthy technology "
                "publication. Write clearly, specifically, and naturally. "
                "Stay strictly inside the supplied evidence boundary."
            ),
        },
        {"role": "user", "content": prompt},
    ], 5000)

    raw = re.sub(
        r"^```(?:html)?\s*",
        "",
        raw.strip(),
        flags=re.I,
    )
    raw = re.sub(r"\s*```$", "", raw)

    return raw.strip()


# ---------------------------------------------------------------------------
# DETERMINISTIC HTML VALIDATION
# ---------------------------------------------------------------------------

ALLOWED_TAGS = {
    "p", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em",
    "a", "table", "thead", "tbody", "tr", "th", "td", "blockquote",
    "br", "code", "pre"
}


def validate_and_clean_html(content):
    if not content:
        return "", ["Article is empty."]

    content = re.sub(
        r"^```(?:html)?\s*",
        "",
        content.strip(),
        flags=re.I,
    )
    content = re.sub(r"\s*```$", "", content)

    content = re.sub(
        r"<h1\b[^>]*>.*?</h1>",
        "",
        content,
        flags=re.I | re.S,
    )

    soup = BeautifulSoup(content, "html.parser")
    issues = []

    for tag in soup([
        "script", "style", "iframe", "object", "embed", "form"
    ]):
        tag.decompose()
        issues.append("Removed unsupported or unsafe HTML element.")

    for comment in soup.find_all(string=lambda x: isinstance(x, Comment)):
        comment.extract()

    for tag in list(soup.find_all(True)):
        name = tag.name.lower()

        if name not in ALLOWED_TAGS:
            tag.unwrap()
            issues.append(f"Removed unsupported HTML tag: {name}")

    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()

        if not re.match(r"^https?://", href, flags=re.I):
            a.unwrap()
            issues.append("Removed an invalid link.")
            continue

        a["rel"] = list(
            dict.fromkeys(
                (a.get("rel") or []) + ["noopener"]
            )
        )

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        if len(rows) < 1:
            table.decompose()
            issues.append("Removed an empty table.")
            continue

        max_cells = max(
            (
                len(row.find_all(["th", "td"]))
                for row in rows
            ),
            default=0,
        )

        if max_cells < 2:
            table.decompose()
            issues.append("Removed a malformed table.")

    text = clean_text(soup.get_text(" ", strip=True))

    if len(text) < 500:
        issues.append("Article is too short to be useful.")

    if not soup.find(["p", "ul", "ol", "table", "blockquote"]):
        issues.append("Article has no recognizable content structure.")

    if not soup.find("h2"):
        issues.append("Article has no H2 heading.")

    return str(soup).strip(), issues


def count_words_from_html(content):
    soup = BeautifulSoup(content or "", "html.parser")
    return len(clean_text(soup.get_text(" ", strip=True)).split())


# ---------------------------------------------------------------------------
# FINAL FACT + QUALITY + ENGAGEMENT CHECK
# ---------------------------------------------------------------------------

def quality_check(
    topic_title,
    source_name,
    source_url,
    source_text,
    editorial_brief,
    article_html,
    html_issues,
):
    compact_brief, source_excerpt = compact_writer_context(
        source_text,
        editorial_brief,
        max_source_chars=4200,
        max_facts=9,
    )

    article_excerpt = (article_html or "")[:15000]
    word_count = count_words_from_html(article_html)

    prompt = f"""
You are the final evidence, quality, SEO, and engagement editor for AIToolNotes.

Check whether the article is accurate, useful, readable, and worth publishing.

TOPIC:
{topic_title}

SOURCE:
{source_name}

SOURCE URL:
{source_url}

WORD COUNT:
{word_count}

EDITORIAL BRIEF:
{json.dumps(compact_brief, ensure_ascii=False, separators=(",", ":"))}

SOURCE EXCERPT:
<BEGIN_SOURCE>
{source_excerpt}
<END_SOURCE>

DETERMINISTIC HTML ISSUES:
{json.dumps(html_issues, ensure_ascii=False)}

ARTICLE:
<BEGIN_ARTICLE>
{article_excerpt}
<END_ARTICLE>

Return ONLY valid JSON:

{{
  "publish": false,
  "score": 0,
  "accuracy_score": 0,
  "usefulness_score": 0,
  "engagement_score": 0,
  "readability_score": 0,
  "search_quality_score": 0,
  "originality_score": 0,
  "issues": [],
  "unsupported_claims": [],
  "missing_value": [],
  "style_issues": [],
  "engagement_issues": [],
  "seo_issues": [],
  "revision_instructions": ""
}}

Scoring:
- accuracy: factual support and attribution
- usefulness: answers the reader's actual need
- engagement: strong opening, specificity, information flow, curiosity,
  concrete takeaways, and absence of filler
- readability: structure, paragraph length, clarity, and natural prose
- search quality: satisfies likely search intent without keyword stuffing
- originality: adds useful organization/interpretation rather than merely
  repeating the source

Rules:

1. Every concrete factual claim must be supported by the supplied evidence.
2. Numbers, names, APIs, prices, dates, specs, availability, quotes,
   partnerships, performance claims, and technical capabilities require direct
   support.
3. Flag invented facts, fake experience, fabricated quotes, misleading
   certainty, unsupported instructions, repetition, and generic filler.
4. Flag generic AI openings and conclusions.
5. Respect deterministic HTML issues.
6. The article should not be rejected merely because it is concise if it is
   genuinely useful.
7. If the article is below 500 words, normally flag missing value unless the
   evidence is genuinely limited.
8. Do not demand facts that are absent from the source.
9. A strong article should have a reason to continue reading beyond the first
   paragraph.
10. Publish only when:
    - score >= {MIN_QUALITY_SCORE}
    - engagement_score >= {MIN_ENGAGEMENT_SCORE}
    - there are no material unsupported claims
    - there are no unresolved deterministic HTML issues
"""

    result = extract_json_object(call_ai([
        {
            "role": "system",
            "content": (
                "You are a strict publication gate. Accuracy comes first, "
                "but the publication must also provide genuine reader value."
            ),
        },
        {"role": "user", "content": prompt},
    ], 3000))

    return result


# ---------------------------------------------------------------------------
# REVISION
# ---------------------------------------------------------------------------

def revise_article(
    topic_title,
    source_name,
    source_url,
    source_text,
    editorial_brief,
    article_html,
    quality_result,
):
    feedback = json.dumps({
        "issues": quality_result.get("issues", []),
        "unsupported_claims": quality_result.get(
            "unsupported_claims", []
        ),
        "missing_value": quality_result.get(
            "missing_value", []
        ),
        "style_issues": quality_result.get(
            "style_issues", []
        ),
        "engagement_issues": quality_result.get(
            "engagement_issues", []
        ),
        "seo_issues": quality_result.get(
            "seo_issues", []
        ),
        "revision_instructions": quality_result.get(
            "revision_instructions", ""
        ),
    }, ensure_ascii=False, indent=2)

    # The previous article is intentionally supplied through the revision
    # instructions only indirectly. The writer regenerates from the same
    # evidence boundary, reducing the chance of preserving bad claims.
    return generate_article(
        topic_title,
        source_name,
        source_url,
        source_text,
        editorial_brief,
        revision_feedback=feedback,
    )


# ---------------------------------------------------------------------------
# LINK / MONETIZATION HELPERS
# ---------------------------------------------------------------------------

def article_text(content):
    soup = BeautifulSoup(content or "", "html.parser")
    return clean_text(soup.get_text(" ", strip=True))


def inject_contextual_affiliate_links(content, editorial_brief):
    """
    Add at most one affiliate link per configured tool and only when the
    article actually discusses that tool. Existing anchors are not replaced.
    """
    if not content:
        return content

    soup = BeautifulSoup(content, "html.parser")
    article_plain = article_text(content).lower()

    for tool, url in AFFILIATE_LINKS.items():
        if not url or tool.lower() not in article_plain:
            continue

        # Avoid linking if this tool is already linked.
        already_linked = any(
            tool.lower() in clean_text(a.get_text(" ", strip=True)).lower()
            for a in soup.find_all("a")
        )

        if already_linked:
            continue

        pattern = re.compile(
            r"\b(" + re.escape(tool) + r")\b",
            re.I,
        )

        for text_node in list(soup.find_all(string=pattern)):
            if text_node.parent.name == "a":
                continue

            match = pattern.search(str(text_node))
            if not match:
                continue

            before = str(text_node)[:match.start()]
            matched = match.group(1)
            after = str(text_node)[match.end():]

            anchor = soup.new_tag(
                "a",
                href=url,
                rel=["nofollow", "sponsored", "noopener"],
            )
            anchor.string = matched

            text_node.replace_with(
                BeautifulSoup(
                    before,
                    "html.parser",
                )
            )
            text_node.parent.insert_after(
                anchor
            )

            if after:
                anchor.insert_after(
                    BeautifulSoup(after, "html.parser")
                )

            break

    return str(soup)


def keyword_tokens(text):
    words = re.findall(r"[a-z0-9]{3,}", (text or "").lower())

    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into",
        "about", "what", "when", "where", "which", "will", "could",
        "have", "has", "how", "new", "your", "you", "are", "its",
        "their", "they", "than", "more", "after", "before", "using",
        "tool", "tools", "ai", "artificial", "intelligence",
    }

    return {w for w in words if w not in stopwords}


def internal_link_relevance(new_article, candidate):
    new_tokens = keyword_tokens(
        new_article.get("primary_keyword", "")
        + " "
        + " ".join(new_article.get("secondary_keywords", []))
        + " "
        + " ".join(new_article.get("topics", []))
    )

    old_tokens = keyword_tokens(
        candidate.get("title", "")
        + " "
        + candidate.get("primary_keyword", "")
        + " "
        + " ".join(candidate.get("secondary_keywords", []))
        + " "
        + " ".join(candidate.get("topics", []))
    )

    if not new_tokens or not old_tokens:
        return 0.0

    overlap = len(new_tokens & old_tokens)
    union = len(new_tokens | old_tokens)

    return overlap / union if union else 0.0


def inject_internal_links(
    content,
    posted_history,
    current_link,
    editorial_brief,
):
    candidates = []

    for p in posted_history:
        if not isinstance(p, dict):
            continue

        if not p.get("post_url"):
            continue

        if p.get("link") == current_link:
            continue

        if not p.get("title"):
            continue

        candidates.append(p)

    if not candidates:
        return content

    scored = []

    for candidate in candidates:
        score = internal_link_relevance(
            editorial_brief,
            candidate,
        )
        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)

    picks = [
        candidate
        for score, candidate in scored[:INTERNAL_LINKS_PER_POST]
        if score > 0
    ]

    if not picks:
        return content

    links_html = "".join(
        f'<li><a href="{html.escape(p["post_url"], quote=True)}">'
        f'{html.escape(p["title"])}'
        f'</a></li>'
        for p in picks
    )

    return (
        content
        + f"<h2>Related reading</h2><ul>{links_html}</ul>"
    )


def append_source_attribution(content, source_name, source_url):
    if not source_url:
        return content

    escaped_name = html.escape(source_name or "the original source")
    escaped_url = html.escape(source_url, quote=True)

    attribution = (
        '<h2>Source</h2>'
        '<p>'
        'This article is based on information published by '
        f'<a href="{escaped_url}" '
        'rel="nofollow noopener">'
        f'{escaped_name}'
        '</a>.'
        '</p>'
    )

    return content + attribution


# ---------------------------------------------------------------------------
# BLOGGER PUBLISH
# ---------------------------------------------------------------------------

def post_to_blogger(service, title, content):
    result = (
        service.posts()
        .insert(
            blogId=BLOG_ID,
            body={
                "kind": "blogger#post",
                "title": title,
                "content": content,
            },
            isDraft=False,
        )
        .execute()
    )

    url = result.get("url", "")
    print(f"  Posted to Blogger: {url}")

    return result, url


# ---------------------------------------------------------------------------
# HISTORY
# ---------------------------------------------------------------------------

def load_posted_history():
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, list) else []

    except Exception:
        return []


def save_posted_history(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(
            posted[-500:],
            f,
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------------------------
# HEADLINE SELECTION
# ---------------------------------------------------------------------------

def choose_headline(brief, fallback):
    options = brief.get("headline_options", [])

    cleaned = []

    for option in options:
        option = clean_text(option)

        if not option:
            continue

        if option.lower() in {
            x.lower() for x in cleaned
        }:
            continue

        if len(option) > 100:
            continue

        cleaned.append(option)

    if cleaned:
        return cleaned[0]

    return clean_text(fallback)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("AIToolNotes Intelligent Blog Automation v4 Starting...")
    print(
        "Mode: source -> editorial intelligence -> evidence -> "
        "headline/SEO -> write -> HTML -> quality/engagement -> "
        "revision -> links -> Blogger"
    )

    posted = load_posted_history()

    posted_titles = {
        p.get("title")
        for p in posted
        if isinstance(p, dict) and p.get("title")
    }

    posted_links = {
        p.get("link")
        for p in posted
        if isinstance(p, dict) and p.get("link")
    }

    posted_titles.update(
        p for p in posted
        if isinstance(p, str)
    )

    service = get_blogger_service()

    all_topics = collect_topics()

    seen_titles = set()
    candidate_pool = []

    candidate_buffer_limit = max(
        MAX_POSTS_PER_RUN * CANDIDATE_BUFFER_MULTIPLIER,
        8,
    )

    for topic in all_topics:
        title = clean_text(topic.get("title", ""))
        link = clean_text(topic.get("link", ""))

        if len(title) <= 15:
            continue

        if title in seen_titles:
            continue

        if link and link in posted_links:
            continue

        if is_obvious_duplicate(title, posted_titles):
            continue

        seen_titles.add(title)
        candidate_pool.append(topic)

        if len(candidate_pool) >= candidate_buffer_limit:
            break

    print(
        f"\nCandidate pool: {len(candidate_pool)} "
        f"(buffer: {candidate_buffer_limit})"
    )

    # -----------------------------------------------------------------------
    # SOURCE VALIDATION + EDITORIAL SCORING
    # -----------------------------------------------------------------------

    analyzed_candidates = []

    for topic_data in candidate_pool:
        title = topic_data["title"]
        link = topic_data.get("link", "")

        print(f"\nEvaluating source: {title[:100]}")

        source_text = fetch_source_article_text(link)

        if len(source_text) < MIN_SOURCE_CHARS:
            print(
                f"  SKIP: source text too short "
                f"({len(source_text)} chars)."
            )
            continue

        try:
            brief = analyze_story(
                title,
                topic_data["source"],
                source_text,
                topic_data.get("published", ""),
            )
        except Exception as e:
            print(f"  SKIP: editorial analysis failed: {e}")
            continue

        score = float(brief.get("topic_score", 0) or 0)

        print(
            f"  Editorial score: {score:.1f}/10 | "
            f"Decision: "
            f"{'PUBLISHABLE' if brief.get('publish_decision') else 'SKIP'}"
        )

        print(
            f"  Type: {brief.get('article_type', 'unknown')} | "
            f"Intent: {brief.get('search_intent', 'unknown')}"
        )

        print(
            f"  Commercial: {brief.get('commercial_intent', 'unknown')} | "
            f"Evidence: {len(brief.get('evidence_ledger', []))}"
        )

        if not brief.get("publish_decision"):
            print(
                "  Skipped: "
                f"{brief.get('reason_if_rejected', 'editorial gate')}"
            )
            continue

        analyzed_candidates.append(
            (score, topic_data, source_text, brief)
        )

    # Highest editorial-value candidates first.
    analyzed_candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    usable_topics = analyzed_candidates[:MAX_POSTS_PER_RUN]

    print(
        f"\nSelected {len(usable_topics)} article(s) "
        f"from {len(analyzed_candidates)} publishable candidate(s)."
    )

    published_this_run = 0

    # -----------------------------------------------------------------------
    # WRITE -> CHECK -> REVISE -> PUBLISH
    # -----------------------------------------------------------------------

    for i, (topic_score, topic_data, source_text, brief) in enumerate(
        usable_topics,
        1,
    ):
        original_title = topic_data["title"]
        source = topic_data["source"]
        source_url = topic_data.get("link", "")
        published = topic_data.get("published", "")

        print(
            f"\nArticle {i}/{len(usable_topics)}: "
            f"{original_title[:100]}"
        )

        try:
            headline = choose_headline(
                brief,
                original_title,
            )

            print(f"  Headline: {headline}")
            print("  Writing evidence-constrained article...")

            article = generate_article(
                headline,
                source,
                source_url,
                source_text,
                brief,
            )

            article, html_issues = validate_and_clean_html(article)

            print(
                f"  Word count: {count_words_from_html(article)}"
            )

            print(
                f"  HTML check: "
                f"{'PASS' if not html_issues else 'ISSUES FOUND'}"
            )

            quality = quality_check(
                headline,
                source,
                source_url,
                source_text,
                brief,
                article,
                html_issues,
            )

            score = int(float(quality.get("score", 0) or 0))
            engagement_score = int(
                float(
                    quality.get(
                        "engagement_score",
                        0,
                    ) or 0
                )
            )

            publish = bool(quality.get("publish"))

            print(
                f"  Quality: {score}/10 | "
                f"Engagement: {engagement_score}/10 | "
                f"Publish: {publish}"
            )

            # ---------------------------------------------------------------
            # ONE REVISION
            # ---------------------------------------------------------------

            if (
                not publish
                or score < MIN_QUALITY_SCORE
                or engagement_score < MIN_ENGAGEMENT_SCORE
                or html_issues
            ):
                if MAX_REWRITE_ATTEMPTS:
                    print("  Revising article once...")

                    article = revise_article(
                        headline,
                        source,
                        source_url,
                        source_text,
                        brief,
                        article,
                        quality,
                    )

                    article, html_issues = validate_and_clean_html(
                        article
                    )

                    quality = quality_check(
                        headline,
                        source,
                        source_url,
                        source_text,
                        brief,
                        article,
                        html_issues,
                    )

                    score = int(
                        float(
                            quality.get("score", 0) or 0
                        )
                    )

                    engagement_score = int(
                        float(
                            quality.get(
                                "engagement_score",
                                0,
                            ) or 0
                        )
                    )

                    publish = bool(
                        quality.get("publish")
                    )

                    print(
                        f"  Revised: {score}/10 | "
                        f"Engagement: {engagement_score}/10 | "
                        f"Publish: {publish}"
                    )

            if (
                not publish
                or score < MIN_QUALITY_SCORE
                or engagement_score < MIN_ENGAGEMENT_SCORE
                or html_issues
            ):
                print(
                    "  NOT PUBLISHED. "
                    "Article failed the evidence/quality gate."
                )

                if quality.get("unsupported_claims"):
                    print(
                        "  Unsupported claims: "
                        f"{len(quality['unsupported_claims'])}"
                    )

                continue

            # ---------------------------------------------------------------
            # POST-VALIDATION ENRICHMENT
            # ---------------------------------------------------------------

            article = inject_contextual_affiliate_links(
                article,
                brief,
            )

            article = inject_internal_links(
                article,
                posted,
                source_url,
                brief,
            )

            article = append_source_attribution(
                article,
                source,
                source_url,
            )

            article, final_html_issues = validate_and_clean_html(
                article
            )

            if final_html_issues:
                print(
                    "  NOT PUBLISHED. Final HTML validation failed: "
                    f"{final_html_issues}"
                )
                continue

            # ---------------------------------------------------------------
            # PUBLISH
            # ---------------------------------------------------------------

            _, post_url = post_to_blogger(
                service,
                headline,
                article,
            )

            now = datetime.now(timezone.utc).isoformat()

            posted.append({
                "title": headline,
                "original_title": original_title,
                "link": source_url,
                "post_url": post_url,
                "source": source,
                "published": published,
                "published_at": now,
                "quality_score": score,
                "engagement_score": engagement_score,
                "editorial_score": topic_score,
                "article_type": brief.get(
                    "article_type",
                    "",
                ),
                "search_intent": brief.get(
                    "search_intent",
                    "",
                ),
                "primary_keyword": brief.get(
                    "primary_keyword",
                    "",
                ),
                "secondary_keywords": brief.get(
                    "secondary_keywords",
                    [],
                ),
                "commercial_intent": brief.get(
                    "commercial_intent",
                    "",
                ),
                "evergreen_potential": brief.get(
                    "evergreen_potential",
                    0,
                ),
                "evidence_facts": len(
                    brief.get(
                        "evidence_ledger",
                        [],
                    )
                ),
            })

            posted = posted[-500:]
            save_posted_history(posted)

            posted_titles.add(headline)
            posted_links.add(source_url)

            published_this_run += 1

            time.sleep(3)

        except Exception as e:
            print(
                f"  Failed: {type(e).__name__}: {e}"
            )
            continue

    print(
        f"\nDone. Published {published_this_run} article(s)."
    )


if __name__ == "__main__":
    main()
