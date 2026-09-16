# AIToolNotes Intelligent Blog Automation v3.2
# RSS -> extraction -> editorial intelligence -> evidence ledger -> writer
# -> deterministic HTML checks -> fact/quality check -> one revision -> Blogger

import os
import json
import requests
import time
import re
import difflib
import html
import xml.etree.ElementTree as ET

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

SCOPES = [
    "https://www.googleapis.com/auth/blogger"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

POSTED_FILE = os.path.join(BASE_DIR, "posted_titles.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")

MAX_POSTS_PER_RUN = 2
INTERNAL_LINKS_PER_POST = 2

SOURCE_MAX_CHARS = 10000
MIN_SOURCE_CHARS = 900

MIN_QUALITY_SCORE = 8
MAX_REWRITE_ATTEMPTS = 1

MAX_SOURCE_FACTS = 12
MAX_EVIDENCE_CHARS_PER_FACT = 300

AFFILIATE_LINKS = {
    "notion": "",
    "jasper": "",
    "murf": "",
    "synthesia": "",
    "customgpt": "",
}

AI_TOOL_SOURCES = [
    (
        "https://www.producthunt.com/feed?category=artificial-intelligence",
        "Product Hunt AI",
    ),
    (
        "https://openai.com/news/rss.xml",
        "OpenAI",
    ),
    (
        "https://blog.google/technology/ai/rss/",
        "Google AI Blog",
    ),
    (
        "https://huggingface.co/blog/feed.xml",
        "Hugging Face",
    ),
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
# HIGH-RISK CLAIM LANGUAGE
# ---------------------------------------------------------------------------

HIGH_RISK_CLAIM_PATTERNS = [
    r"\bguarantee(?:s|d)?\b",
    r"\bguaranteed\b",
    r"\bprove(?:s|d)?\b",
    r"\bproves?\b",
    r"\balways\b",
    r"\bnever\b",
    r"\bensure(?:s|d)?\b",
    r"\beliminate(?:s|d)?\b",
    r"\bsolves?\b",
    r"\bwill increase\b",
    r"\bwill decrease\b",
    r"\bwill improve\b",
    r"\bwill reduce\b",
    r"\bcan meet\b",
    r"\brevolutionize\b",
]


# ---------------------------------------------------------------------------
# BLOGGER
# ---------------------------------------------------------------------------

def get_blogger_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_FILE,
                SCOPES
            )

            creds = flow.run_local_server(
                port=8080,
                open_browser=True
            )

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build(
        "blogger",
        "v3",
        credentials=creds
    )


# ---------------------------------------------------------------------------
# SOURCE COLLECTION
# ---------------------------------------------------------------------------

def get_rss_items(url, source, limit=3):
    out = []

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        r.raise_for_status()

        root = ET.fromstring(r.content)

        # Standard RSS
        items = root.findall(".//item")

        # Atom fallback
        if not items:

            ns = {
                "atom": "http://www.w3.org/2005/Atom"
            }

            for entry in root.findall(".//atom:entry", ns)[:limit]:

                title = entry.findtext(
                    "atom:title",
                    "",
                    ns
                ).strip()

                published = (
                    entry.findtext(
                        "atom:published",
                        "",
                        ns
                    ).strip()
                    or
                    entry.findtext(
                        "atom:updated",
                        "",
                        ns
                    ).strip()
                )

                link = ""

                link_el = entry.find(
                    "atom:link",
                    ns
                )

                if link_el is not None:
                    link = (
                        link_el.attrib.get("href")
                        or ""
                    ).strip()

                if len(title) > 15 and link:

                    out.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": published,
                    })

        else:

            for item in items[:limit]:

                title = item.findtext(
                    "title",
                    ""
                ).strip()

                link = item.findtext(
                    "link",
                    ""
                ).strip()

                published = (
                    item.findtext(
                        "pubDate",
                        ""
                    ).strip()
                    or
                    item.findtext(
                        "published",
                        ""
                    ).strip()
                )

                if len(title) > 15 and link:

                    out.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": published,
                    })

        print(
            f"  Got {len(out)} from {source}"
        )

    except Exception as e:

        print(
            f"  {source} RSS failed: {e}"
        )

    return out


def clean_text(text):
    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


