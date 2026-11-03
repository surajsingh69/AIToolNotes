#!/usr/bin/env python3
"""
PUBLISH NEW ARTICLES — SEO-OPTIMIZED
Publishes articles to Blogger with schema markup and internal links.
"""

import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
sys.path.insert(0, str(BASE_DIR))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "7352205941047679763"
TOKEN_FILE = BASE_DIR / "token.json"
SEO_DIR = BASE_DIR / "seo"
KEYWORD_MAP = SEO_DIR / "keyword_map.json"


def load_keyword_map():
    if KEYWORD_MAP.exists():
        return json.loads(KEYWORD_MAP.read_text(encoding="utf-8"))
    return {}


def markdown_to_html(md_text: str) -> str:
    """Convert markdown to HTML."""
    lines = md_text.split('\n')
    html_parts = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('# '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h2>{stripped[2:]}</h2>')
        elif stripped.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h3>{stripped[3:]}</h3>')
        elif stripped.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h4>{stripped[4:]}</h4>')
        elif stripped.startswith('- '):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append(f'<li>{stripped[2:]}</li>')
        elif stripped.startswith('1. ') or stripped.startswith('2. ') or stripped.startswith('3. '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p>{stripped}</p>')
        elif stripped == '':
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append('<br>')
        elif stripped.startswith('**') and '**' in stripped[2:]:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p><strong>{stripped.replace("**", "")}</strong></p>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if stripped:
                html_parts.append(f'<p>{stripped}</p>')
    
    if in_list:
        html_parts.append('</ul>')
    
    return '\n'.join(html_parts)


def add_internal_links(html: str, slug: str) -> str:
    """Add related article links at the end of content."""
    keyword_map = load_keyword_map()
    
    # Find related articles (same category or similar keywords)
    related = []
    current_keywords = set(slug.replace('-', ' ').split())
    
    for other_slug, data in keyword_map.items():
        if other_slug == slug:
            continue
        other_keywords = set(other_slug.replace('-', ' ').split())
        overlap = current_keywords & other_keywords
        if len(overlap) >= 1:
            related.append((other_slug, data))
    
    # Take top 3 related
    related = related[:3]
    if not related:
        return html
    
    links_html = '\n<h3>Related Articles</h3>\n<ul>\n'
    for rel_slug, rel_data in related:
        rel_title = rel_data.get('title', rel_slug.replace('-', ' ').title())
        rel_url = f"https://aitoolnotes.blogspot.com/2026/11/{rel_slug}.html"
        links_html += f'<li><a href="{rel_url}">{rel_title}</a></li>\n'
    links_html += '</ul>\n'
    
    return html + links_html


def generate_schema(title: str, description: str, slug: str) -> str:
    """Generate JSON-LD Article schema."""
    url = f"https://aitoolnotes.blogspot.com/2026/11/{slug}.html"
    published_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    title_escaped = title.replace('"', '\\"')
    desc_escaped = description.replace('"', '\\"')
    
    return f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title_escaped}",
  "description": "{desc_escaped}",
  "url": "{url}",
  "datePublished": "{published_date}",
  "dateModified": "{published_date}",
  "publisher": {{
    "@type": "Organization",
    "name": "AIToolNotes",
    "url": "https://aitoolnotes.blogspot.com"
  }}
}}
</script>"""


def get_blogger_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), ["https://www.googleapis.com/auth/blogger"])
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("ERROR: No valid credentials.")
            sys.exit(1)
    return build("blogger", "v3", credentials=creds)


def main():
    # Get article files from command line args or use defaults
    if len(sys.argv) > 1:
        article_files = [BASE_DIR / arg for arg in sys.argv[1:]]
    else:
        # Default: publish one article
        article_files = [BASE_DIR / "articles" / "best-free-ai-tools-for-teachers-2026.md"]
    
    service = get_blogger_service()
    results = []
    
    print(f"Publishing {len(article_files)} articles...")
    print()
    
    for i, article_path in enumerate(article_files, 1):
        print(f"[{i}/{len(article_files)}] {article_path.name}")
        
        if not article_path.exists():
            print(f"  SKIP: File not found: {article_path}")
            continue
        
        md_content = article_path.read_text(encoding="utf-8")
        slug = article_path.stem
        
        keyword_map = load_keyword_map()
        kw_data = keyword_map.get(slug, {})
        
        # Extract title
        title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else slug.replace('-', ' ').title()
        
        # Generate description
        description = kw_data.get('meta_description', '')
        if not description:
            clean = re.sub(r'[#*_\-]+', '', md_content)
            sentences = re.split(r'[.!?\n]', clean)
            first_sentence = next((s.strip() for s in sentences if len(s.strip()) > 50), "")
            description = f"{title}. {first_sentence}" if first_sentence else title
            if len(description) > 155:
                description = description[:152].rsplit(' ', 1)[0] + '...'
        
        # Convert to HTML
        html = markdown_to_html(md_content)
        
        # Add internal links
        html = add_internal_links(html, slug)
        
        # Add schema
        schema = generate_schema(title, description, slug)
        html = schema + '\n' + html
        
        # Get labels
        labels = kw_data.get('labels', ['AI Tools', 'Free AI', '2026'])
        
        try:
            result = (
                service.posts()
                .insert(
                    blogId=BLOG_ID,
                    body={
                        "kind": "blogger#post",
                        "title": title,
                        "content": html,
                        "labels": labels,
                    },
                    isDraft=False,
                )
                .execute()
            )
            url = result.get("url", "")
            print(f"  ✓ Posted: {url}")
            results.append({
                "slug": slug,
                "success": True,
                "post_id": result.get("id", ""),
                "title": title,
                "url": url,
            })
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            results.append({
                "slug": slug,
                "success": False,
                "error": str(e),
            })
        
        # Rate limit
        if i < len(article_files):
            time.sleep(2.0)
    
    # Save publish log
    log_file = BASE_DIR / f"publish_log_{datetime.utcnow().strftime('%Y-%m-%d')}-seo.json"
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump({
            "published_at": datetime.utcnow().isoformat() + "Z",
            "total": len(article_files),
            "successful": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "results": results,
        }, f, indent=2)
    
    print(f"\n=== Publish Complete ===")
    print(f"Successful: {sum(1 for r in results if r.get('success'))}")
    print(f"Failed: {sum(1 for r in results if not r.get('success'))}")
    print(f"Log saved to: {log_file}")


if __name__ == "__main__":
    main()
