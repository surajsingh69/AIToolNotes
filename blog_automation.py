````python
# AIToolNotes Intelligent Blog Automation v5
#
# RSS -> source extraction -> editorial intelligence
# -> deterministic evidence verification
# -> headline/SEO/engagement -> writer
# -> deterministic HTML checks
# -> fact/quality gate -> one revision
# -> contextual links -> final validation -> Blogger
#
# v5 improvements:
# - Evidence excerpts are deterministically verified against source text.
# - Editorial score is calculated in Python.
# - Larger candidate pool.
# - Better source-container extraction.
# - Better headline selection.
# - Revision receives the previous article.
# - Affiliate injection is safe and supports aliases.
# - Final enrichment is deterministically validated.
# - Richer publishing history.
#
# Required:
#   GROQ_API_KEY
#   BLOG_ID
#
# Google Blogger:
#   credentials.json in this script directory.
#
# Optional:
#   AFFILIATE_NOTION_URL
#   AFFILIATE_JASPER_URL
#   AFFILIATE_MURF_URL
#   AFFILIATE_SYNTHESIA_URL
#   AFFILIATE_CUSTOMGPT_URL

import os
import json
import requests
import time
import re
import difflib
import html
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, NavigableString
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

# Evaluate more stories before selecting winners.
RAW_CANDIDATE_LIMIT = 40
MAX_EDITORIAL_CANDIDATES = 24

INTERNAL_LINKS_PER_POST = 2

SOURCE_MAX_CHARS = 16000
MIN_SOURCE_CHARS = 900

MIN_QUALITY_SCORE = 8.0
MIN_ENGAGEMENT_SCORE = 7.0
MIN_EDITORIAL_SCORE = 6.5

MAX_REWRITE_ATTEMPTS = 1

MAX_SOURCE_FACTS = 12
MAX_EVIDENCE_CHARS_PER_FACT = 300

MAX_ARTICLE_WORDS = 1100
MIN_ARTICLE_WORDS = 500

MAX_REVISION_ARTICLE_CHARS = 18000

AFFILIATE_LINKS = {
    "notion": os.getenv("AFFILIATE_NOTION_URL", "").strip(),
    "jasper": os.getenv("AFFILIATE_JASPER_URL", "").strip(),
    "murf": os.getenv("AFFILIATE_MURF_URL", "").strip(),
    "synthesia": os.getenv("AFFILIATE_SYNTHESIA_URL", "").strip(),
    "customgpt": os.getenv("AFFILIATE_CUSTOMGPT_URL", "").strip(),
}

# Matching aliases for contextual affiliate placement.
AFFILIATE_ALIASES = {
    "notion": [
        "notion"
    ],
    "jasper": [
        "jasper",
        "jasper ai"
    ],
    "murf": [
        "murf",
        "murf ai"
    ],
    "synthesia": [
        "synthesia",
        "synthesia ai"
    ],
    "customgpt": [
        "customgpt",
        "custom gpt",
        "custom gpts",
    ],
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
# BLOGGER
# ---------------------------------------------------------------------------

def get_blogger_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_FILE,
                SCOPES,
            )
            creds = flow.run_local_server(
                port=8080,
                open_browser=True,
            )

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build(
        "blogger",
        "v3",
        credentials=creds,
    )


# ---------------------------------------------------------------------------
# TEXT HELPERS
# ---------------------------------------------------------------------------

def clean_text(text):
    return re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip()


def normalize_for_match(text):
    text = html.unescape(text or "")
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def keyword_tokens(text):
    words = re.findall(
        r"[a-z0-9]{3,}",
        (text or "").lower(),
    )

    stopwords = {
        "the", "and", "for", "with", "that", "this",
        "from", "into", "about", "what", "when",
        "where", "which", "will", "could", "have",
        "has", "how", "new", "your", "you", "are",
        "its", "their", "they", "than", "more",
        "after", "before", "using", "tool", "tools",
        "artificial", "intelligence",
    }

    return {
        word
        for word in words
        if word not in stopwords
    }


# ---------------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------------

def get_rss_items(url, source, limit=10):
    out = []

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)

        items = root.findall(".//item")

        if items:
            for item in items[:limit]:
                title = clean_text(
                    item.findtext("title", "")
                )

                link = clean_text(
                    item.findtext("link", "")
                )

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
            ns = {
                "atom": "http://www.w3.org/2005/Atom"
            }

            entries = root.findall(
                ".//atom:entry",
                ns,
            )

            for entry in entries[:limit]:
                title = clean_text(
                    entry.findtext(
                        "atom:title",
                        "",
                        ns,
                    )
                )

                published = (
                    clean_text(
                        entry.findtext(
                            "atom:published",
                            "",
                            ns,
                        )
                    )
                    or clean_text(
                        entry.findtext(
                            "atom:updated",
                            "",
                            ns,
                        )
                    )
                )

                link = ""

                for link_el in entry.findall(
                    "atom:link",
                    ns,
                ):
                    href = clean_text(
                        link_el.attrib.get(
                            "href",
                            "",
                        )
                    )

                    rel = link_el.attrib.get(
                        "rel",
                        "alternate",
                    )

                    if href and rel == "alternate":
                        link = href
                        break

                if not link:
                    link_el = entry.find(
                        "atom:link",
                        ns,
                    )

                    if link_el is not None:
                        link = clean_text(
                            link_el.attrib.get(
                                "href",
                                "",
                            )
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


def collect_topics():
    print(
        "Collecting AI topics from configured sources..."
    )

    topics = []

    for url, source in AI_TOOL_SOURCES:
        topics.extend(
            get_rss_items(
                url,
                source,
                limit=10,
            )
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
            (title or "").lower(),
        ),
    ).strip()


def title_similarity(a, b):
    return difflib.SequenceMatcher(
        None,
        normalize_title(a),
        normalize_title(b),
    ).ratio()


def is_obvious_duplicate(
    title,
    existing_titles,
    threshold=0.88,
):
    normalized = normalize_title(title)

    for old in existing_titles:
        if not old:
            continue

        if normalized and normalized == normalize_title(old):
            return True

        if title_similarity(
            title,
            old,
        ) >= threshold:
            return True

    return False


# ---------------------------------------------------------------------------
# FRESHNESS
# ---------------------------------------------------------------------------

def parse_published_date(value):
    if not value:
        return None

    value = value.strip()

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            )
        except ValueError:
            continue

    return None