def fetch_source_article_text(
    url,
    max_chars=SOURCE_MAX_CHARS
):

    if not url:
        return ""

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        r.raise_for_status()

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        # Remove non-content elements
        for tag in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
            "noscript",
            "svg",
            "button",
            "input",
            "select",
            "textarea",
        ]):

            tag.decompose()

        # Prefer article-like containers
        candidates = [
            soup.find("article"),
            soup.find("main"),
            soup.find(
                attrs={"role": "main"}
            ),
        ]

        container = next(
            (
                x
                for x in candidates
                if x
            ),
            soup.body
        )

        if not container:
            return ""

        text = clean_text(
            container.get_text(
                " ",
                strip=True
            )
        )

        print(
            f"  Extracted {len(text)} source characters"
        )

        return text[:max_chars]

    except Exception as e:

        print(
            f"  Could not fetch source body: {e}"
        )

        return ""


def collect_topics():

    print(
        "Collecting AI tool topics from configured sources..."
    )

    topics = []

    for url, source in AI_TOOL_SOURCES:

        topics += get_rss_items(
            url,
            source,
            limit=3
        )

    print(
        f"\nTotal raw topics: {len(topics)}"
    )

    return topics


# ---------------------------------------------------------------------------
# DUPLICATE CONTROL
# ---------------------------------------------------------------------------

def normalize_title(title):

    return re.sub(
        r"\s+",
        " ",
        re.sub(
            r"[^a-z0-9\s]",
            " ",
            (title or "").lower()
        )
    ).strip()


def title_similarity(a, b):

    return difflib.SequenceMatcher(
        None,
        normalize_title(a),
        normalize_title(b)
    ).ratio()


def is_obvious_duplicate(
    title,
    existing_titles,
    threshold=0.88
):

    normalized = normalize_title(title)

    for old in existing_titles:

        if (
            normalized
            and normalized == normalize_title(old)
        ):
            return True

        if title_similarity(
            title,
            old
        ) >= threshold:

            return True

    return False


# ---------------------------------------------------------------------------
# AI HELPERS
# ---------------------------------------------------------------------------

def extract_json_object(text):

    if not text:
        raise ValueError(
            "Empty AI response"
        )

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.I
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end <= start:

        raise ValueError(
            "No JSON object found in AI response"
        )

    return json.loads(
        cleaned[start:end + 1]
    )


def call_ai(messages, max_tokens):

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=max_tokens,
        messages=messages,
    )

    content = (
        response.choices[0].message.content
        or ""
    )

    if (
        response.choices[0].finish_reason
        == "length"
    ):

        print(
            "  WARNING: AI response reached token limit"
        )

    return content.strip()


# ---------------------------------------------------------------------------
# EDITORIAL INTELLIGENCE + EVIDENCE LEDGER
# ---------------------------------------------------------------------------

