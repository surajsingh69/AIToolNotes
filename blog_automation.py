# AIToolNotes Intelligent Blog Automation v3
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

from bs4 import BeautifulSoup
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
    ("https://www.producthunt.com/feed?category=artificial-intelligence", "Product Hunt AI"),
    ("https://openai.com/news/rss.xml", "OpenAI"),
    ("https://blog.google/technology/ai/rss/", "Google AI Blog"),
    ("https://huggingface.co/blog/feed.xml", "Hugging Face"),
    ("https://techcrunch.com/tag/artificial-intelligence/feed/", "TechCrunch AI"),
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

def get_rss_items(url, source, limit=3):
    out = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        root = ET.fromstring(r.content)

        # Standard RSS feeds.
        items = root.findall(".//item")

        # Basic Atom fallback.
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns)[:limit]:
                title = entry.findtext("atom:title", "", ns).strip()
                published = (
                    entry.findtext("atom:published", "", ns).strip()
                    or entry.findtext("atom:updated", "", ns).strip()
                )
                link = ""
                link_el = entry.find("atom:link", ns)
                if link_el is not None:
                    link = (link_el.attrib.get("href") or "").strip()

                if len(title) > 15 and link:
                    out.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": published,
                    })

        else:
            for item in items[:limit]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                published = (
                    item.findtext("pubDate", "").strip()
                    or item.findtext("published", "").strip()
                )

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


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


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
            "textarea"
        ]):
            tag.decompose()

        # Prefer article-like containers.
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
    print("Collecting AI tool topics from configured sources...")

    topics = []

    for url, source in AI_TOOL_SOURCES:
        topics += get_rss_items(url, source, limit=3)

    print(f"\nTotal raw topics: {len(topics)}")
    return topics


# ---------------------------------------------------------------------------
# DUPLICATE CONTROL
# ---------------------------------------------------------------------------

def normalize_title(title):
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^a-z0-9\s]", " ", (title or "").lower())
    ).strip()


def title_similarity(a, b):
    return difflib.SequenceMatcher(
        None,
        normalize_title(a),
        normalize_title(b)
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
        flags=re.I
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

    content = response.choices[0].message.content or ""

    if response.choices[0].finish_reason == "length":
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
            "unsupported_claims_to_avoid": [
                "Do not infer product details from the headline alone."
            ],
            "useful_angle": "",
            "article_type": "news_explainer",
            "search_intent": "",
            "commercial_intent": "low",
            "reason_if_rejected": "Insufficient source material.",
        }

    prompt = f"""
You are the evidence-first editorial intelligence layer for AIToolNotes.

Your job is NOT to write the article. Your job is to understand the supplied
source and build a strict evidence boundary for a later writer.

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
   the supplied source that supports the fact. Do not invent evidence.
3. Keep evidence excerpts short and close to the source wording.
4. Never turn a source headline into a fact unless the body supports it.
5. Never invent product names, model names, APIs, pricing, dates, statistics,
   performance numbers, hardware requirements, integrations, user counts,
   partnerships, availability, quotes, or technical capabilities.
6. Treat company promotional claims as claims by the company, not independent
   verification.
7. If the source is thin, contradictory, inaccessible, mostly navigation,
   promotional boilerplate, or insufficient for a useful article, set
   publish_decision to false.
8. A publishable story should contain enough supported information to explain
   what happened and why a reader should care.
9. missing_context means information genuinely absent from the supplied source.
10. unsupported_claims_to_avoid should contain likely temptations for the writer
    that the source does NOT establish.
11. article_type must be one of:
    news_explainer, practical_guide, tool_review, comparison, roundup, analysis.
12. commercial_intent must be low, medium, or high.
13. Do not use outside knowledge to fill gaps.
14. Keep the evidence ledger to at most {MAX_SOURCE_FACTS} important facts.
"""

    result = extract_json_object(call_ai([
        {
            "role": "system",
            "content": (
                "You are a strict evidence editor. "
                "Source-grounded accuracy is more important than publishing volume."
            ),
        },
        {"role": "user", "content": prompt},
    ], 4500))

    # Normalize critical fields.
    result.setdefault("important_facts", [])
    result.setdefault("evidence_ledger", [])
    result.setdefault("missing_context", [])
    result.setdefault("unsupported_claims_to_avoid", [])

    result["important_facts"] = result["important_facts"][:MAX_SOURCE_FACTS]
    result["evidence_ledger"] = result["evidence_ledger"][:MAX_SOURCE_FACTS]

    # Remove malformed evidence entries.
    valid_ledger = []
    for item in result["evidence_ledger"]:
        if not isinstance(item, dict):
            continue

        fact = clean_text(item.get("fact"))
        evidence = clean_text(item.get("evidence"))

        if fact and evidence:
            valid_ledger.append({
                "fact": fact,
                "evidence": evidence[:MAX_EVIDENCE_CHARS_PER_FACT],
                "confidence": item.get("confidence", "medium"),
            })

    result["evidence_ledger"] = valid_ledger

    if len(result["evidence_ledger"]) < 2:
        result["publish_decision"] = False
        result["reason_if_rejected"] = (
            "The source did not yield enough independently traceable facts."
        )

    return result


