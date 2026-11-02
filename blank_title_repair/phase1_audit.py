#!/usr/bin/env python3
"""
AIToolNotes Blank Title Repair - Phase 1: Audit
Retrieves all posts with blank/whitespace-only titles from Blogger.
"""
import os
import sys
import json
import re
from pathlib import Path

# Add blog_automation directory to path
BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
sys.path.insert(0, str(BASE_DIR))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "7352205941047679763"
TOKEN_FILE = BASE_DIR / "token.json"
CREDS_FILE = BASE_DIR / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/blogger"]
AUDIT_DIR = BASE_DIR / "blank_title_audit_2026-11-02"
AUDIT_DIR.mkdir(exist_ok=True)

def get_blogger_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("ERROR: No valid credentials. Run blog_automation.py first to authenticate.")
            sys.exit(1)
    return build("blogger", "v3", credentials=creds)

def fetch_all_posts(service):
    """Fetch all posts from Blogger, handling pagination."""
    posts = []
    page_token = None
    # Request fields we need for audit
    fields = "items(id,title,content,url,published,updated,labels),nextPageToken"
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
    print(f"Fetched {len(posts)} total posts")
    return posts

def is_blank_title(post):
    """Check if title is blank or whitespace-only."""
    title = post.get("title", "") or ""
    return not title.strip()

def classify_post(post):
    """Classify post type based on content and URL."""
    url = post.get("url", "")
    content = post.get("content", "") or ""
    labels_raw = post.get("labels", [])
    if labels_raw and isinstance(labels_raw[0], str):
        labels = labels_raw
    else:
        labels = [l.get("name", "") for l in labels_raw]
    
    text = content.lower()
    
    # Check if empty
    if not content.strip():
        return "empty_page"
    
    # Check if very short (likely test)
    if len(content.strip()) < 100:
        return "test_post"
    
    # Check URL slug patterns
    slug = url.split("/")[-1].replace(".html", "") if url else ""
    
    # Check for duplicates based on content similarity
    return "legitimate_article"

def main():
    print("=== AIToolNotes Blank Title Repair - Phase 1: Audit ===\n")
    
    service = get_blogger_service()
    posts = fetch_all_posts(service)
    
    blank_posts = [p for p in posts if is_blank_title(p)]
    print(f"Found {len(blank_posts)} posts with blank/whitespace-only titles\n")
    
    audit_records = []
    for post in blank_posts:
        post_id = post.get("id", "")
        url = post.get("url", "")
        published = post.get("published", "")
        updated = post.get("updated", "")
        content = post.get("content", "") or ""
        labels_raw = post.get("labels", [])
        if labels_raw and isinstance(labels_raw[0], str):
            labels = labels_raw
        else:
            labels = [l.get("name", "") for l in labels_raw]
        
        # Extract slug from URL
        slug = url.split("/")[-1].replace(".html", "") if url else ""
        
        # Get word count
        text = re.sub(r'<[^>]+>', '', content)
        word_count = len(text.split())
        
        classification = classify_post(post)
        
        record = {
            "post_id": post_id,
            "url": url,
            "slug": slug,
            "published": published,
            "updated": updated,
            "word_count": word_count,
            "labels": labels,
            "classification": classification,
            "content_preview": text[:500].strip(),
        }
        audit_records.append(record)
        
        print(f"Post ID: {post_id}")
        print(f"  URL: {url}")
        print(f"  Slug: {slug}")
        print(f"  Published: {published}")
        print(f"  Words: {word_count}")
        print(f"  Labels: {labels}")
        print(f"  Classification: {classification}")
        print(f"  Preview: {text[:200].strip()}...")
        print()
    
    # Save audit data
    audit_file = AUDIT_DIR / "blank_posts_audit.json"
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_blank_posts": len(blank_posts),
            "posts": audit_records
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Audit saved to: {audit_file}")
    print(f"Total blank posts: {len(blank_posts)}")
    
    # Summary
    classifications = {}
    for r in audit_records:
        cls = r["classification"]
        classifications[cls] = classifications.get(cls, 0) + 1
    
    print("\nClassification summary:")
    for cls, count in classifications.items():
        print(f"  {cls}: {count}")

if __name__ == "__main__":
    main()