def analyze_story(
    topic_title,
    source_name,
    source_text,
    published=""
):

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
            "unsupported_claims_to_avoid": [
                "Do not infer product details from the headline alone."
            ],
            "useful_angle": "",
            "article_type": "news_explainer",
            "search_intent": "",
            "commercial_intent": "low",
            "reason_if_rejected": (
                "Insufficient source material."
            ),
        }

    prompt = f"""
You are the evidence-first editorial intelligence layer for AIToolNotes.

Your job is NOT to write the article.

Your job is to understand the supplied source and build a strict evidence
boundary for a later writer.

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
  "commercial_intent": "low",
  "reason_if_rejected": ""
}}

Rules:

1. Every factual item in important_facts must be directly supported by the
   supplied source text.

2. Every item in evidence_ledger must contain a concise evidence excerpt from
   the supplied source that supports the fact.

3. Do not invent evidence.

4. Keep evidence excerpts short and close to the source wording.

5. Never turn a source headline into a fact unless the body supports it.

6. Never invent product names, model names, APIs, pricing, dates, statistics,
   performance numbers, hardware requirements, integrations, user counts,
   partnerships, availability, quotes, or technical capabilities.

7. Treat company promotional claims as claims by the company, not independent
   verification.

8. If the source is thin, contradictory, inaccessible, mostly navigation,
   promotional boilerplate, or insufficient for a useful article, set
   publish_decision to false.

9. A publishable story should contain enough supported information to explain
   what happened and why a reader should care.

10. missing_context means information genuinely absent from the supplied source.

11. unsupported_claims_to_avoid should contain likely temptations for the writer
    that the source does NOT establish.

12. article_type must be one of:
    news_explainer, practical_guide, tool_review, comparison, roundup, analysis.

13. commercial_intent must be low, medium, or high.

14. Do not use outside knowledge to fill gaps.

15. Keep the evidence ledger to at most {MAX_SOURCE_FACTS} important facts.

16. Do not convert experimental or benchmark results into guarantees about
    real-world performance.

17. Preserve the scope of the evidence. If a result applies only to a specific
    model, benchmark, geography, experiment, timeframe, or test group, record
    that limitation.

18. Distinguish direct source facts from reasonable implications.
"""

    result = extract_json_object(
        call_ai(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a strict evidence editor. "
                        "Source-grounded accuracy is more important "
                        "than publishing volume."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            4500
        )
    )

    result.setdefault(
        "important_facts",
        []
    )

    result.setdefault(
        "evidence_ledger",
        []
    )

    result.setdefault(
        "missing_context",
        []
    )

    result.setdefault(
        "unsupported_claims_to_avoid",
        []
    )

    result["important_facts"] = (
        result["important_facts"]
        [:MAX_SOURCE_FACTS]
    )

    result["evidence_ledger"] = (
        result["evidence_ledger"]
        [:MAX_SOURCE_FACTS]
    )

    valid_ledger = []

    for item in result["evidence_ledger"]:

        if not isinstance(item, dict):
            continue

        fact = clean_text(
            item.get("fact")
        )

        evidence = clean_text(
            item.get("evidence")
        )

        confidence = clean_text(
            item.get("confidence")
        ) or "medium"

        if fact and evidence:

            valid_ledger.append({
                "fact": fact,
                "evidence": evidence[
                    :MAX_EVIDENCE_CHARS_PER_FACT
                ],
                "confidence": confidence,
            })

    result["evidence_ledger"] = valid_ledger

    if len(result["evidence_ledger"]) < 2:

        result["publish_decision"] = False

        result["reason_if_rejected"] = (
            "The source did not yield enough independently "
            "traceable facts."
        )

    return result


# ---------------------------------------------------------------------------
# ARTICLE GENERATION
# ---------------------------------------------------------------------------

def compact_writer_context(
    source_text,
    editorial_brief,
    max_source_chars=4500,
    max_facts=9
):

    ledger = editorial_brief.get(
        "evidence_ledger",
        []
    )

    compact_ledger = []

    for item in ledger[:max_facts]:

        if not isinstance(item, dict):
            continue

        fact = clean_text(
            item.get("fact")
        )

        evidence = clean_text(
            item.get("evidence")
        )

        confidence = clean_text(
            item.get("confidence")
        ) or "medium"

        if fact and evidence:

            compact_ledger.append({
                "fact": fact[:350],
                "evidence": evidence[:300],
                "confidence": confidence[:20],
            })

    compact_brief = {

        "story_summary": editorial_brief.get(
            "story_summary",
            ""
        ),

        "reader_problem_or_interest":
            editorial_brief.get(
                "reader_problem_or_interest",
                ""
            ),

        "why_it_matters":
            editorial_brief.get(
                "why_it_matters",
                ""
            ),

        "who_should_care":
            editorial_brief.get(
                "who_should_care",
                ""
            ),

        "useful_angle":
            editorial_brief.get(
                "useful_angle",
                ""
            ),

        "article_type":
            editorial_brief.get(
                "article_type",
                "news_explainer"
            ),

        "search_intent":
            editorial_brief.get(
                "search_intent",
                ""
            ),

        "missing_context":
            editorial_brief.get(
                "missing_context",
                []
            )[:4],

        "unsupported_claims_to_avoid":
            editorial_brief.get(
                "unsupported_claims_to_avoid",
                []
            )[:6],

        "evidence_ledger":
            compact_ledger,
    }

    source_excerpt = clean_text(
        source_text or ""
    )[:max_source_chars]

    return (
        compact_brief,
        source_excerpt
    )


