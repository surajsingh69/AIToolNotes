#!/usr/bin/env python3
"""
UPDATE EXISTING POSTS WITH SEO SCHEMA
Adds JSON-LD Article schema to all published Blogger posts.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
sys.path.insert(0, str(BASE_DIR))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "7352205941047679763"
TOKEN_FILE = BASE_DIR / "token.json"
SCHEMA_DIR = BASE_DIR / "seo"

# Map of slug -> keyword data
KEYWORD_MAP_PATH = SCHEMA_DIR / "keyword_map.json"


def load_keyword_map():
    if KEYWORD_MAP_PATH.exists():
        return json.loads(KEYWORD_MAP_PATH.read_text(encoding="utf-8"))
    return {}


def generate_schema(title: str, description: str, slug: str, published: str = None) -> str:
    url = f"https://aitoolnotes.blogspot.com/2026/11/{slug}.html"
    published_date = published or datetime.utcnow().strftime("%Y-%m-%d")
    
    # Escape quotes for JSON
    title_escaped = title.replace('"', '\\"')
    desc_escaped = description.replace('"', '\\"')
    
    schema = f"""<script type="application/ld+json">
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
    return schema


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


def update_post_with_schema(service, post_id: str, title: str, content: str, slug: str):
    """Update a post with schema markup."""
    keyword_map = load_keyword_map()
    kw_data = keyword_map.get(slug, {})
    description = kw_data.get('meta_description', f'{title}. Complete guide for 2026.')
    
    # Extract published date from content if possible, or use current
    published = datetime.utcnow().strftime("%Y-%m-%d")
    
    schema = generate_schema(title, description, slug, published)
    
    # Check if schema already exists
    if '<script type="application/ld+json">' in content:
        print(f"  Schema already present, skipping: {title[:50]}")
        return False
    
    # Inject schema at start of content
    new_content = schema + '\n' + content
    
    try:
        service.posts().update(
            blogId=BLOG_ID,
            postId=post_id,
            body={
                "kind": "blogger#post",
                "id": post_id,
                "title": title,
                "content": new_content,
            },
        ).execute()
        print(f"  Updated: {title[:50]}")
        return True
    except Exception as e:
        print(f"  FAILED to update {title[:50]}: {e}")
        return False


def main():
    service = get_blogger_service()
    
    # Load all posts
    print("Fetching all posts...")
    posts = []
    req = service.posts().list(blogId=BLOG_ID, maxResults=500)
    while req:
        resp = req.execute()
        posts.extend(resp.get('items', []))
        req = service.posts().list_next(req, resp)
    
    print(f"Total posts: {len(posts)}")
    
    # Update each post with schema
    updated = 0
    skipped = 0
    failed = 0
    
    for post in posts:
        post_id = post.get('id')
        title = post.get('title', '')
        content = post.get('content', '')
        url = post.get('url', '')
        
        # Extract slug from URL
        slug_match = re.search(r'/2026/11/([^\.]+)\.html', url)
        if not slug_match:
            skipped += 1
            continue
        
        slug = slug_match.group(1)
        
        # Skip if already has schema
        if '<script type="application/ld+json">' in content:
            skipped += 1
            continue
        
        if update_post_with_schema(service, post_id, title, content, slug):
            updated += 1
        else:
            skipped += 1
    
    print(f"\n=== Update Complete ===")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