def freshness_score(published):
    dt = parse_published_date(published)

    if not dt:
        return 5.0

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    now = datetime.now(timezone.utc)

    age_hours = max(
        0,
        (now - dt).total_seconds() / 3600,
    )

    if age_hours <= 24:
        return 10.0

    if age_hours <= 72:
        return 9.0

    if age_hours <= 168:
        return 8.0

    if age_hours <= 336:
        return 6.5

    if age_hours <= 720:
        return 5.0

    return 3.0


# ---------------------------------------------------------------------------
# SOURCE EXTRACTION
# ---------------------------------------------------------------------------

def score_content_container(container):
    if not container:
        return -1

    paragraphs = container.find_all("p")
    text = clean_text(
        container.get_text(
            " ",
            strip=True,
        )
    )

    if len(text) < 300:
        return -1

    paragraph_text = sum(
        len(clean_text(p.get_text(" ", strip=True)))
        for p in paragraphs
    )

    links = container.find_all("a")

    link_text = sum(
        len(clean_text(a.get_text(" ", strip=True)))
        for a in links
    )

    text_length = max(
        len(text),
        1,
    )

    paragraph_score = min(
        paragraph_text / 5000,
        5,
    )

    density_score = (
        paragraph_text / text_length
    ) * 5

    link_penalty = (
        link_text / text_length
    ) * 5

    paragraph_count_bonus = min(
        len(paragraphs) / 10,
        3,
    )

    return (
        paragraph_score
        + density_score
        + paragraph_count_bonus
        - link_penalty
    )


