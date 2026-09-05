import os, json, requests, time, re
from bs4 import BeautifulSoup
from groq import Groq
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import xml.etree.ElementTree as ET

# === CONFIGURATION ===
# SECURITY: secrets now come from environment variables, never hardcoded.
# Set these as GitHub Actions "Secrets" (Settings -> Secrets and variables -> Actions).
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
BLOG_ID      = os.environ["BLOG_ID"]
SCOPES       = ["https://www.googleapis.com/auth/blogger"]

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
POSTED_FILE = os.path.join(BASE_DIR, "posted_titles.json")
TOKEN_FILE  = os.path.join(BASE_DIR, "token.json")
CREDS_FILE  = os.path.join(BASE_DIR, "credentials.json")

# How many articles to publish per run. Kept deliberately low & original
# rather than high-volume — see note on Google's "scaled content abuse"
# policy in the README. Quality/day matters more than quantity/day.
MAX_POSTS_PER_RUN = 2

client = Groq(api_key=GROQ_API_KEY)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# === GOOGLE AUTH ===
def get_blogger_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # NOTE: run_local_server only works on your own machine, once,
            # to generate token.json the first time. After that, token.json
            # (stored as a GitHub Secret) is reused headlessly in CI — see README.
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("blogger", "v3", credentials=creds)

# === SOURCE FEEDS: real AI/tool release & product sources, not general news ===
# These are primary sources about AI tools themselves (release notes, launches,
# product blogs) — good raw material for genuinely original tutorials/comparisons,
# unlike generic news headlines which give the LLM nothing to actually report on.
AI_TOOL_SOURCES = [
    ("https://www.producthunt.com/feed?category=artificial-intelligence", "Product Hunt AI"),
    ("https://openai.com/news/rss.xml", "OpenAI"),
    ("https://blog.google/technology/ai/rss/", "Google AI Blog"),
    ("https://huggingface.co/blog/feed.xml", "Hugging Face"),
    ("https://techcrunch.com/tag/artificial-intelligence/feed/", "TechCrunch AI"),
]

def get_rss_items(url, source, limit=3):
    items_out = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        root = ET.fromstring(r.content)
        items = root.findall('.//item')[:limit]
        for item in items:
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            if len(title) > 15 and link:
                items_out.append({"title": title, "link": link, "source": source})
        print(f"  Got {len(items_out)} from {source}")
    except Exception as e:
        print(f"  {source} RSS failed: {e}")
    return items_out

def fetch_source_article_text(url, max_chars=6000):
    """Actually fetch and read the source page, not just its headline.
    This is what lets the LLM write something with real substance instead
    of hallucinating details around a title it's never seen the body of."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        text = re.sub(r'\s+', ' ', soup.get_text()).strip()
        return text[:max_chars]
    except Exception as e:
        print(f"  Could not fetch source body: {e}")
        return ""

def collect_topics():
    print("Collecting AI tool topics from primary sources...")
    topics = []
    for url, source in AI_TOOL_SOURCES:
        topics += get_rss_items(url, source, limit=3)
    print(f"\nTotal raw topics: {len(topics)}")
    return topics

# === GENERATE ARTICLE (tutorial/comparison style, grounded in real source text) ===
def generate_article(topic_title, source_name, source_text):
    print(f"  Writing: {topic_title[:60]}...")
    grounding = source_text if source_text else "(no extra source text available — rely only on the title, and clearly keep claims general)"
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{
            "role": "user",
            "content": f"""You are writing an original, SEO-friendly blog article for a tech blog
about AI tools, aimed at readers deciding whether/how to use a tool.

Topic: {topic_title}
Primary source: {source_name}
Source content excerpt (ground your facts in this, do not invent specifics beyond it):
\"\"\"{grounding}\"\"\"

Write one of these formats, whichever fits the topic best:
- A practical "how to use [tool] for [task]" tutorial with concrete steps
- A "[tool] vs [alternative]" comparison with a pros/cons table in HTML
- A "best AI tools for [use case]" roundup

