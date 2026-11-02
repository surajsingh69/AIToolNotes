#!/usr/bin/env python3
"""
Publish 5 new articles to Blogger
"""
import sys
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
sys.path.insert(0, str(BASE_DIR))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "7352205941047679763"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/blogger"]

def markdown_to_html(md_text):
    """Convert markdown to HTML for Blogger."""
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
    print(f"  Posted: {url}")
    return result, url

def main():
    articles = [
        {
            "file": BASE_DIR / "articles" / "best-free-ai-voice-generator-2026-top.md",
            "slug": "best-free-ai-voice-generator-2026-top",
        },
        {
            "file": BASE_DIR / "articles" / "best-free-ai-coding-assistant-2026.md",
            "slug": "best-free-ai-coding-assistant-2026",
        },
        {
            "file": BASE_DIR / "articles" / "best-free-ai-tools-for-ecommerce-2026.md",
            "slug": "best-free-ai-tools-for-ecommerce-2026",
        },
        {
            "file": BASE_DIR / "articles" / "best-free-ai-tools-for-content-marketing-2026.md",
            "slug": "best-free-ai-tools-for-content-marketing-2026",
        },
        {
            "file": BASE_DIR / "articles" / "best-free-ai-tools-for-educators-2026.md",
            "slug": "best-free-ai-tools-for-educators-2026",
        },
    ]
    
    service = get_blogger_service()
    results = []
    
    for i, article in enumerate(articles, 1):
        file_path = article["file"]
        slug = article["slug"]
        
        print(f"\n[{i}/{len(articles)}] Publishing: {slug}")
        
        if not file_path.exists():
            print(f"  SKIP: File not found: {file_path}")
            results.append({
                "slug": slug,
                "success": False,
                "error": "File not found",
            })
            continue
        
        md_content = file_path.read_text(encoding="utf-8")
        html_content = markdown_to_html(md_content)
        
        # Extract title from first H1
        import re
        title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else slug.replace('-', ' ').title()
        
        try:
            result, url = post_to_blogger(service, title, html_content)
            results.append({
                "slug": slug,
                "success": True,
                "post_id": result.get("id", ""),
                "title": title,
                "url": url,
                "word_count": len(md_content.split()),
            })
        except Exception as e:
            print(f"  FAILED: {str(e)}")
            results.append({
                "slug": slug,
                "success": False,
                "error": str(e),
            })
        
        # Rate limit
        if i < len(articles):
            import time
            time.sleep(2.0)
    
    # Save publish log
    log_file = BASE_DIR / "publish_log_2026-11-02-new-articles.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump({
            "published_at": datetime.utcnow().isoformat() + "Z",
            "total": len(articles),
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
