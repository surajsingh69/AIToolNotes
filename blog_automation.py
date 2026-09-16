# AIToolNotes Intelligent Blog Automation v2
# RSS -> source extraction -> intelligence -> writer -> quality check -> Blogger
import os, json, requests, time, re, difflib
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from groq import Groq
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
BLOG_ID = os.environ["BLOG_ID"]
SCOPES = ["https://www.googleapis.com/auth/blogger"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTED_FILE = os.path.join(BASE_DIR, "posted_titles.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")
MAX_POSTS_PER_RUN = 2
INTERNAL_LINKS_PER_POST = 2
SOURCE_MAX_CHARS = 12000
MIN_QUALITY_SCORE = 7
MAX_REWRITE_ATTEMPTS = 1

AFFILIATE_LINKS = {
    "notion": "", "jasper": "", "murf": "", "synthesia": "", "customgpt": "",
}
client = Groq(api_key=GROQ_API_KEY)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"}


def get_blogger_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("blogger", "v3", credentials=creds)


AI_TOOL_SOURCES = [
    ("https://www.producthunt.com/feed?category=artificial-intelligence", "Product Hunt AI"),
    ("https://openai.com/news/rss.xml", "OpenAI"),
    ("https://blog.google/technology/ai/rss/", "Google AI Blog"),
    ("https://huggingface.co/blog/feed.xml", "Hugging Face"),
    ("https://techcrunch.com/tag/artificial-intelligence/feed/", "TechCrunch AI"),
]


def get_rss_items(url, source, limit=3):
    out = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            published = item.findtext("pubDate", "").strip()
            if len(title) > 15 and link:
                out.append({"title": title, "link": link, "source": source, "published": published})
        print(f"  Got {len(out)} from {source}")
    except Exception as e:
        print(f"  {source} RSS failed: {e}")
    return out


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def fetch_source_article_text(url, max_chars=SOURCE_MAX_CHARS):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"]):
            tag.decompose()
        container = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body
        if not container:
            return ""
        for tag in container.find_all(["button", "input", "select", "textarea"]):
            tag.decompose()
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


def normalize_title(title):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (title or "").lower())).strip()


def title_similarity(a, b):
    return difflib.SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def is_obvious_duplicate(title, existing_titles, threshold=0.88):
    n = normalize_title(title)
    for old in existing_titles:
        if n and n == normalize_title(old):
            return True
        if title_similarity(title, old) >= threshold:
            return True
    return False


def extract_json_object(text):
    if not text:
        raise ValueError("Empty AI response")
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in AI response")
    return json.loads(cleaned[start:end + 1])


def call_ai(messages, max_tokens):
    response = client.chat.completions.create(model="openai/gpt-oss-120b", max_tokens=max_tokens, messages=messages)
    content = response.choices[0].message.content or ""
    if response.choices[0].finish_reason == "length":
        print("  WARNING: AI response reached token limit")
    return content.strip()


def analyze_story(topic_title, source_name, source_text, published=""):
    grounding = source_text or "(No source body was available. Do not invent details.)"
    prompt = f'''You are the editorial intelligence layer for AIToolNotes, a practical AI-tools and technology publication.
Your job is NOT to write the article. Understand the source and decide whether enough reliable information exists for a genuinely useful article.

SOURCE: {source_name}
TITLE: {topic_title}
PUBLISHED DATE: {published or "unknown"}
SOURCE TEXT:
"""{grounding}"""

Return ONLY valid JSON with these exact keys:
{{
  "publish_decision": true,
  "story_summary": "",
  "important_facts": [],
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
1. Base factual claims on the supplied source.
2. Never invent pricing, features, release dates, performance numbers, integrations, user counts, or capabilities.
3. If the source is too thin, unclear, broken, or lacks enough information for a useful article, set publish_decision to false.
4. Prefer a useful reader problem/decision over generic AI news.
5. Identify what information a reader actually needs.
6. Practical articles should have a practical angle.
7. Do not treat promotional claims as independently verified facts.
8. commercial_intent must be low, medium, or high.
9. article_type must be one of: news_explainer, practical_guide, tool_review, comparison, roundup, analysis.'''
    return extract_json_object(call_ai([
        {"role": "system", "content": "You are a careful editorial researcher. Accuracy and usefulness come before publishing volume."},
        {"role": "user", "content": prompt}
    ], 3000))