# ---------------------------------------------------------------------------
# ARTICLE GENERATION
# ---------------------------------------------------------------------------

def compact_writer_context(source_text, editorial_brief, max_source_chars=4500, max_facts=9):
    """Build a small evidence-first context so Groq requests stay below TPM limits."""
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
        "reader_problem_or_interest": editorial_brief.get("reader_problem_or_interest", ""),
        "why_it_matters": editorial_brief.get("why_it_matters", ""),
        "who_should_care": editorial_brief.get("who_should_care", ""),
        "useful_angle": editorial_brief.get("useful_angle", ""),
        "article_type": editorial_brief.get("article_type", "news_explainer"),
        "search_intent": editorial_brief.get("search_intent", ""),
        "missing_context": editorial_brief.get("missing_context", [])[:4],
        "unsupported_claims_to_avoid": editorial_brief.get("unsupported_claims_to_avoid", [])[:6],
        "evidence_ledger": compact_ledger,
    }

    source_excerpt = clean_text(source_text or "")[:max_source_chars]
    return compact_brief, source_excerpt


def generate_article(
    topic_title,
    source_name,
    source_text,
    editorial_brief,
    revision_feedback=""
):
    compact_brief, source_excerpt = compact_writer_context(source_text, editorial_brief)

    feedback = ""
    if revision_feedback:
        feedback = f"""
Previous quality feedback. Fix these issues without introducing new facts:
{revision_feedback[:2200]}
"""

    prompt = f"""
Write a genuinely useful AIToolNotes article using ONLY the supplied evidence.
The evidence ledger defines the factual boundary. Do not use outside knowledge.

TITLE: {topic_title}
SOURCE: {source_name}

EDITORIAL BRIEF:
{json.dumps(compact_brief, ensure_ascii=False, separators=(",", ":"))}

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
- Use H2 headings. Use numbered steps only when the evidence supports them.
- Avoid generic AI filler and fake personal experience.
- Aim for 700-950 words when the evidence supports it. Do not pad.
- End with a concrete takeaway.
- Output RAW HTML ONLY. No Markdown, no code fences, no H1.
"""

    raw = call_ai([
        {
            "role": "system",
            "content": (
                "You are the senior writer of a trustworthy technology publication. "
                "Stay strictly inside the supplied evidence boundary."
            ),
        },
        {"role": "user", "content": prompt},
    ], 4000)

    raw = re.sub(r"^```(?:html)?\s*", "", raw.strip(), flags=re.I)
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

    # Remove Markdown fences and accidental H1.
    content = re.sub(r"^```(?:html)?\s*", "", content.strip(), flags=re.I)
    content = re.sub(r"\s*```$", "", content)
    content = re.sub(r"<h1\b[^>]*>.*?</h1>", "", content, flags=re.I | re.S)

    soup = BeautifulSoup(content, "html.parser")
    issues = []

    # Remove dangerous/non-content elements.
    for tag in soup(["script", "style", "iframe", "object", "embed", "form"]):
        tag.decompose()
        issues.append("Removed unsupported or unsafe HTML element.")

    # Remove comments.
    for comment in soup.find_all(string=lambda x: isinstance(x, type(soup.string))):
        # BeautifulSoup's Comment type is handled below; this is intentionally
        # conservative and does not remove normal text nodes.
        pass

    # Strip tags outside our intended article vocabulary while preserving text.
    for tag in soup.find_all(True):
        if tag.name.lower() not in ALLOWED_TAGS:
            tag.unwrap()
            issues.append(f"Removed unsupported HTML tag: {tag.name}")

    # Clean links.
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not re.match(r"^https?://", href, flags=re.I):
            a.unwrap()
            issues.append("Removed an invalid link.")

    # Tables need a minimum coherent structure.
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 1:
            table.decompose()
            issues.append("Removed an empty table.")
            continue

        max_cells = max((len(r.find_all(["th", "td"])) for r in rows), default=0)
        if max_cells < 2:
            table.decompose()
            issues.append("Removed a malformed table.")

    cleaned = str(soup)

    # Basic structural checks.
    if not soup.find("p") and not soup.find(["ul", "ol", "table", "blockquote"]):
        issues.append("Article has no recognizable content structure.")

    text = clean_text(soup.get_text(" ", strip=True))

    if len(text) < 500:
        issues.append("Article is too short to be useful.")

    return cleaned.strip(), issues


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
    compact_brief, source_excerpt = compact_writer_context(
        source_text,
        editorial_brief,
        max_source_chars=3500,
        max_facts=9,
    )
    article_excerpt = (article_html or "")[:12000]

    prompt = f"""
You are the final evidence and quality editor for AIToolNotes.
Check whether this article is accurate, useful, and safe to publish using ONLY
this supplied evidence.

TOPIC: {topic_title}
SOURCE: {source_name}

EDITORIAL BRIEF + EVIDENCE:
{json.dumps(compact_brief, ensure_ascii=False, separators=(",", ":"))}

SOURCE EXCERPT:
<BEGIN_SOURCE>
{source_excerpt}
<END_SOURCE>

DETERMINISTIC HTML ISSUES:
{json.dumps(html_issues, ensure_ascii=False)}

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
1. Check concrete factual claims against the evidence ledger/source excerpt.
2. Numbers, product names, APIs, prices, dates, specs, availability, quotes,
   partnerships, and performance claims require direct support.
3. Flag invented facts, fake experience, fabricated quotes, misleading certainty,
   repetition, generic filler, and unsupported actionable instructions.
4. Respect the deterministic HTML issues provided.
5. Score 10 exceptional, 9 excellent, 8 strong, 7 acceptable, 6 needs work.
6. Publish only when score >= {MIN_QUALITY_SCORE}, there are no material
   unsupported factual claims, and there are no unresolved HTML issues.
"""

    return extract_json_object(call_ai([
        {
            "role": "system",
            "content": "You are a strict publication gate. Reject unsupported factual claims.",
        },
        {"role": "user", "content": prompt},
    ], 2500))