def generate_article(
    topic_title,
    source_name,
    source_text,
    editorial_brief,
    revision_feedback=""
):

    compact_brief, source_excerpt = (
        compact_writer_context(
            source_text,
            editorial_brief
        )
    )

    feedback = ""

    if revision_feedback:

        feedback = f"""
Previous quality feedback.

Fix these issues without introducing new facts:

{revision_feedback[:2200]}
"""

    prompt = f"""
Write a genuinely useful AIToolNotes article using ONLY the supplied evidence.

The evidence ledger defines the factual boundary.

Do not use outside knowledge.

TITLE:
{topic_title}

SOURCE:
{source_name}

EDITORIAL BRIEF:

{json.dumps(
    compact_brief,
    ensure_ascii=False,
    separators=(",", ":")
)}

SOURCE EXCERPT:

<BEGIN_SOURCE>

{source_excerpt}

<END_SOURCE>

{feedback}

Rules:

- Never invent or guess product names, models, APIs, prices, dates, statistics,
  benchmarks, integrations, hardware requirements, partnerships, quotes, users,
  availability, or technical capabilities.

- Treat promotional statements as claims by the source/company, not independent
  verification.

- If a detail is not supported, do not add it.

- Explain unfamiliar terms plainly and focus on what changed and why it matters.

- Distinguish clearly between:

  FACT:
  Directly supported by the evidence.

  ATTRIBUTED CLAIM:
  Something explicitly stated by the company, researchers, or source.

  INFERENCE:
  A reasonable interpretation that is clearly framed as a possibility.

- Do not turn benchmark results into guarantees about real-world or production
  performance.

- Do not generalize a result from one model, benchmark, geography, experiment,
  population, or timeframe to all models, businesses, users, or production
  environments.

- Do not claim that a product increases revenue, conversions, ROI,
  reliability, productivity, or compliance unless the supplied evidence
  directly establishes that outcome.

- Do not use "guarantees", "proves", "ensures", "eliminates", "solves", or
  other absolute language unless the source explicitly supports that level
  of certainty.

- When discussing possible implications, use appropriately cautious wording
  such as "could", "may", "suggests", "the results indicate", or
  "in the tested setup".

- Do not state a specific number of major features or changes unless the
  source itself clearly groups them into that exact number.

- Avoid generic AI filler and fake personal experience.

- Use H2 headings.

- Use numbered steps only when the evidence supports them.

- Aim for 700-950 words when the evidence supports it.

- Do not pad the article.

- End with a concrete takeaway.

- Output RAW HTML ONLY.

- No Markdown.

- No code fences.

- No H1.
"""

    raw = call_ai(
        [
            {
                "role": "system",
                "content": (
                    "You are the senior writer of a trustworthy "
                    "technology publication. Stay strictly inside "
                    "the supplied evidence boundary."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        4000
    )

    raw = re.sub(
        r"^```(?:html)?\s*",
        "",
        raw.strip(),
        flags=re.I
    )

    raw = re.sub(
        r"\s*```$",
        "",
        raw
    )

    return raw.strip()


# ---------------------------------------------------------------------------
# DETERMINISTIC HTML VALIDATION + CLEANUP
# ---------------------------------------------------------------------------

ALLOWED_TAGS = {
    "p",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "blockquote",
    "br",
    "code",
    "pre",
}


def validate_and_clean_html(content):

    if not content:
        return "", ["Article is empty."]

    # Remove Markdown fences.
    content = re.sub(
        r"^```(?:html)?\s*",
        "",
        content.strip(),
        flags=re.I
    )

    content = re.sub(
        r"\s*```$",
        "",
        content
    )

    # Remove complete SVG blocks.
    content = re.sub(
        r"<svg\b[^>]*>.*?</svg>",
        "",
        content,
        flags=re.I | re.S
    )

    # Remove accidental H1.
    content = re.sub(
        r"<h1\b[^>]*>.*?</h1>",
        "",
        content,
        flags=re.I | re.S
    )

    soup = BeautifulSoup(
        content,
        "html.parser"
    )

    issues = []

    # Remove dangerous/non-content elements.
    for tag in soup([
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "form",
    ]):

        tag.decompose()

        issues.append(
            "Removed unsupported or unsafe HTML element."
        )

    # Remove SVG elements that survived parsing.
    for tag in soup.find_all("svg"):

        tag.decompose()

        issues.append(
            "Removed SVG artifact."
        )

    # Remove literal standalone SVG artifacts.
    for text_node in list(
        soup.find_all(string=True)
    ):

        if (
            text_node.strip().lower()
            == "svg"
        ):

            text_node.extract()

            issues.append(
                "Removed literal SVG artifact."
            )

    # Remove HTML comments.
    for comment in soup.find_all(
        string=lambda x: isinstance(x, Comment)
    ):

        comment.extract()

    # Strip unsupported tags.
    for tag in soup.find_all(True):

        if tag.name.lower() not in ALLOWED_TAGS:

            tag_name = tag.name

            tag.unwrap()

            issues.append(
                f"Removed unsupported HTML tag: {tag_name}"
            )

    # Clean links.
    for a in soup.find_all("a"):

        href = (
            a.get("href")
            or ""
        ).strip()

        if not re.match(
            r"^https?://",
            href,
            flags=re.I
        ):

            a.unwrap()

            issues.append(
                "Removed an invalid link."
            )

    # Tables need coherent structure.
    for table in soup.find_all("table"):

        rows = table.find_all("tr")

        if len(rows) < 1:

            table.decompose()

            issues.append(
                "Removed an empty table."
            )

            continue

        max_cells = max(
            (
                len(
                    r.find_all(
                        ["th", "td"]
                    )
                )
                for r in rows
            ),
            default=0
        )

        if max_cells < 2:

            table.decompose()

            issues.append(
                "Removed a malformed table."
            )

    # Remove empty paragraphs.
    for p in soup.find_all("p"):

        if not clean_text(
            p.get_text(
                " ",
                strip=True
            )
        ):

            p.decompose()

    cleaned = str(soup)

    # Basic structure check.
    if not soup.find("p") and not soup.find(
        [
            "ul",
            "ol",
            "table",
            "blockquote",
        ]
    ):

        issues.append(
            "Article has no recognizable content structure."
        )

    text = clean_text(
        soup.get_text(
            " ",
            strip=True
        )
    )

    if len(text) < 500:

        issues.append(
            "Article is too short to be useful."
        )

    return (
        cleaned.strip(),
        issues
    )


# ---------------------------------------------------------------------------
# HIGH-RISK CLAIM DETECTION
# ---------------------------------------------------------------------------

def detect_high_risk_claim_language(content):

    text = clean_text(
        BeautifulSoup(
            content or "",
            "html.parser"
        ).get_text(
            " ",
            strip=True
        )
    )

    matches = []

    for pattern in HIGH_RISK_CLAIM_PATTERNS:

        if re.search(
            pattern,
            text,
            flags=re.I
        ):

            matches.append(pattern)

    return matches


# ---------------------------------------------------------------------------
# FINAL FACT + QUALITY CHECK
# ---------------------------------------------------------------------------

def quality_check(
    topic_title,
    source_name,
    source_text,
    editorial_brief,
    article_html,
    html_issues
):

    compact_brief, source_excerpt = (
        compact_writer_context(
            source_text,
            editorial_brief,
            max_source_chars=3500,
            max_facts=9,
        )
    )

    article_excerpt = (
        article_html or ""
    )[:12000]

    high_risk_patterns = (
        detect_high_risk_claim_language(
            article_html
        )
    )

    prompt = f"""
You are the final evidence and quality editor for AIToolNotes.

Check whether this article is accurate, useful, and safe to publish using ONLY
the supplied evidence.

TOPIC:
{topic_title}

SOURCE:
{source_name}

EDITORIAL BRIEF + EVIDENCE:

{json.dumps(
    compact_brief,
    ensure_ascii=False,
    separators=(",", ":")
)}

SOURCE EXCERPT:

<BEGIN_SOURCE>

{source_excerpt}

<END_SOURCE>

DETERMINISTIC HTML ISSUES:

{json.dumps(
    html_issues,
    ensure_ascii=False
)}

HIGH-RISK CLAIM LANGUAGE DETECTED:

{json.dumps(
    high_risk_patterns,
    ensure_ascii=False
)}

ARTICLE HTML:

<BEGIN_ARTICLE>

{article_excerpt}

<END_ARTICLE>

Return ONLY valid JSON:

{{
  "publish": false,
  "score": 0,
  "issues": [],
  "unsupported_claims": [],
  "missing_value": [],
  "style_issues": [],
  "revision_instructions": ""
}}

Rules:

1. Check concrete factual claims against the evidence ledger and source.

2. Numbers, product names, APIs, prices, dates, specifications, availability,
   quotes, partnerships, and performance claims require direct support.

3. The strength of the wording must match the strength of the evidence.

4. A supported fact can still be misleading if the article exaggerates what
   that fact proves.

5. Distinguish benchmark/test results from real-world outcomes.

6. Do not allow a result from one model, benchmark, geography, experiment,
   population, or timeframe to be generalized beyond its evidence.

7. Treat guarantees and absolute statements as high-risk claims requiring
   explicit evidence.

8. Flag invented facts, fake experience, fabricated quotes, misleading
   certainty, repetition, generic filler, and unsupported actionable
   instructions.

9. High-risk language is a review trigger, not an automatic failure.
   Determine whether the supplied evidence actually supports the wording.

10. Examples:

    "The benchmark increased from 53% to 69%"
    can be a FACT if supported.

    "The results suggest improved reliability"
    can be an INFERENCE if appropriately supported.

    "The system guarantees production reliability"
    is UNSUPPORTED unless the source explicitly establishes such a guarantee.

11. Respect the deterministic HTML issues provided.

12. Score:
    10 = exceptional
    9 = excellent
    8 = strong
    7 = acceptable
    6 or below = needs work

13. Publish only when:
    - score >= {MIN_QUALITY_SCORE}
    - there are no material unsupported factual claims
    - there are no unresolved HTML issues
    - the article provides useful reader value
    - claims are appropriately scoped

14. Do not reject cautious language such as "may", "could", "suggests",
    "the results indicate", or "in the tested setup" when appropriate.

15. If the article contains an exact numerical count such as "three major
    changes", verify that the article actually contains exactly that number
    of major items or that the source explicitly uses that grouping.
"""

    return extract_json_object(
        call_ai(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a strict publication gate. "
                        "Reject unsupported factual claims."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            2500
        )
    )


# ---------------------------------------------------------------------------
# ARTICLE REVISION
# ---------------------------------------------------------------------------

def revise_article(
    topic_title,
    source_name,
    source_text,
    editorial_brief,
    article_html,
    quality_result
):

    feedback = json.dumps(
        {
            "issues": quality_result.get(
                "issues",
                []
            ),

            "unsupported_claims":
                quality_result.get(
                    "unsupported_claims",
                    []
                ),

            "missing_value":
                quality_result.get(
                    "missing_value",
                    []
                ),

            "style_issues":
                quality_result.get(
                    "style_issues",
                    []
                ),

            "revision_instructions":
                quality_result.get(
                    "revision_instructions",
                    ""
                ),
        },
        ensure_ascii=False,
        indent=2
    )

    return generate_article(
        topic_title,
        source_name,
        source_text,
        editorial_brief,
        revision_feedback=feedback,
    )


# ---------------------------------------------------------------------------
# LINK INJECTION
# ---------------------------------------------------------------------------

def inject_affiliate_links(content):

    for tool, url in AFFILIATE_LINKS.items():

        if not url:
            continue

        pattern = re.compile(
            r'(?<!["\'>])\b('
            + re.escape(tool)
            + r')\b',
            re.I
        )

        content = pattern.sub(
            lambda m: (
                f'<a href="{html.escape(url, quote=True)}" '
                f'rel="nofollow sponsored">'
                f'{m.group(1)}'
                f'</a>'
            ),
            content,
            count=1,
        )

    return content


def inject_internal_links(
    content,
    posted_history,
    current_link
):

    candidates = [

        p

        for p in posted_history

        if isinstance(p, dict)
        and p.get("post_url")
        and p.get("link") != current_link
        and p.get("title")
    ]

    if not candidates:
        return content

    picks = candidates[
        -INTERNAL_LINKS_PER_POST:
    ]

    links_html = "".join(

        f'<li>'
        f'<a href="{html.escape(p["post_url"], quote=True)}">'
        f'{html.escape(p["title"])}'
        f'</a>'
        f'</li>'

        for p in picks
    )

    return (
        content
        + "<h2>Related reading</h2>"
        + f"<ul>{links_html}</ul>"
    )


# ---------------------------------------------------------------------------
# BLOGGER PUBLISH
# ---------------------------------------------------------------------------

def post_to_blogger(
    service,
    title,
    content
):

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

    url = result.get(
        "url",
        ""
    )

    print(
        f"  Posted to Blogger: {url}"
    )

    return result, url


# ---------------------------------------------------------------------------
# HISTORY
# ---------------------------------------------------------------------------

def load_posted_history():

    try:

        with open(
            POSTED_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        return (
            data
            if isinstance(data, list)
            else []
        )

    except Exception:

        return []


def save_posted_history(posted):

    with open(
        POSTED_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            posted[-500:],
            f,
            ensure_ascii=False,
            indent=2
        )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():

    print(
        "AIToolNotes Intelligent Blog Automation v3.2 Starting..."
    )

    print(
        "Mode: source -> intelligence -> evidence -> write -> "
        "HTML cleanup -> fact check -> publish"
    )

    posted = load_posted_history()

    posted_titles = {
        p.get("title")

        for p in posted

        if (
            isinstance(p, dict)
            and p.get("title")
        )
    }

    posted_links = {
        p.get("link")

        for p in posted

        if (
            isinstance(p, dict)
            and p.get("link")
        )
    }

    posted_titles.update(
        p

        for p in posted

        if isinstance(p, str)
    )

    service = get_blogger_service()

    all_topics = collect_topics()

    seen_titles = set()
    candidate_pool = []

    # Build a buffer larger than the publishing quota.
    # Blocked sources must not consume the entire run.
    candidate_buffer_limit = max(
        MAX_POSTS_PER_RUN * 3,
        6
    )

    for topic in all_topics:

        title = (
            topic.get("title", "")
            .strip()
        )

        link = (
            topic.get("link", "")
            .strip()
        )

        if len(title) <= 15:
            continue

        if title in seen_titles:
            continue

        if link and link in posted_links:
            continue

        if is_obvious_duplicate(
            title,
            posted_titles
        ):
            continue

        seen_titles.add(title)

        candidate_pool.append(
            topic
        )

        if (
            len(candidate_pool)
            >= candidate_buffer_limit
        ):
            break

    print(
        f"\nCandidate pool: "
        f"{len(candidate_pool)} "
        f"(buffer: {candidate_buffer_limit})"
    )

    # Validate source accessibility before counting
    # candidates toward the publishing quota.
    usable_topics = []

    for topic_data in candidate_pool:

        if (
            len(usable_topics)
            >= MAX_POSTS_PER_RUN
        ):
            break

        title = topic_data["title"]

        link = topic_data.get(
            "link",
            ""
        )

        print(
            f"\nChecking source: "
            f"{title[:100]}"
        )

        try:

            source_text = (
                fetch_source_article_text(
                    link
                )
            )

            if len(source_text) < MIN_SOURCE_CHARS:

                print(
                    f"  SKIP: source text too short "
                    f"({len(source_text)} chars)."
                )

                continue

            usable_topics.append(
                (
                    topic_data,
                    source_text
                )
            )

        except Exception as e:

            print(
                f"  SKIP: source validation failed: {e}"
            )

            continue

    print(
        f"\nUsable candidates: "
        f"{len(usable_topics)} "
        f"(cap: {MAX_POSTS_PER_RUN})"
    )

    published_this_run = 0

    for i, (
        topic_data,
        source_text
    ) in enumerate(
        usable_topics,
        1
    ):

        title = topic_data["title"]

        source = topic_data["source"]

        link = topic_data.get(
            "link",
            ""
        )

        published = topic_data.get(
            "published",
            ""
        )

        print(
            f"\nArticle {i}/{len(usable_topics)}: "
            f"{title[:100]}"
        )

        try:

            # ---------------------------------------------------------------
            # INTELLIGENCE
            # ---------------------------------------------------------------

            print(
                "  Analyzing story and building evidence ledger..."
            )

            brief = analyze_story(
                title,
                source,
                source_text,
                published,
            )

            decision = bool(
                brief.get(
                    "publish_decision"
                )
            )

            print(
                "  Decision: "
                f"{'PUBLISHABLE' if decision else 'SKIP'}"
            )

            print(
                f"  Type: "
                f"{brief.get('article_type', 'unknown')}"
            )

            print(
                f"  Intent: "
                f"{brief.get('search_intent', 'unknown')}"
            )

            print(
                "  Commercial intent: "
                f"{brief.get('commercial_intent', 'unknown')}"
            )

            print(
                "  Evidence facts: "
                f"{len(brief.get('evidence_ledger', []))}"
            )

            if not decision:

                print(
                    "  Skipped: "
                    f"{brief.get(
                        'reason_if_rejected',
                        'insufficient evidence'
                    )}"
                )

                continue

            # ---------------------------------------------------------------
            # WRITING
            # ---------------------------------------------------------------

            print(
                "  Writing evidence-constrained article..."
            )

            article = generate_article(
                title,
                source,
                source_text,
                brief,
            )

            # ---------------------------------------------------------------
            # HTML CLEANUP
            # ---------------------------------------------------------------

            article, html_issues = (
                validate_and_clean_html(
                    article
                )
            )

            print(
                "  HTML check: "
                f"{'PASS' if not html_issues else 'ISSUES FOUND'}"
            )

            if html_issues:

                print(
                    "  HTML cleanup issues: "
                    f"{html_issues}"
                )

            # ---------------------------------------------------------------
            # QUALITY CHECK
            # ---------------------------------------------------------------

            quality = quality_check(
                title,
                source,
                source_text,
                brief,
                article,
                html_issues,
            )

            score = int(
                quality.get(
                    "score",
                    0
                ) or 0
            )

            publish = bool(
                quality.get(
                    "publish"
                )
            )

            print(
                f"  Quality score: "
                f"{score}/10 | "
                f"Publish: {publish}"
            )

            # ---------------------------------------------------------------
            # ONE REVISION
            # ---------------------------------------------------------------

            if (
                not publish
                or score < MIN_QUALITY_SCORE
            ):

                if MAX_REWRITE_ATTEMPTS:

                    print(
                        "  Revising article once..."
                    )

                    article = revise_article(
                        title,
                        source,
                        source_text,
                        brief,
                        article,
                        quality,
                    )

                    article, html_issues = (
                        validate_and_clean_html(
                            article
                        )
                    )

                    quality = quality_check(
                        title,
                        source,
                        source_text,
                        brief,
                        article,
                        html_issues,
                    )

                    score = int(
                        quality.get(
                            "score",
                            0
                        ) or 0
                    )

                    publish = bool(
                        quality.get(
                            "publish"
                        )
                    )

                    print(
                        f"  Revised score: "
                        f"{score}/10 | "
                        f"Publish: {publish}"
                    )

            # ---------------------------------------------------------------
            # FINAL PUBLISH GATE
            # ---------------------------------------------------------------

            if (
                not publish
                or score < MIN_QUALITY_SCORE
            ):

                print(
                    "  NOT PUBLISHED. "
                    "Article failed the evidence/quality gate."
                )

                if quality.get(
                    "unsupported_claims"
                ):

                    print(
                        "  Unsupported claims detected: "
                        f"{len(quality.get('unsupported_claims', []))}"
                    )

                continue

            # ---------------------------------------------------------------
            # LINK INJECTION
            # ---------------------------------------------------------------

            article = inject_affiliate_links(
                article
            )

            article = inject_internal_links(
                article,
                posted,
                link,
            )

            # ---------------------------------------------------------------
            # FINAL HTML CLEANUP
            # ---------------------------------------------------------------

            article, final_html_issues = (
                validate_and_clean_html(
                    article
                )
            )

            if final_html_issues:

                print(
                    "  NOT PUBLISHED. "
                    "Final HTML validation failed: "
                    f"{final_html_issues}"
                )

                continue

            # ---------------------------------------------------------------
            # BLOGGER
            # ---------------------------------------------------------------

            _, post_url = post_to_blogger(
                service,
                title,
                article,
            )

            # ---------------------------------------------------------------
            # SAVE HISTORY
            # ---------------------------------------------------------------

            posted.append({

                "title": title,

                "link": link,

                "post_url": post_url,

                "source": source,

                "quality_score": score,

                "article_type":
                    brief.get(
                        "article_type",
                        ""
                    ),

                "commercial_intent":
                    brief.get(
                        "commercial_intent",
                        ""
                    ),

                "evidence_facts":
                    len(
                        brief.get(
                            "evidence_ledger",
                            []
                        )
                    ),
            })

            posted = posted[-500:]

            save_posted_history(
                posted
            )

            posted_titles.add(
                title
            )

            posted_links.add(
                link
            )

            published_this_run += 1

            time.sleep(3)

        except Exception as e:

            print(
                f"  Failed: "
                f"{type(e).__name__}: {e}"
            )

            continue

    print(
        f"\nDone. Published "
        f"{published_this_run} article(s)."
    )


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()