def generate_article(topic_title, source_name, source_text, editorial_brief, revision_feedback=""):
    grounding = source_text or "(No source body was available. Stay strictly within the brief.)"
    feedback = f"A previous quality check found these issues. Fix all of them:\n{revision_feedback}" if revision_feedback else ""
    prompt = f'''Write a genuinely useful AIToolNotes article based on the editorial brief below.

This is not a generic SEO article and not a rewrite of the source. Write for a real person who came to the page because they want an answer, practical solution, or help deciding whether an AI tool/development matters.

EDITORIAL BRIEF:
{json.dumps(editorial_brief, ensure_ascii=False, indent=2)}

SOURCE: {source_name}
SOURCE TEXT:
"""{grounding}"""

{feedback}

Requirements:
- Aim for 900-1200 words when the topic supports it. Do not pad.
- The first sentence should immediately tell the reader what matters.
- Do not start with or repeat the title.
- Use useful H2 headings and H3 only when helpful.
- Explain unfamiliar terms plainly.
- Give concrete examples where supported.
- Clearly separate confirmed facts from interpretation.
- Include limitations/caveats when relevant.
- Never invent features, prices, benchmarks, dates, statistics, quotes, integrations, or user reactions.
- Never claim personal testing or experience unless the supplied information documents it.
- Avoid repetitive AI filler such as "in today's rapidly evolving world", "game-changer", "revolutionary", "unlock the power", and "seamlessly" unless genuinely necessary.
- For practical guides, use numbered steps.
- For comparisons, explain which use case each option fits rather than declaring a universal winner.
- For news/explainers, explain what changed and why it matters.
- End with a specific practical takeaway.
- Output RAW HTML ONLY. No markdown fences. No H1.'''
    raw = call_ai([
        {"role": "system", "content": "You are the senior writer for a useful, trustworthy technology publication. Write naturally and precisely."},
        {"role": "user", "content": prompt}
    ], 6500)
    raw = re.sub(r"^```(?:html)?\s*", "", raw.strip(), flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def quality_check(topic_title, source_name, source_text, editorial_brief, article_html):
    prompt = f'''You are the final quality editor for AIToolNotes. Evaluate the article BEFORE publication.

ORIGINAL TOPIC: {topic_title}
SOURCE: {source_name}
EDITORIAL BRIEF:
{json.dumps(editorial_brief, ensure_ascii=False, indent=2)}
SOURCE TEXT:
"""{source_text or "(not available)"}"""
ARTICLE HTML:
"""{article_html}"""

Return ONLY valid JSON:
{{
  "publish": true,
  "score": 8,
  "issues": [],
  "unsupported_claims": [],
  "missing_value": [],
  "style_issues": [],
  "revision_instructions": ""
}}

Score 10 exceptional, 9 excellent, 8 strong, 7 publishable, 6 needs revision, 5 or below substantial revision.
Set publish=true only when score >= 7.
Flag invented/unsupported facts, generic filler, source rewriting, misleading claims, missing explanation, repetition, fake experience, weak HTML, or failure to solve the reader's likely problem.'''
    return extract_json_object(call_ai([
        {"role": "system", "content": "You are a strict but practical final editor. Protect readers from inaccurate or empty content."},
        {"role": "user", "content": prompt}
    ], 2500))


def revise_article(topic_title, source_name, source_text, editorial_brief, article_html, quality_result):
    feedback = json.dumps({
        "issues": quality_result.get("issues", []),
        "unsupported_claims": quality_result.get("unsupported_claims", []),
        "missing_value": quality_result.get("missing_value", []),
        "style_issues": quality_result.get("style_issues", []),
        "revision_instructions": quality_result.get("revision_instructions", "")
    }, ensure_ascii=False, indent=2)
    return generate_article(topic_title, source_name, source_text, editorial_brief, feedback)


def inject_affiliate_links(content):
    for tool, url in AFFILIATE_LINKS.items():
        if not url:
            continue
        pattern = re.compile(r'(?<!["\'>])\b(' + re.escape(tool) + r')\b', re.I)
        content = pattern.sub(lambda m: f'<a href="{url}" rel="nofollow sponsored">{m.group(1)}</a>', content, count=1)
    return content


def inject_internal_links(content, posted_history, current_link):
    candidates = [p for p in posted_history if isinstance(p, dict) and p.get("post_url") and p.get("link") != current_link]
    if not candidates:
        return content
    picks = candidates[-INTERNAL_LINKS_PER_POST:]
    links_html = "".join(f'<li><a href="{p["post_url"]}">{p["title"]}</a></li>' for p in picks)
    return content + f"<h2>Related reading</h2><ul>{links_html}</ul>"


def post_to_blogger(service, title, content):
    result = service.posts().insert(blogId=BLOG_ID, body={"kind": "blogger#post", "title": title, "content": content}, isDraft=False).execute()
    url = result.get("url", "")
    print(f"  Posted to Blogger: {url}")
    return result, url


def main():
    print("AIToolNotes Intelligent Blog Automation Starting...")
    print("Mode: understand -> write -> quality check -> publish")
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            posted = json.load(f)
    except Exception:
        posted = []

    posted_titles = {p.get("title") for p in posted if isinstance(p, dict) and p.get("title")}
    posted_links = {p.get("link") for p in posted if isinstance(p, dict) and p.get("link")}
    posted_titles.update(p for p in posted if isinstance(p, str))

    service = get_blogger_service()
    all_topics = collect_topics()
    seen_titles, unique_topics = set(), []

    for topic in all_topics:
        title, link = topic.get("title", "").strip(), topic.get("link", "").strip()
        if len(title) <= 15 or title in seen_titles or (link and link in posted_links) or is_obvious_duplicate(title, posted_titles):
            continue
        seen_titles.add(title)
        unique_topics.append(topic)
        if len(unique_topics) >= MAX_POSTS_PER_RUN:
            break

    print(f"\nCandidate articles: {len(unique_topics)} (cap: {MAX_POSTS_PER_RUN})")
    published_this_run = 0

    for i, topic_data in enumerate(unique_topics, 1):
        title = topic_data["title"]
        source = topic_data["source"]
        link = topic_data.get("link", "")
        published = topic_data.get("published", "")
        print(f"\nArticle {i}/{len(unique_topics)}: {title[:80]}")
        try:
            source_text = fetch_source_article_text(link) if link else ""
            print("  Analyzing story...")
            brief = analyze_story(title, source, source_text, published)
            print(f"  Decision: {'PUBLISHABLE' if brief.get('publish_decision') else 'SKIP'}")
            print(f"  Type: {brief.get('article_type', 'unknown')}")
            print(f"  Intent: {brief.get('search_intent', 'unknown')}")
            print(f"  Commercial intent: {brief.get('commercial_intent', 'unknown')}")
            if not brief.get("publish_decision", False):
                print(f"  Skipped: {brief.get('reason_if_rejected', 'insufficient value')}")
                continue

            print("  Writing useful article...")
            article = generate_article(title, source, source_text, brief)
            quality = quality_check(title, source, source_text, brief, article)
            score = int(quality.get("score", 0) or 0)
            print(f"  Quality score: {score}/10 | Publish: {quality.get('publish', False)}")

            if not quality.get("publish", False) or score < MIN_QUALITY_SCORE:
                if MAX_REWRITE_ATTEMPTS:
                    print("  Revising article once...")
                    article = revise_article(title, source, source_text, brief, article, quality)
                    quality = quality_check(title, source, source_text, brief, article)
                    score = int(quality.get("score", 0) or 0)
                    print(f"  Revised score: {score}/10 | Publish: {quality.get('publish', False)}")

            if not quality.get("publish", False) or score < MIN_QUALITY_SCORE:
                print("  NOT PUBLISHED. Article failed the quality threshold.")
                continue

            article = inject_affiliate_links(article)
            article = inject_internal_links(article, posted, link)
            _, post_url = post_to_blogger(service, title, article)
            posted.append({
                "title": title, "link": link, "post_url": post_url, "source": source,
                "quality_score": score, "article_type": brief.get("article_type", ""),
                "commercial_intent": brief.get("commercial_intent", "")
            })
            posted = posted[-500:]
            with open(POSTED_FILE, "w", encoding="utf-8") as f:
                json.dump(posted, f, ensure_ascii=False, indent=2)
            posted_titles.add(title)
            published_this_run += 1
            time.sleep(3)
        except Exception as e:
            print(f"  Failed: {e}")
            continue

    print(f"\nDone. Published {published_this_run} article(s).")


if __name__ == "__main__":
    main()