Requirements:
- 900-1200 words
- Do NOT start with a title, heading, or restatement of the topic as a first line —
  Blogger already displays the post title separately, so the body must start
  directly with the opening paragraph/hook, no duplicate title text anywhere
- Original analysis and opinion, not a rewrite of the source — add your own
  take on who this is actually useful for and any caveats/limitations
- Clear H2 headings in HTML for each section, but no H1 and no title line at the top
- Include one comparison or feature table using HTML <table> tags if relevant
- End with a clear, specific takeaway (not generic "in conclusion" filler)
- Natural, conversational tone, written for a human reader, not for search engines
- Full HTML formatting ready for blog posting
- Do NOT wrap your output in markdown code fences (no ``` at the start or end) —
  output raw HTML only, nothing else

Write the full article now:"""
        }]
    )
    content = response.choices[0].message.content
    # Strip markdown code fences if the model wrapped its output in one
    content = re.sub(r'^```(?:html)?\s*\n?', '', content.strip())
    content = re.sub(r'\n?```\s*$', '', content.strip())
    # Safety net: the model sometimes writes its own title as the very first
    # line, then immediately repeats it before the real intro paragraph.
    # Detect an exact duplicated chunk of text (10-200 chars, ignoring tags
    # in between) right at the start, and drop the first occurrence.
    dup_pattern = re.compile(r'^\s*(?:<[^>]+>\s*)*([^<]{10,200}?)\s*(?:<[^>]+>\s*)*\1', re.IGNORECASE)
    m = dup_pattern.match(content)
    if m:
        dup_text = m.group(1)
        second_start = content.find(dup_text, m.start(1) + len(dup_text))
        if second_start != -1:
            content = content[second_start:]
    return content.strip()

# === POST TO BLOGGER ===
def post_to_blogger(service, title, content):
    post = {"kind": "blogger#post", "title": title, "content": content}
    result = service.posts().insert(blogId=BLOG_ID, body=post, isDraft=False).execute()
    url = result.get('url', '')
    print(f"  Posted to Blogger: {url}")
    return result, url

# === MAIN ===
def main():
    print("AIToolNotes Blog Automation Starting...")

    try:
        posted = json.loads(open(POSTED_FILE).read())
    except Exception:
        posted = []

    # Support both old format (list of titles) and new format (list of dicts)
    posted_titles = set()
    posted_links = set()
    for p in posted:
        if isinstance(p, dict):
            posted_titles.add(p.get('title', ''))
            posted_links.add(p.get('link', ''))
        else:
            posted_titles.add(p)

    service = get_blogger_service()
    all_topics = collect_topics()

    seen = set()
    unique_topics = []
    for t in all_topics:
        title = t['title']
        link = t.get('link', '')
        already_posted = (title in posted_titles) or (link and link in posted_links)
        if title not in seen and not already_posted and len(title) > 15:
            seen.add(title)
            unique_topics.append(t)
        if len(unique_topics) >= MAX_POSTS_PER_RUN:
            break

    print(f"\nPosting {len(unique_topics)} new articles (cap: {MAX_POSTS_PER_RUN})...")

    for i, topic_data in enumerate(unique_topics, 1):
        title = topic_data['title']
        source = topic_data['source']
        link = topic_data.get('link', '')
        print(f"\nArticle {i}/{len(unique_topics)}: {title[:60]}")

        try:
            source_text = fetch_source_article_text(link) if link else ""
            article = generate_article(title, source, source_text)
            result, url = post_to_blogger(service, title, article)
            posted.append({"title": title, "link": link})
            open(POSTED_FILE, 'w').write(json.dumps(posted[-500:]))
            time.sleep(3)
        except Exception as e:
            print(f"  Failed: {e}")
            continue

    print("\nDone.")

if __name__ == "__main__":
    main()