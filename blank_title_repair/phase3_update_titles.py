#!/usr/bin/env python3
"""
AIToolNotes Blank Title Repair - Phase 3: Apply Changes
Updates only the title field for blank-title posts via Blogger API.
"""
import os
import sys
import json
import time
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
AUDIT_DIR = BASE_DIR / "blank_title_audit_2026-11-02"
FINAL_FILE = AUDIT_DIR / "unique_titles_for_update.json"
UPDATE_LOG = AUDIT_DIR / "update_log.json"
AUDIT_LOG = AUDIT_DIR / "blank_posts_audit.json"

sys.path.insert(0, str(BASE_DIR))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "7352205941047679763"
TOKEN_FILE = BASE_DIR / "token.json"
CREDS_FILE = BASE_DIR / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/blogger"]

DELAY_BETWEEN_UPDATES = 1.5  # seconds to avoid rate limits

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

def update_post_title(service, post_id, new_title):
    """Update only the title field of a post."""
    try:
        # Fetch current post to preserve all other fields
        current = service.posts().get(
            blogId=BLOG_ID,
            postId=post_id,
        ).execute()
        
        # Update only title
        current["title"] = new_title
        
        # Update the post
        result = service.posts().update(
            blogId=BLOG_ID,
            postId=post_id,
            body=current,
        ).execute()
        
        return {
            "success": True,
            "post_id": post_id,
            "new_title": new_title,
            "url": result.get("url", ""),
            "updated": result.get("updated", ""),
        }
    except Exception as e:
        return {
            "success": False,
            "post_id": post_id,
            "new_title": new_title,
            "error": str(e),
        }

def main():
    print("=== AIToolNotes Blank Title Repair - Phase 3: Apply Changes ===\n")
    
    # Load final titles
    with open(FINAL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    posts = data["posts"]
    
    # Load original audit for logging
    with open(AUDIT_LOG, "r", encoding="utf-8") as f:
        audit_data = json.load(f)
    
    audit_map = {p["post_id"]: p for p in audit_data["posts"]}
    
    service = get_blogger_service()
    
    update_log = []
    success_count = 0
    fail_count = 0
    
    for i, post in enumerate(posts, 1):
        post_id = post["post_id"]
        new_title = post["proposed_title"]
        original = audit_map.get(post_id, {})
        
        print(f"[{i}/{len(posts)}] Updating {post_id}")
        print(f"  New title: {new_title}")
        
        result = update_post_title(service, post_id, new_title)
        
        log_entry = {
            "post_id": post_id,
            "url": original.get("url", ""),
            "original_title": "",  # was blank
            "new_title": new_title,
            "success": result["success"],
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        
        if result["success"]:
            log_entry["post_url"] = result.get("url", "")
            log_entry["blogger_updated"] = result.get("updated", "")
            success_count += 1
            print(f"  SUCCESS")
        else:
            log_entry["error"] = result.get("error", "")
            fail_count += 1
            print(f"  FAILED: {result.get('error', '')}")
        
        update_log.append(log_entry)
        print()
        
        # Rate limit delay
        if i < len(posts):
            time.sleep(DELAY_BETWEEN_UPDATES)
    
    # Save update log
    with open(UPDATE_LOG, "w", encoding="utf-8") as f:
        json.dump({
            "total_posts": len(posts),
            "successful": success_count,
            "failed": fail_count,
            "updates": update_log
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Update Complete ===")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Update log saved to: {UPDATE_LOG}")

if __name__ == "__main__":
    main()