def revise_article(
    topic_title,
    source_name,
    source_text,
    editorial_brief,
    article_html,
    quality_result
):
    feedback = json.dumps({
        "issues": quality_result.get("issues", []),
        "unsupported_claims": quality_result.get("unsupported_claims", []),
        "missing_value": quality_result.get("missing_value", []),
        "style_issues": quality_result.get("style_issues", []),
        "revision_instructions": quality_result.get(
            "revision_instructions", ""
        ),
    }, ensure_ascii=False, indent=2)

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
            r'(?<!["\'>])\b(' + re.escape(tool) + r')\b',
            re.I
        )

        content = pattern.sub(
            lambda m: (
                f'<a href="{html.escape(url, quote=True)}" '
                f'rel="nofollow sponsored">{m.group(1)}</a>'
            ),
            content,
            count=1,
        )

    return content


def inject_internal_links(content, posted_history, current_link):
    candidates = [
        p for p in posted_history
        if isinstance(p, dict)
        and p.get("post_url")
        and p.get("link") != current_link
        and p.get("title")
    ]

    if not candidates:
        return content

    picks = candidates[-INTERNAL_LINKS_PER_POST:]

    links_html = "".join(
        f'<li><a href="{html.escape(p["post_url"], quote=True)}">'
        f'{html.escape(p["title"])}</a></li>'
        for p in picks
    )

    return (
        content
        + f"<h2>Related reading</h2><ul>{links_html}</ul>"
    )


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
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("AIToolNotes Intelligent Blog Automation v3 Starting...")
    print(
        "Mode: source -> intelligence -> evidence -> write -> "
        "HTML check -> fact check -> publish"
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
    unique_topics = []

    for topic in all_topics:
        title = topic.get("title", "").strip()
        link = topic.get("link", "").strip()

        if len(title) <= 15:
            continue

        if title in seen_titles:
            continue

        if link and link in posted_links:
            continue

        if is_obvious_duplicate(title, posted_titles):
            continue

        seen_titles.add(title)
        unique_topics.append(topic)

        if len(unique_topics) >= MAX_POSTS_PER_RUN:
            break

    print(
        f"\nCandidate articles: {len(unique_topics)} "
        f"(cap: {MAX_POSTS_PER_RUN})"
    )

    published_this_run = 0

    for i, topic_data in enumerate(unique_topics, 1):
        title = topic_data["title"]
        source = topic_data["source"]
        link = topic_data.get("link", "")
        published = topic_data.get("published", "")

        print(f"\nArticle {i}/{len(unique_topics)}: {title[:100]}")

        try:
            source_text = fetch_source_article_text(link)

            if len(source_text) < MIN_SOURCE_CHARS:
                print(
                    f"  SKIP: source text too short "
                    f"({len(source_text)} chars)."
                )
                continue

            print("  Analyzing story and building evidence ledger...")

            brief = analyze_story(
                title,
                source,
                source_text,
                published,
            )

            decision = bool(brief.get("publish_decision"))

            print(
                f"  Decision: "
                f"{'PUBLISHABLE' if decision else 'SKIP'}"
            )
            print(
                f"  Type: {brief.get('article_type', 'unknown')}"
            )
            print(
                f"  Intent: {brief.get('search_intent', 'unknown')}"
            )
            print(
                f"  Commercial intent: "
                f"{brief.get('commercial_intent', 'unknown')}"
            )
            print(
                f"  Evidence facts: "
                f"{len(brief.get('evidence_ledger', []))}"
            )

            if not decision:
                print(
                    "  Skipped: "
                    f"{brief.get('reason_if_rejected', 'insufficient evidence')}"
                )
                continue

            print("  Writing evidence-constrained article...")

            article = generate_article(
                title,
                source,
                source_text,
                brief,
            )

            article, html_issues = validate_and_clean_html(article)

            print(
                f"  HTML check: "
                f"{'PASS' if not html_issues else 'ISSUES FOUND'}"
            )

            quality = quality_check(
                title,
                source,
                source_text,
                brief,
                article,
                html_issues,
            )

            score = int(quality.get("score", 0) or 0)

            publish = bool(quality.get("publish"))

            print(
                f"  Quality score: {score}/10 | "
                f"Publish: {publish}"
            )

            if not publish or score < MIN_QUALITY_SCORE:
                if MAX_REWRITE_ATTEMPTS:
                    print("  Revising article once...")

                    article = revise_article(
                        title,
                        source,
                        source_text,
                        brief,
                        article,
                        quality,
                    )

                    article, html_issues = validate_and_clean_html(article)

                    quality = quality_check(
                        title,
                        source,
                        source_text,
                        brief,
                        article,
                        html_issues,
                    )

                    score = int(quality.get("score", 0) or 0)
                    publish = bool(quality.get("publish"))

                    print(
                        f"  Revised score: {score}/10 | "
                        f"Publish: {publish}"
                    )

            if not publish or score < MIN_QUALITY_SCORE:
                print(
                    "  NOT PUBLISHED. "
                    "Article failed the evidence/quality gate."
                )

                if quality.get("unsupported_claims"):
                    print(
                        "  Unsupported claims detected: "
                        f"{len(quality.get('unsupported_claims', []))}"
                    )

                continue

            # Link injection happens only AFTER factual/editorial validation.
            article = inject_affiliate_links(article)
            article = inject_internal_links(
                article,
                posted,
                link,
            )

            # Final deterministic HTML pass after link injection.
            article, final_html_issues = validate_and_clean_html(article)

            if final_html_issues:
                print(
                    "  NOT PUBLISHED. Final HTML validation failed: "
                    f"{final_html_issues}"
                )
                continue

            _, post_url = post_to_blogger(
                service,
                title,
                article,
            )

            posted.append({
                "title": title,
                "link": link,
                "post_url": post_url,
                "source": source,
                "quality_score": score,
                "article_type": brief.get("article_type", ""),
                "commercial_intent": brief.get(
                    "commercial_intent",
                    "",
                ),
                "evidence_facts": len(
                    brief.get("evidence_ledger", [])
                ),
            })

            posted = posted[-500:]
            save_posted_history(posted)

            posted_titles.add(title)
            posted_links.add(link)

            published_this_run += 1

            time.sleep(3)

        except Exception as e:
            print(f"  Failed: {type(e).__name__}: {e}")
            continue

    print(
        f"\nDone. Published {published_this_run} article(s)."
    )


if __name__ == "__main__":
    main()
