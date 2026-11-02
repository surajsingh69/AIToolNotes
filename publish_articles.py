#!/usr/bin/env python3
"""
AIToolNotes Article Publisher
Publishes expanded and new articles to Blogger via API.
"""
import os
import sys
import json
import re
import time
import html
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
ARTICLES_DIR = BASE_DIR / "articles"
BLANK_CONTENT_DIR = BASE_DIR / "articles" / "blank_post_content"
SCOPES = ["https://www.googleapis.com/auth/blogger"]
TOKEN_FILE = BASE_DIR / "token.json"
BLOG_ID = "7352205941047679763"
PUBLISH_LOG = BASE_DIR / "publish_log_2026-11-02.json"

sys.path.insert(0, str(BASE_DIR))
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

DELAY_BETWEEN_UPDATES = 2.0

def get_blogger_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("ERROR: No valid credentials.")
            sys.exit(1)
    return build("blogger", "v3", credentials=creds)

def markdown_to_html(md_text):
    """Convert markdown to HTML for Blogger."""
    lines = md_text.split('\n')
    html_parts = []
    in_list = False
    in_paragraph = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if in_paragraph:
                html_parts.append('</p>')
                in_paragraph = False
            continue
        
        # Headings
        if stripped.startswith('# '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if in_paragraph:
                html_parts.append('</p>')
                in_paragraph = False
            text = stripped[2:].strip()
            html_parts.append(f'<h2>{html.escape(text)}</h2>')
            continue
        elif stripped.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if in_paragraph:
                html_parts.append('</p>')
                in_paragraph = False
            text = stripped[3:].strip()
            html_parts.append(f'<h3>{html.escape(text)}</h3>')
            continue
        elif stripped.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if in_paragraph:
                html_parts.append('</p>')
                in_paragraph = False
            text = stripped[4:].strip()
            html_parts.append(f'<h4>{html.escape(text)}</h4>')
            continue
        
        # List items
        if stripped.startswith('- ') or stripped.startswith('* '):
            if in_paragraph:
                html_parts.append('</p>')
                in_paragraph = False
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            text = stripped[2:].strip()
            # Handle bold and links
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
            html_parts.append(f'<li>{text}</li>')
            continue
        
        # Close list if not a list item
        if in_list:
            html_parts.append('</ul>')
            in_list = False
        
        # Paragraphs
        if not in_paragraph:
            html_parts.append('<p>')
            in_paragraph = True
        
        # Process inline formatting
        line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', line)
        line = html.escape(line, quote=False)
        
        html_parts.append(line)
    
    if in_list:
        html_parts.append('</ul>')
    if in_paragraph:
        html_parts.append('</p>')
    
    return '\n'.join(html_parts)

def find_blogger_post_by_slug(service, slug):
    """Find a Blogger post by URL slug."""
    # Fetch all posts and match by slug
    posts = []
    page_token = None
    fields = "items(id,title,url,content,published,updated),nextPageToken"
    while True:
        resp = service.posts().list(
            blogId=BLOG_ID,
            maxResults=500,
            pageToken=page_token,
            fields=fields,
        ).execute()
        items = resp.get("items", [])
        posts.extend(items)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    
    for post in posts:
        url = post.get("url", "")
        if slug in url:
            return post
    return None

def update_post_content(service, post_id, new_content, new_title=None):
    """Update a Blogger post with new content."""
    try:
        current = service.posts().get(
            blogId=BLOG_ID,
            postId=post_id,
        ).execute()
        
        current["content"] = new_content
        if new_title:
            current["title"] = new_title
        
        result = service.posts().update(
            blogId=BLOG_ID,
            postId=post_id,
            body=current,
        ).execute()
        
        return {
            "success": True,
            "post_id": post_id,
            "url": result.get("url", ""),
            "title": result.get("title", ""),
            "updated": result.get("updated", ""),
        }
    except Exception as e:
        return {
            "success": False,
            "post_id": post_id,
            "error": str(e),
        }

def main():
    print("=== AIToolNotes Article Publisher ===\n")
    
    service = get_blogger_service()
    
    # Define articles to publish
    articles = [
        # 10 expanded articles
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "best-free-ai-tools-2026.md",
            "slug": "best-free-ai-tools-2026-top-50-no-cost",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "best-free-ai-tools-for-students-2026.md",
            "slug": "best-free-ai-tools-for-students-10_01285977117",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "best-free-ai-tools-for-teachers-2026.md",
            "slug": "best-free-ai-tools-for-teachers-2026",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "free-ai-image-generator-comparison-2026.md",
            "slug": "free-ai-image-generator-best-tools",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "free-ai-tools-for-content-creators-2026.md",
            "slug": "free-ai-tools-for-content-creators-2026",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "free-ai-tools-for-entrepreneurs-2026.md",
            "slug": "free-ai-tools-for-entrepreneurs-2026",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "free-ai-tools-for-freelancers-2026.md",
            "slug": "free-ai-tools-for-freelancers-2026",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "free-ai-tools-for-marketing-2026.md",
            "slug": "free-ai-marketing-tools-2026-best-picks",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "free-ai-tools-for-nonprofits-2026.md",
            "slug": "free-ai-tools-for-nonprofits-2026",
        },
        {
            "type": "expanded",
            "file": ARTICLES_DIR / "free-ai-tools-for-small-business-2026.md",
            "slug": "free-ai-tools-for-small-business-build",
        },
        # 5 new blank post drafts
        {
            "type": "new_draft",
            "file": BLANK_CONTENT_DIR / "ai-video-editor-comparison-best-tools.md",
            "slug": "ai-video-editor-comparison-best-tools",
        },
        {
            "type": "new_draft",
            "file": BLANK_CONTENT_DIR / "best-free-ai-video-generator-2026-top.md",
            "slug": "best-free-ai-video-generator-2026-top",
        },
        {
            "type": "new_draft",
            "file": BLANK_CONTENT_DIR / "ai-script-to-video-workflow-complete.md",
            "slug": "ai-script-to-video-workflow-complete",
        },
        {
            "type": "new_draft",
            "file": BLANK_CONTENT_DIR / "n8n-vs-make-vs-zapier-which-automation.md",
            "slug": "n8n-vs-make-vs-zapier-which-automation",
        },
        {
            "type": "new_draft",
            "file": BLANK_CONTENT_DIR / "elevenlabs-vs-murf-for-podcasts-voice.md",
            "slug": "elevenlabs-vs-murf-for-podcasts-voice",
        },
    ]
    
    results = []
    
    for i, article in enumerate(articles, 1):
        slug = article["slug"]
        file_path = article["file"]
        
        print(f"[{i}/{len(articles)}] Publishing: {slug}")
        
        # Read markdown
        if not file_path.exists():
            print(f"  SKIP: File not found: {file_path}")
            results.append({
                "slug": slug,
                "type": article["type"],
                "success": False,
                "error": "File not found",
            })
            continue
        
        md_content = file_path.read_text(encoding="utf-8")
        
        # Convert to HTML
        html_content = markdown_to_html(md_content)
        
        # Extract title from first H1
        title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else slug.replace('-', ' ').title()
        
        # Find existing post
        post = find_blogger_post_by_slug(service, slug)
        
        if not post:
            print(f"  SKIP: No existing post found for slug: {slug}")
            results.append({
                "slug": slug,
                "type": article["type"],
                "success": False,
                "error": "Post not found",
            })
            continue
        
        post_id = post["id"]
        current_title = post.get("title", "")
        
        # Update post
        result = update_post_content(service, post_id, html_content, title)
        
        if result["success"]:
            print(f"  SUCCESS: {title}")
            print(f"  URL: {result.get('url', '')}")
            results.append({
                "slug": slug,
                "type": article["type"],
                "success": True,
                "post_id": post_id,
                "title": title,
                "url": result.get("url", ""),
                "word_count": len(md_content.split()),
            })
        else:
            print(f"  FAILED: {result.get('error', '')}")
            results.append({
                "slug": slug,
                "type": article["type"],
                "success": False,
                "error": result.get("error", ""),
            })
        
        # Rate limit
        if i < len(articles):
            time.sleep(DELAY_BETWEEN_UPDATES)
    
    # Save publish log
    with open(PUBLISH_LOG, "w", encoding="utf-8") as f:
        json.dump({
            "published_at": datetime.utcnow().isoformat() + "Z",
            "total_articles": len(articles),
            "successful": len([r for r in results if r["success"]]),
            "failed": len([r for r in results if not r["success"]]),
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Publish Complete ===")
    print(f"Successful: {len([r for r in results if r['success']])}")
    print(f"Failed: {len([r for r in results if not r['success']])}")
    print(f"Log saved to: {PUBLISH_LOG}")

if __name__ == "__main__":
    main()