def fetch_source_article_text(
    url,
    max_chars=SOURCE_MAX_CHARS,
):
    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

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
            "iframe",
            "object",
            "embed",
        ]):
            tag.decompose()

        candidates = []

        article = soup.find("article")
        if article:
            candidates.append(article)

        main = soup.find("main")
        if main:
            candidates.append(main)

        role_main = soup.find(
            attrs={"role": "main"}
        )
        if role_main:
            candidates.append(role_main)

        for div in soup.find_all(
            ["div", "section"]
        ):
            if div.find_all("p"):
                candidates.append(div)

        scored = []

        for candidate in candidates:
            score = score_content_container(
                candidate
            )

            if score >= 0:
                scored.append(
                    (score, candidate)
                )

        if scored:
            scored.sort(
                key=lambda x: x[0],
                reverse=True,
            )

            container = scored[0][1]

        else:
            container = soup.body

        if not container:
            return ""

        text = clean_text(
            container.get_text(
                " ",
                strip=True,
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
        flags=re.I,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
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

    choice = response.choices[0]

    content = (
        choice.message.content
        or ""
    )

    if choice.finish_reason == "length":
        print(
            "  WARNING: AI response reached token limit"
        )

    return content.strip()


# ---------------------------------------------------------------------------
# EVIDENCE VERIFICATION
# ---------------------------------------------------------------------------

def evidence_match_score(
    evidence,
    source_text,
):
    evidence_norm = normalize_for_match(
        evidence
    )

    source_norm = normalize_for_match(
        source_text
    )

    if not evidence_norm:
        return 0.0

    if evidence_norm in source_norm:
        return 1.0

    evidence_tokens = keyword_tokens(
        evidence_norm
    )

    source_tokens = keyword_tokens(
        source_norm
    )

    if not evidence_tokens or not source_tokens:
        return 0.0

    overlap = (
        len(
            evidence_tokens
            & source_tokens
        )
        / len(evidence_tokens)
    )

    return min(
        overlap,
        1.0,
    )


def verify_evidence_ledger(
    ledger,
    source_text,
):
    verified = []
    rejected = []

    for item in ledger:
        if not isinstance(item, dict):
            continue

        fact = clean_text(
            item.get("fact", "")
        )

        evidence = clean_text(
            item.get("evidence", "")
        )

        confidence = clean_text(
            item.get("confidence", "")
        )

        if not fact or not evidence:
            rejected.append({
                "fact": fact,
                "reason": "Missing fact or evidence.",
            })
            continue

        score = evidence_match_score(
            evidence,
            source_text,
        )

        # Exact source substring is ideal.
        # Token overlap is accepted only when strong.
        if score >= 0.92:
            verified.append({
                "fact": fact[:500],
                "evidence": evidence[
                    :MAX_EVIDENCE_CHARS_PER_FACT
                ],
                "confidence": (
                    confidence
                    if confidence in {
                        "high",
                        "medium",
                        "low",
                    }
                    else "medium"
                ),
                "verification_score": round(
                    score,
                    3,
                ),
            })
        else:
            rejected.append({
                "fact": fact,
                "evidence": evidence,
                "reason": (
                    "Evidence could not be "
                    "strongly matched to source."
                ),
                "verification_score": round(
                    score,
                    3,
                ),
            })

    return verified, rejected


# ---------------------------------------------------------------------------
# EDITORIAL SCORING
# ---------------------------------------------------------------------------

def clamp_score(value):
    try:
        return max(
            0.0,
            min(
                10.0,
                float(value),
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def calculate_editorial_score(
    brief,
    source_text,
    published,
):
    reader_value = clamp_score(
        brief.get("reader_value_score", 0)
    )

    novelty = clamp_score(
        brief.get("novelty_score", 0)
    )

    search_value = clamp_score(
        brief.get("search_value_score", 0)
    )

    commercial_relevance = clamp_score(
        brief.get(
            "commercial_relevance_score",
            0,
        )
    )

    source_strength = clamp_score(
        brief.get(
            "source_strength_score",
            0,
        )
    )

    content_depth = clamp_score(
        brief.get(
            "content_depth_score",
            0,
        )
    )

    freshness = freshness_score(
        published
    )

    evidence_count = len(
        brief.get(
            "evidence_ledger",
            [],
        )
    )

    evidence_bonus = min(
        evidence_count / 12 * 1.0,
        1.0,
    )

    score = (
        reader_value * 0.25
        + novelty * 0.15
        + search_value * 0.15
        + commercial_relevance * 0.10
        + source_strength * 0.15
        + content_depth * 0.10
        + freshness * 0.10
        + evidence_bonus
    )

    return round(
        min(score, 10.0),
        2,
    )


# ---------------------------------------------------------------------------
# EDITORIAL INTELLIGENCE
# ---------------------------------------------------------------------------

def analyze_story(
    topic_title,
    source_name,
    source_text,
    published="",
):
    if len(source_text) < MIN_SOURCE_CHARS:
        return {
            "publish_decision": False,
            "evidence_ledger": [],
            "topic_score": 0,
            "reason_if_rejected": (
                "Insufficient source material."
            ),
        }

    prompt = f"""
You are the editorial intelligence layer for AIToolNotes.

Do NOT write the article.

Analyze only the supplied source.

SOURCE NAME:
{source_name}

RSS TITLE:
{topic_title}

PUBLISHED:
{published or "unknown"}

SOURCE TEXT:
<BEGIN_SOURCE>
{source_text}
<END_SOURCE>

Return ONLY valid JSON.

Use exactly these keys:

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
  "engagement_strategy": [],

  "headline_options": [],

  "commercial_intent": "low",
  "evergreen_potential": 0,

  "reader_value_score": 0,
  "novelty_score": 0,
  "search_value_score": 0,
  "commercial_relevance_score": 0,
  "source_strength_score": 0,
  "content_depth_score": 0,

  "reason_if_rejected": ""
}}

Allowed article types:
news_explainer
practical_guide
tool_review
comparison
roundup
analysis

Allowed commercial intent:
low
medium
high

Rules:

1. Every factual item must be supported by the source.

2. Every evidence ledger item must contain a short,
   near-verbatim excerpt from the supplied source.

3. Do not invent evidence.

4. Do not use outside knowledge.

5. Never invent:
   product names, APIs, prices, dates, statistics,
   benchmarks, hardware requirements, integrations,
   partnerships, quotes, users, availability,
   capabilities, or performance.

6. Company promotional claims must remain attributed.

7. Reject thin or useless stories.

8. Do not publish simply because a company announced something.

9. The article must have a clear reader reason to exist.

10. Search intent must be realistic.

11. Keywords must be naturally supported.

12. content_gap must explain what the article can clarify
    without introducing outside facts.

13. reader_questions must contain 2-5 supportable questions.

14. headline_options must contain 3-5 accurate headlines.

15. Headlines should generally be under 70 characters.

16. Score each editorial dimension from 0-10.

17. reader_value_score measures how useful the story is.

18. novelty_score measures whether the development is genuinely
    distinct from ordinary repeated AI news.

19. search_value_score measures potential usefulness for people
    actively searching for the topic.

20. commercial_relevance_score measures whether the topic has
    legitimate tool/business relevance, not whether it can be
    artificially monetized.

21. source_strength_score measures how complete and trustworthy
    the supplied source material is.

22. content_depth_score measures whether enough evidence exists
    to create a useful article.

23. Keep the evidence ledger to at most {MAX_SOURCE_FACTS} facts.
"""

    result = extract_json_object(
        call_ai(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a strict evidence editor. "
                        "Accuracy and reader value come before volume."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            5000,
        )
    )

    defaults = {
        "important_facts": [],
        "evidence_ledger": [],
        "missing_context": [],
        "unsupported_claims_to_avoid": [],
        "secondary_keywords": [],
        "reader_questions": [],
        "headline_options": [],
        "engagement_strategy": [],
    }

    for key, default in defaults.items():
        result.setdefault(
            key,
            default,
        )

    raw_ledger = result.get(
        "evidence_ledger",
        [],
    )

    raw_ledger = raw_ledger[
        :MAX_SOURCE_FACTS
    ]

    verified_ledger, rejected_ledger = (
        verify_evidence_ledger(
            raw_ledger,
            source_text,
        )
    )

    result["evidence_ledger"] = (
        verified_ledger
    )

    result["rejected_evidence"] = (
        rejected_ledger
    )

    result["important_facts"] = (
        result["important_facts"]
        [:MAX_SOURCE_FACTS]
    )

    result["secondary_keywords"] = (
        result["secondary_keywords"]
        [:8]
    )

    result["reader_questions"] = (
        result["reader_questions"]
        [:5]
    )

    result["headline_options"] = (
        result["headline_options"]
        [:5]
    )

    result["missing_context"] = (
        result["missing_context"]
        [:6]
    )

    result[
        "unsupported_claims_to_avoid"
    ] = (
        result[
            "unsupported_claims_to_avoid"
        ][:8]
    )

    try:
        result["evergreen_potential"] = int(
            float(
                result.get(
                    "evergreen_potential",
                    0,
                )
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        result["evergreen_potential"] = 0

    result["evergreen_potential"] = max(
        0,
        min(
            10,
            result["evergreen_potential"],
        ),
    )

    # Deterministic editorial score.
    result["topic_score"] = (
        calculate_editorial_score(
            result,
            source_text,
            published,
        )
    )

    if len(
        result["evidence_ledger"]
    ) < 2:
        result["publish_decision"] = False

        result["reason_if_rejected"] = (
            "Not enough independently "
            "verified source evidence."
        )

    if result["topic_score"] < MIN_EDITORIAL_SCORE:
        result["publish_decision"] = False

        result["reason_if_rejected"] = (
            result.get(
                "reason_if_rejected"
            )
            or "Editorial score below threshold."
        )

    return result


# ---------------------------------------------------------------------------
# SOURCE PASSAGES
# ---------------------------------------------------------------------------

def split_source_passages(
    source_text,
    max_passages=10,
):
    text = clean_text(
        source_text
    )

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    passages = []

    current = ""

    for sentence in sentences:
        sentence = clean_text(
            sentence
        )

        if not sentence:
            continue

        if len(current) + len(sentence) > 700:
            if current:
                passages.append(
                    current.strip()
                )

            current = sentence

        else:
            current += " " + sentence

    if current:
        passages.append(
            current.strip()
        )

    return passages[
        :max_passages
    ]


def relevant_source_passages(
    source_text,
    editorial_brief,
    max_passages=8,
):
    passages = split_source_passages(
        source_text,
        max_passages=50,
    )

    query = (
        editorial_brief.get(
            "primary_keyword",
            "",
        )
        + " "
        + editorial_brief.get(
            "useful_angle",
            "",
        )
        + " "
        + " ".join(
            editorial_brief.get(
                "secondary_keywords",
                [],
            )
        )
    )

    query_tokens = keyword_tokens(
        query
    )

    scored = []

    for passage in passages:
        passage_tokens = keyword_tokens(
            passage
        )

        if not passage_tokens:
            continue

        overlap = len(
            query_tokens
            & passage_tokens
        )

        score = overlap / max(
            len(query_tokens),
            1,
        )

        scored.append(
            (
                score,
                passage,
            )
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    selected = []

    for _, passage in scored:
        if passage not in selected:
            selected.append(passage)

        if len(selected) >= max_passages:
            break

    return selected


# ---------------------------------------------------------------------------
# WRITER CONTEXT
# ---------------------------------------------------------------------------

def compact_writer_context(
    source_text,
    editorial_brief,
    max_facts=10,
):
    ledger = (
        editorial_brief.get(
            "evidence_ledger",
            [],
        )
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
                "fact": fact[:400],
                "evidence": evidence[:300],
                "confidence": confidence[:20],
            })

    passages = relevant_source_passages(
        source_text,
        editorial_brief,
        max_passages=8,
    )

    compact_brief = {
        "story_summary": editorial_brief.get(
            "story_summary",
            "",
        ),
        "reader_problem_or_interest":
            editorial_brief.get(
                "reader_problem_or_interest",
                "",
            ),
        "why_it_matters":
            editorial_brief.get(
                "why_it_matters",
                "",
            ),
        "who_should_care":
            editorial_brief.get(
                "who_should_care",
                "",
            ),
        "useful_angle":
            editorial_brief.get(
                "useful_angle",
                "",
            ),
        "article_type":
            editorial_brief.get(
                "article_type",
                "news_explainer",
            ),
        "search_intent":
            editorial_brief.get(
                "search_intent",
                "",
            ),
        "primary_keyword":
            editorial_brief.get(
                "primary_keyword",
                "",
            ),
        "secondary_keywords":
            editorial_brief.get(
                "secondary_keywords",
                [],
            )[:8],
        "content_gap":
            editorial_brief.get(
                "content_gap",
                "",
            ),
        "hook_strategy":
            editorial_brief.get(
                "hook_strategy",
                "",
            ),
        "reader_questions":
            editorial_brief.get(
                "reader_questions",
                [],
            )[:5],
        "engagement_strategy":
            editorial_brief.get(
                "engagement_strategy",
                [],
            )[:5],
        "headline_options":
            editorial_brief.get(
                "headline_options",
                [],
            )[:5],
        "missing_context":
            editorial_brief.get(
                "missing_context",
                [],
            )[:5],
        "unsupported_claims_to_avoid":
            editorial_brief.get(
                "unsupported_claims_to_avoid",
                [],
            )[:8],
        "evidence_ledger":
            compact_ledger,
    }

    return (
        compact_brief,
        passages,
    )


# ---------------------------------------------------------------------------
# HEADLINE SELECTION
# ---------------------------------------------------------------------------

def headline_candidate_score(
    headline,
    brief,
):
    headline = clean_text(
        headline
    )

    if not headline:
        return -999

    score = 0.0

    length = len(headline)

    if length <= 60:
        score += 2.0
    elif length <= 70:
        score += 1.5
    elif length <= 85:
        score += 0.5
    elif length > 100:
        score -= 3.0

    keyword = clean_text(
        brief.get(
            "primary_keyword",
            "",
        )
    ).lower()

    if keyword and keyword in headline.lower():
        score += 2.0

    tokens = keyword_tokens(
        headline
    )

    if len(tokens) >= 5:
        score += 1.0

    # Avoid obvious clickbait.
    banned = [
        "shocking",
        "you won't believe",
        "insane",
        "game-changing",
        "revolutionary",
        "guaranteed",
        "secret",
        "destroy",
        "finally!",
    ]

    for phrase in banned:
        if phrase in headline.lower():
            score -= 3.0

    # Avoid unnecessary punctuation.
    if headline.count("!") > 0:
        score -= 1.0

    return score


def choose_headline(
    brief,
    fallback,
):
    options = brief.get(
        "headline_options",
        [],
    )

    cleaned = []

    for option in options:
        option = clean_text(option)

        if not option:
            continue

        if len(option) > 100:
            continue

        if any(
            option.lower() == old.lower()
            for old in cleaned
        ):
            continue

        cleaned.append(option)

    if not cleaned:
        return clean_text(
            fallback
        )

    ranked = sorted(
        cleaned,
        key=lambda x: headline_candidate_score(
            x,
            brief,
        ),
        reverse=True,
    )

    return ranked[0]


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
    previous_article="",
):
    compact_brief, source_passages = (
        compact_writer_context(
            source_text,
            editorial_brief,
        )
    )

    selected_headline = choose_headline(
        editorial_brief,
        topic_title,
    )

    revision_block = ""

    if revision_feedback:
        revision_block = f"""
QUALITY REVIEW TO FIX:

{revision_feedback[:4000]}
"""

    previous_article_block = ""

    if previous_article:
        previous_article_block = f"""
PREVIOUS ARTICLE:

<BEGIN_PREVIOUS_ARTICLE>
{previous_article[:MAX_REVISION_ARTICLE_CHARS]}
<END_PREVIOUS_ARTICLE>

Revise this article rather than inventing a completely unrelated article.

Preserve valid factual material.
Remove unsupported claims.
Improve only what the quality review identifies.
"""

    prompt = f"""
Write a genuinely useful AIToolNotes article.

The verified evidence ledger is the factual boundary.

Do not use outside knowledge.

ORIGINAL RSS TITLE:
{topic_title}

PREFERRED HEADLINE:
{selected_headline}

SOURCE:
{source_name}

SOURCE URL:
{source_url}

EDITORIAL BRIEF:
{json.dumps(
    compact_brief,
    ensure_ascii=False,
    separators=(",", ":"),
)}

VERIFIED SOURCE PASSAGES:

<BEGIN_PASSAGES>
{json.dumps(
    source_passages,
    ensure_ascii=False,
)}
<END_PASSAGES>

{revision_block}

{previous_article_block}

ARTICLE REQUIREMENTS:

1. Output RAW HTML ONLY.

2. No Markdown.

3. No code fences.

4. No H1.

5. Use H2/H3 where useful.

6. The first paragraph must immediately explain
   what happened and why it matters.

7. Never use generic AI openings.

8. Do not merely rewrite the source chronologically.

9. Explain unfamiliar terms plainly.

10. Answer the reader's likely questions.

11. Use short paragraphs.

12. Use lists or tables only when they improve clarity.

13. Do not invent instructions.

14. Do not claim personal testing.

15. Do not fabricate quotes.

16. Do not repeat facts unnecessarily.

17. Do not pad the article.

18. Target {MIN_ARTICLE_WORDS}-{MAX_ARTICLE_WORDS}
    only when the evidence supports that length.

19. End with a concrete takeaway.

20. Use the primary keyword naturally.

21. Never keyword-stuff.

22. Attribute promotional claims.

23. Do not use unsupported superlatives.

24. Do not create a fake FAQ.

25. Every factual claim must trace to the verified
    evidence ledger or supplied source passages.

26. If information is not supported, omit it.

"""

    raw = call_ai(
        [
            {
                "role": "system",
                "content": (
                    "You are the senior writer of a "
                    "trustworthy technology publication. "
                    "Stay strictly inside the supplied evidence."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        6000,
    )

    raw = re.sub(
        r"^```(?:html)?\s*",
        "",
        raw.strip(),
        flags=re.I,
    )

    raw = re.sub(
        r"\s*```$",
        "",
        raw,
    )

    return raw.strip()


# ---------------------------------------------------------------------------
# HTML VALIDATION / SANITIZATION
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
        return "", [
            "Article is empty."
        ]

    content = re.sub(
        r"^```(?:html)?\s*",
        "",
        content.strip(),
        flags=re.I,
    )

    content = re.sub(
        r"\s*```$",
        "",
        content,
    )

    soup = BeautifulSoup(
        content,
        "html.parser",
    )

    issues = []

    # Remove unsafe tags.
    for tag in soup([
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "form",
        "svg",
        "math",
        "canvas",
    ]):
        tag.decompose()

        issues.append(
            "Removed unsupported or unsafe HTML element."
        )

    # Remove comments.
    for comment in soup.find_all(
        string=lambda x: isinstance(
            x,
            Comment,
        )
    ):
        comment.extract()

    # Remove H1.
    for h1 in soup.find_all("h1"):
        h1.decompose()

        issues.append(
            "Removed H1 heading."
        )

    # Remove unsupported tags.
    for tag in list(
        soup.find_all(True)
    ):
        name = tag.name.lower()

        if name not in ALLOWED_TAGS:
            tag.unwrap()

            issues.append(
                f"Removed unsupported HTML tag: {name}"
            )

    # Remove dangerous attributes.
    for tag in soup.find_all(True):
        allowed_attrs = set()

        if tag.name == "a":
            allowed_attrs = {
                "href",
                "rel",
                "title",
            }

        for attr in list(
            tag.attrs.keys()
        ):
            attr_lower = attr.lower()

            if (
                attr_lower.startswith("on")
                or attr_lower not in allowed_attrs
            ):
                del tag.attrs[attr]

    # Validate links.
    for a in soup.find_all("a"):
        href = (
            a.get("href") or ""
        ).strip()

        if not re.match(
            r"^https?://",
            href,
            flags=re.I,
        ):
            a.unwrap()

            issues.append(
                "Removed an invalid link."
            )
            continue

        parsed = urlparse(href)

        if parsed.scheme.lower() not in {
            "http",
            "https",
        }:
            a.unwrap()

            issues.append(
                "Removed unsafe link scheme."
            )
            continue

        existing_rel = a.get(
            "rel",
            [],
        )

        if isinstance(
            existing_rel,
            str,
        ):
            existing_rel = (
                existing_rel.split()
            )

        a["rel"] = list(
            dict.fromkeys(
                existing_rel
                + ["noopener"]
            )
        )

    # Validate tables.
    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        if not rows:
            table.decompose()

            issues.append(
                "Removed empty table."
            )
            continue

        max_cells = max(
            (
                len(
                    row.find_all(
                        ["th", "td"]
                    )
                )
                for row in rows
            ),
            default=0,
        )

        if max_cells < 2:
            table.decompose()

            issues.append(
                "Removed malformed table."
            )

    text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    word_count = len(
        text.split()
    )

    if len(text) < 500:
        issues.append(
            "Article is too short."
        )

    if word_count > (
        MAX_ARTICLE_WORDS + 250
    ):
        issues.append(
            "Article exceeds reasonable maximum length."
        )

    if not soup.find(
        ["p", "ul", "ol", "table", "blockquote"]
    ):
        issues.append(
            "Article has no recognizable content structure."
        )

    if not soup.find("h2"):
        issues.append(
            "Article has no H2 heading."
        )

    return (
        str(soup).strip(),
        issues,
    )


def count_words_from_html(content):
    soup = BeautifulSoup(
        content or "",
        "html.parser",
    )

    return len(
        clean_text(
            soup.get_text(
                " ",
                strip=True,
            )
        ).split()
    )


# ---------------------------------------------------------------------------
# QUALITY SCORING
# ---------------------------------------------------------------------------

def deterministic_quality_score(
    result,
):
    weights = {
        "accuracy_score": 0.30,
        "usefulness_score": 0.20,
        "engagement_score": 0.15,
        "readability_score": 0.10,
        "search_quality_score": 0.10,
        "originality_score": 0.15,
    }

    score = 0.0

    for field, weight in weights.items():
        score += (
            clamp_score(
                result.get(
                    field,
                    0,
                )
            )
            * weight
        )

    return round(
        score,
        2,
    )


# ---------------------------------------------------------------------------
# QUALITY / FACT CHECK
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
    compact_brief, source_passages = (
        compact_writer_context(
            source_text,
            editorial_brief,
        )
    )

    word_count = count_words_from_html(
        article_html
    )

    article_excerpt = (
        article_html or ""
    )[:18000]

    prompt = f"""
You are the final evidence, quality,
SEO, and engagement editor for AIToolNotes.

Check this article against the supplied evidence.

TOPIC:
{topic_title}

SOURCE:
{source_name}

SOURCE URL:
{source_url}

WORD COUNT:
{word_count}

EDITORIAL BRIEF:
{json.dumps(
    compact_brief,
    ensure_ascii=False,
    separators=(",", ":"),
)}

VERIFIED SOURCE PASSAGES:
{json.dumps(
    source_passages,
    ensure_ascii=False,
)}

DETERMINISTIC HTML ISSUES:
{json.dumps(
    html_issues,
    ensure_ascii=False,
)}

ARTICLE:
<BEGIN_ARTICLE>
{article_excerpt}
<END_ARTICLE>

Return ONLY valid JSON:

{{
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

Score every dimension from 0-10.

Rules:

1. Every concrete factual claim needs source support.

2. Numbers, names, dates, APIs, prices, specifications,
   availability, quotes, partnerships, performance claims,
   and technical capabilities require direct evidence.

3. Flag invented facts.

4. Flag fabricated quotes.

5. Flag fake personal experience.

6. Flag unsupported instructions.

7. Flag misleading certainty.

8. Flag repetitive or generic filler.

9. Flag generic openings and conclusions.

10. Check whether the article answers the intended search query.

11. Check whether the article provides useful organization
    beyond simply repeating the source.

12. Do not demand information absent from the source.

13. Concise articles can pass if genuinely useful.

14. Below 500 words normally indicates missing value,
    unless the source itself is extremely limited.

15. Deterministic HTML issues must be treated as unresolved
    unless they were only harmless normalization.

16. Do not invent problems just to justify a revision.

"""

    result = extract_json_object(
        call_ai(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a strict publication gate. "
                        "Accuracy comes first."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            3500,
        )
    )

    result["score"] = (
        deterministic_quality_score(
            result
        )
    )

    try:
        result["engagement_score"] = clamp_score(
            result.get(
                "engagement_score",
                0,
            )
        )
    except Exception:
        result["engagement_score"] = 0.0

    unsupported = result.get(
        "unsupported_claims",
        [],
    )

    material_unsupported = (
        len(unsupported) > 0
    )

    result["publish"] = (
        result["score"]
        >= MIN_QUALITY_SCORE
        and result["engagement_score"]
        >= MIN_ENGAGEMENT_SCORE
        and not material_unsupported
        and not html_issues
    )

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
    feedback = json.dumps(
        {
            "issues": quality_result.get(
                "issues",
                [],
            ),
            "unsupported_claims":
                quality_result.get(
                    "unsupported_claims",
                    [],
                ),
            "missing_value":
                quality_result.get(
                    "missing_value",
                    [],
                ),
            "style_issues":
                quality_result.get(
                    "style_issues",
                    [],
                ),
            "engagement_issues":
                quality_result.get(
                    "engagement_issues",
                    [],
                ),
            "seo_issues":
                quality_result.get(
                    "seo_issues",
                    [],
                ),
            "revision_instructions":
                quality_result.get(
                    "revision_instructions",
                    "",
                ),
        },
        ensure_ascii=False,
        indent=2,
    )

    return generate_article(
        topic_title,
        source_name,
        source_url,
        source_text,
        editorial_brief,
        revision_feedback=feedback,
        previous_article=article_html,
    )


# ---------------------------------------------------------------------------
# ARTICLE TEXT
# ---------------------------------------------------------------------------

def article_text(content):
    soup = BeautifulSoup(
        content or "",
        "html.parser",
    )

    return clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )


# ---------------------------------------------------------------------------
# AFFILIATE LINKS
# ---------------------------------------------------------------------------

def find_affiliate_match(
    text,
    aliases,
):
    lowered = text.lower()

    for alias in sorted(
        aliases,
        key=len,
        reverse=True,
    ):
        pattern = re.compile(
            r"\b"
            + re.escape(alias)
            + r"\b",
            re.I,
        )

        match = pattern.search(
            lowered
        )

        if match:
            return match

    return None


def inject_contextual_affiliate_links(
    content,
    editorial_brief,
):
    """
    Safely adds at most one affiliate link per configured tool.

    Only links a tool when the article actually discusses it.
    Existing anchors are not replaced.
    """

    if not content:
        return content

    soup = BeautifulSoup(
        content,
        "html.parser",
    )

    for tool, url in AFFILIATE_LINKS.items():
        if not url:
            continue

        aliases = AFFILIATE_ALIASES.get(
            tool,
            [tool],
        )

        # Check article text.
        plain_text = article_text(
            str(soup)
        )

        match = find_affiliate_match(
            plain_text,
            aliases,
        )

        if not match:
            continue

        # Do not inject another link if this tool
        # is already represented by an anchor.
        already_linked = False

        for anchor in soup.find_all("a"):
            anchor_text = clean_text(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            ).lower()

            for alias in aliases:
                if alias.lower() in anchor_text:
                    already_linked = True
                    break

            if already_linked:
                break

        if already_linked:
            continue

        # Safely inspect text nodes.
        injected = False

        for text_node in list(
            soup.find_all(
                string=True
            )
        ):
            if not isinstance(
                text_node,
                NavigableString,
            ):
                continue

            parent = text_node.parent

            if not parent:
                continue

            if parent.name == "a":
                continue

            node_text = str(
                text_node
            )

            node_match = (
                find_affiliate_match(
                    node_text,
                    aliases,
                )
            )

            if not node_match:
                continue

            start = node_match.start()
            end = node_match.end()

            before = node_text[:start]
            matched = node_text[
                start:end
            ]
            after = node_text[end:]

            fragment = []

            if before:
                fragment.append(
                    NavigableString(
                        before
                    )
                )

            anchor = soup.new_tag(
                "a",
                href=url,
            )

            anchor["rel"] = [
                "nofollow",
                "sponsored",
                "noopener",
            ]

            anchor.string = matched

            fragment.append(anchor)

            if after:
                fragment.append(
                    NavigableString(
                        after
                    )
                )

            # Replace the original node with
            # properly attached fragments.
            for item in reversed(
                fragment
            ):
                text_node.insert_after(
                    item
                )

            text_node.extract()

            injected = True
            break

        if injected:
            continue

    return str(soup)


# ---------------------------------------------------------------------------
# INTERNAL LINKS
# ---------------------------------------------------------------------------

def internal_link_relevance(
    new_article,
    candidate,
):
    new_text = (
        new_article.get(
            "primary_keyword",
            "",
        )
        + " "
        + " ".join(
            new_article.get(
                "secondary_keywords",
                [],
            )
        )
        + " "
        + new_article.get(
            "useful_angle",
            "",
        )
        + " "
        + new_article.get(
            "article_type",
            "",
        )
    )

    old_text = (
        candidate.get(
            "title",
            "",
        )
        + " "
        + candidate.get(
            "primary_keyword",
            "",
        )
        + " "
        + " ".join(
            candidate.get(
                "secondary_keywords",
                [],
            )
        )
        + " "
        + candidate.get(
            "useful_angle",
            "",
        )
        + " "
        + candidate.get(
            "article_type",
            "",
        )
    )

    new_tokens = keyword_tokens(
        new_text
    )

    old_tokens = keyword_tokens(
        old_text
    )

    if not new_tokens or not old_tokens:
        return 0.0

    overlap = len(
        new_tokens & old_tokens
    )

    union = len(
        new_tokens | old_tokens
    )

    score = (
        overlap / union
        if union
        else 0.0
    )

    # Extra title/keyword relevance bonus.
    primary = clean_text(
        new_article.get(
            "primary_keyword",
            "",
        )
    ).lower()

    candidate_text = clean_text(
        candidate.get(
            "title",
            "",
        )
        + " "
        + candidate.get(
            "primary_keyword",
            "",
        )
    ).lower()

    if primary and primary in candidate_text:
        score += 0.15

    return min(
        score,
        1.0,
    )


def inject_internal_links(
    content,
    posted_history,
    current_link,
    editorial_brief,
):
    candidates = []

    for post in posted_history:
        if not isinstance(
            post,
            dict,
        ):
            continue

        post_url = post.get(
            "post_url"
        )

        if not post_url:
            continue

        if post.get("link") == current_link:
            continue

        if not post.get("title"):
            continue

        candidates.append(post)

    if not candidates:
        return content

    scored = []

    for candidate in candidates:
        score = internal_link_relevance(
            editorial_brief,
            candidate,
        )

        scored.append(
            (
                score,
                candidate,
            )
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    picks = [
        candidate
        for score, candidate
        in scored[
            :INTERNAL_LINKS_PER_POST
        ]
        if score >= 0.08
    ]

    if not picks:
        return content

    links_html = ""

    for candidate in picks:
        safe_url = html.escape(
            candidate["post_url"],
            quote=True,
        )

        safe_title = html.escape(
            candidate["title"]
        )

        links_html += (
            f'<li><a href="{safe_url}" '
            f'rel="noopener">'
            f'{safe_title}'
            f'</a></li>'
        )

    return (
        content
        + "<h2>Related reading</h2>"
        + f"<ul>{links_html}</ul>"
    )


# ---------------------------------------------------------------------------
# SOURCE ATTRIBUTION
# ---------------------------------------------------------------------------

def append_source_attribution(
    content,
    source_name,
    source_url,
):
    if not source_url:
        return content

    escaped_name = html.escape(
        source_name
        or "the original source"
    )

    escaped_url = html.escape(
        source_url,
        quote=True,
    )

    attribution = (
        "<h2>Source</h2>"
        "<p>"
        "This article is based on information "
        "published by "
        f'<a href="{escaped_url}" '
        'rel="nofollow noopener">'
        f"{escaped_name}"
        "</a>."
        "</p>"
    )

    return (
        content
        + attribution
    )


# ---------------------------------------------------------------------------
# FINAL ENRICHMENT VALIDATION
# ---------------------------------------------------------------------------

def final_content_validation(
    content,
    source_url,
):
    issues = []

    soup = BeautifulSoup(
        content or "",
        "html.parser",
    )

    # No scripts.
    if soup.find(
        [
            "script",
            "iframe",
            "object",
            "embed",
        ]
    ):
        issues.append(
            "Unsafe HTML remains after enrichment."
        )

    # Check source link.
    if source_url:
        source_links = [
            a.get("href")
            for a in soup.find_all("a")
        ]

        if source_url not in source_links:
            issues.append(
                "Source attribution link missing."
            )

    # Check duplicate identical hrefs.
    hrefs = [
        (
            a.get("href") or ""
        ).strip()
        for a in soup.find_all("a")
    ]

    # Identical links are allowed when intentional,
    # but flag suspicious excessive repetition.
    for href in set(hrefs):
        if href and hrefs.count(href) > 4:
            issues.append(
                f"Excessive repeated link: {href}"
            )

    # No javascript/data links.
    for href in hrefs:
        if re.match(
            r"^(javascript|data|vbscript):",
            href,
            flags=re.I,
        ):
            issues.append(
                "Unsafe URL scheme detected."
            )

    return issues


# ---------------------------------------------------------------------------
# BLOGGER PUBLISH
# ---------------------------------------------------------------------------

def post_to_blogger(
    service,
    title,
    content,
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
        "",
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
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        return (
            data
            if isinstance(
                data,
                list,
            )
            else []
        )

    except Exception:
        return []


def save_posted_history(posted):
    with open(
        POSTED_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            posted[-500:],
            f,
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------------------------
# CANDIDATE PRE-FILTER
# ---------------------------------------------------------------------------

def build_candidate_pool(
    all_topics,
    posted_titles,
    posted_links,
):
    seen_titles = set()
    pool = []

    for topic in all_topics:
        title = clean_text(
            topic.get(
                "title",
                "",
            )
        )

        link = clean_text(
            topic.get(
                "link",
                "",
            )
        )

        if len(title) <= 15:
            continue

        if title in seen_titles:
            continue

        if link and link in posted_links:
            continue

        if is_obvious_duplicate(
            title,
            posted_titles,
        ):
            continue

        # Avoid obvious RSS junk.
        lowered = title.lower()

        junk_patterns = [
            "subscribe",
            "newsletter",
            "podcast episode",
            "weekly roundup",
            "job opening",
        ]

        if any(
            pattern in lowered
            for pattern in junk_patterns
        ):
            continue

        seen_titles.add(title)

        pool.append(topic)

        if len(pool) >= RAW_CANDIDATE_LIMIT:
            break

    return pool


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print(
        "AIToolNotes Intelligent Blog Automation v5 Starting..."
    )

    print(
        "Mode: RSS -> source -> editorial intelligence -> "
        "verified evidence -> writer -> quality gate -> "
        "revision -> enrichment -> Blogger"
    )

    posted = load_posted_history()

    posted_titles = {
        p.get("title")
        for p in posted
        if isinstance(p, dict)
        and p.get("title")
    }

    posted_links = {
        p.get("link")
        for p in posted
        if isinstance(p, dict)
        and p.get("link")
    }

    posted_titles.update(
        p
        for p in posted
        if isinstance(p, str)
    )

    service = get_blogger_service()

    all_topics = collect_topics()

    candidate_pool = build_candidate_pool(
        all_topics,
        posted_titles,
        posted_links,
    )

    print(
        f"\nCandidate pool: {len(candidate_pool)}"
    )

    # -----------------------------------------------------------------------
    # SOURCE VALIDATION + EDITORIAL INTELLIGENCE
    # -----------------------------------------------------------------------

    analyzed_candidates = []

    for index, topic_data in enumerate(
        candidate_pool[
            :MAX_EDITORIAL_CANDIDATES
        ],
        1,
    ):
        title = topic_data[
            "title"
        ]

        link = topic_data.get(
            "link",
            "",
        )

        published = topic_data.get(
            "published",
            "",
        )

        print(
            f"\nEvaluating "
            f"{index}/{min(len(candidate_pool), MAX_EDITORIAL_CANDIDATES)}:"
        )

        print(
            f"  {title[:110]}"
        )

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

        try:
            brief = analyze_story(
                title,
                topic_data[
                    "source"
                ],
                source_text,
                published,
            )

        except Exception as e:
            print(
                f"  SKIP: editorial analysis failed: {e}"
            )
            continue

        score = clamp_score(
            brief.get(
                "topic_score",
                0,
            )
        )

        verified_evidence = len(
            brief.get(
                "evidence_ledger",
                [],
            )
        )

        print(
            f"  Editorial score: "
            f"{score:.2f}/10"
        )

        print(
            f"  Decision: "
            f"{'PUBLISHABLE' if brief.get('publish_decision') else 'SKIP'}"
        )

        print(
            f"  Evidence verified: "
            f"{verified_evidence}"
        )

        print(
            f"  Type: "
            f"{brief.get('article_type', 'unknown')}"
        )

        print(
            f"  Intent: "
            f"{brief.get('search_intent', 'unknown')}"
        )

        if not brief.get(
            "publish_decision"
        ):
            print(
                "  Reason: "
                + brief.get(
                    "reason_if_rejected",
                    "Editorial gate.",
                )
            )
            continue

        analyzed_candidates.append(
            (
                score,
                topic_data,
                source_text,
                brief,
            )
        )

    # Highest deterministic editorial score first.
    analyzed_candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    usable_topics = analyzed_candidates[
        :MAX_POSTS_PER_RUN
    ]

    print(
        f"\nSelected {len(usable_topics)} article(s) "
        f"from {len(analyzed_candidates)} publishable candidate(s)."
    )

    published_this_run = 0

    # -----------------------------------------------------------------------
    # WRITE -> CHECK -> REVISE -> ENRICH -> PUBLISH
    # -----------------------------------------------------------------------

    for i, (
        topic_score,
        topic_data,
        source_text,
        brief,
    ) in enumerate(
        usable_topics,
        1,
    ):
        original_title = topic_data[
            "title"
        ]

        source = topic_data[
            "source"
        ]

        source_url = topic_data.get(
            "link",
            "",
        )

        published = topic_data.get(
            "published",
            "",
        )

        print(
            f"\nArticle {i}/{len(usable_topics)}: "
            f"{original_title[:100]}"
        )

        try:
            headline = choose_headline(
                brief,
                original_title,
            )

            print(
                f"  Headline: {headline}"
            )

            print(
                "  Writing evidence-constrained article..."
            )

            article = generate_article(
                headline,
                source,
                source_url,
                source_text,
                brief,
            )

            article, html_issues = (
                validate_and_clean_html(
                    article
                )
            )

            print(
                f"  Word count: "
                f"{count_words_from_html(article)}"
            )

            print(
                "  HTML check: "
                + (
                    "PASS"
                    if not html_issues
                    else "ISSUES FOUND"
                )
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

            score = clamp_score(
                quality.get(
                    "score",
                    0,
                )
            )

            engagement_score = clamp_score(
                quality.get(
                    "engagement_score",
                    0,
                )
            )

            publish = bool(
                quality.get(
                    "publish",
                    False,
                )
            )

            print(
                f"  Quality: {score:.2f}/10"
            )

            print(
                f"  Engagement: "
                f"{engagement_score:.2f}/10"
            )

            print(
                f"  Publish: {publish}"
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
                    print(
                        "  Revising article once..."
                    )

                    article = revise_article(
                        headline,
                        source,
                        source_url,
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
                        headline,
                        source,
                        source_url,
                        source_text,
                        brief,
                        article,
                        html_issues,
                    )

                    score = clamp_score(
                        quality.get(
                            "score",
                            0,
                        )
                    )

                    engagement_score = clamp_score(
                        quality.get(
                            "engagement_score",
                            0,
                        )
                    )

                    publish = bool(
                        quality.get(
                            "publish",
                            False,
                        )
                    )

                    print(
                        f"  Revised quality: "
                        f"{score:.2f}/10"
                    )

                    print(
                        f"  Revised engagement: "
                        f"{engagement_score:.2f}/10"
                    )

                    print(
                        f"  Revised publish: "
                        f"{publish}"
                    )

            # ---------------------------------------------------------------
            # FINAL QUALITY GATE
            # ---------------------------------------------------------------

            if (
                not publish
                or score < MIN_QUALITY_SCORE
                or engagement_score < MIN_ENGAGEMENT_SCORE
                or html_issues
            ):
                print(
                    "  NOT PUBLISHED. "
                    "Article failed publication gate."
                )

                unsupported = quality.get(
                    "unsupported_claims",
                    [],
                )

                if unsupported:
                    print(
                        "  Unsupported claims: "
                        f"{len(unsupported)}"
                    )

                continue

            # ---------------------------------------------------------------
            # POST-VALIDATION ENRICHMENT
            # ---------------------------------------------------------------

            article = (
                inject_contextual_affiliate_links(
                    article,
                    brief,
                )
            )

            article = (
                inject_internal_links(
                    article,
                    posted,
                    source_url,
                    brief,
                )
            )

            article = (
                append_source_attribution(
                    article,
                    source,
                    source_url,
                )
            )

            article, final_html_issues = (
                validate_and_clean_html(
                    article
                )
            )

            final_content_issues = (
                final_content_validation(
                    article,
                    source_url,
                )
            )

            final_issues = (
                final_html_issues
                + final_content_issues
            )

            if final_issues:
                print(
                    "  NOT PUBLISHED. "
                    "Final validation failed:"
                )

                for issue in final_issues:
                    print(
                        f"   - {issue}"
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

            now = datetime.now(
                timezone.utc
            ).isoformat()

            posted.append({
                "title": headline,
                "original_title": original_title,
                "link": source_url,
                "post_url": post_url,
                "source": source,
                "published": published,
                "published_at": now,

                "quality_score": score,
                "engagement_score":
                    engagement_score,

                "editorial_score":
                    topic_score,

                "article_type":
                    brief.get(
                        "article_type",
                        "",
                    ),

                "search_intent":
                    brief.get(
                        "search_intent",
                        "",
                    ),

                "primary_keyword":
                    brief.get(
                        "primary_keyword",
                        "",
                    ),

                "secondary_keywords":
                    brief.get(
                        "secondary_keywords",
                        [],
                    ),

                "commercial_intent":
                    brief.get(
                        "commercial_intent",
                        "",
                    ),

                "evergreen_potential":
                    brief.get(
                        "evergreen_potential",
                        0,
                    ),

                "useful_angle":
                    brief.get(
                        "useful_angle",
                        "",
                    ),

                "content_gap":
                    brief.get(
                        "content_gap",
                        "",
                    ),

                "reader_questions":
                    brief.get(
                        "reader_questions",
                        [],
                    ),

                "hook_strategy":
                    brief.get(
                        "hook_strategy",
                        "",
                    ),

                "evidence_facts":
                    len(
                        brief.get(
                            "evidence_ledger",
                            [],
                        )
                    ),
            })

            posted = posted[-500:]

            save_posted_history(
                posted
            )

            posted_titles.add(
                headline
            )

            posted_links.add(
                source_url
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
````
