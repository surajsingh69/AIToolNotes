#!/usr/bin/env python3
"""
AIToolNotes Blank Title Repair - Phase 4: Verify Results
Re-fetches updated posts and verifies titles, URLs, and content integrity.
"""
import json
import time
import re
from pathlib import Path
from difflib import SequenceMatcher

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
AUDIT_DIR = BASE_DIR / "blank_title_audit_2026-11-02"
UPDATE_LOG = AUDIT_DIR / "update_log.json"
VERIFICATION_REPORT = AUDIT_DIR / "verification_report.json"

SCOPES = ["https://www.googleapis.com/auth/blogger"]
TOKEN_FILE = BASE_DIR / "token.json"
BLOG_ID = "7352205941047679763"

def get_blogger_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    return build("blogger", "v3", credentials=creds)

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def main():
    print("=== AIToolNotes Blank Title Repair - Phase 4: Verify Results ===\n")
    
    # Load update log
    with open(UPDATE_LOG, "r", encoding="utf-8") as f:
        update_data = json.load(f)
    
    updates = update_data["updates"]
    service = get_blogger_service()
    
    verified = []
    issues = []
    
    for i, update in enumerate(updates, 1):
        post_id = update["post_id"]
        expected_title = update["new_title"]
        original_url = update.get("url", "")
        
        print(f"[{i}/{len(updates)}] Verifying {post_id}")
        
        try:
            # Re-fetch post
            post = service.posts().get(
                blogId=BLOG_ID,
                postId=post_id,
            ).execute()
            
            actual_title = post.get("title", "")
            actual_url = post.get("url", "")
            actual_content = post.get("content", "") or ""
            actual_published = post.get("published", "")
            actual_updated = post.get("updated", "")
            
            # Verify title
            title_match = actual_title == expected_title
            
            # Verify URL unchanged
            url_match = actual_url == original_url if original_url else True
            
            # Verify content unchanged (should still be empty)
            content_unchanged = len(actual_content.strip()) == 0
            
            # Check for unexpected changes
            unexpected = []
            if not title_match:
                unexpected.append(f"Title mismatch: expected '{expected_title}', got '{actual_title}'")
            if not url_match:
                unexpected.append(f"URL changed: {original_url} -> {actual_url}")
            if not content_unchanged:
                unexpected.append(f"Content changed: expected empty, got {len(actual_content)} chars")
            
            record = {
                "post_id": post_id,
                "url": actual_url,
                "expected_title": expected_title,
                "actual_title": actual_title,
                "title_match": title_match,
                "url_match": url_match,
                "content_unchanged": content_unchanged,
                "updated": actual_updated,
                "status": "VERIFIED" if not unexpected else "ISSUES"
            }
            verified.append(record)
            
            if unexpected:
                issues.extend(unexpected)
                for u in unexpected:
                    print(f"  ISSUE: {u}")
            else:
                print(f"  VERIFIED: '{actual_title}'")
            
        except Exception as e:
            issues.append(f"Failed to fetch post {post_id}: {e}")
            verified.append({
                "post_id": post_id,
                "status": "FETCH_FAILED",
                "error": str(e)
            })
            print(f"  FAILED: {e}")
        
        time.sleep(0.5)
    
    # Check for duplicate titles among verified posts
    titles = [v["actual_title"] for v in verified if v.get("title_match")]
    seen = {}
    duplicates = []
    for title in titles:
        if title in seen:
            duplicates.append(title)
        else:
            seen[title] = 1
    
    # Generate summary
    verified_count = len([v for v in verified if v["status"] == "VERIFIED"])
    issues_count = len(issues)
    fetch_failed = len([v for v in verified if v["status"] == "FETCH_FAILED"])
    
    report = {
        "total_verified": len(verified),
        "verified_success": verified_count,
        "fetch_failed": fetch_failed,
        "issues_count": issues_count,
        "duplicate_titles": duplicates,
        "details": verified,
        "issues": issues
    }
    
    with open(VERIFICATION_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Verification Summary ===")
    print(f"Total posts verified: {len(verified)}")
    print(f"Verified successfully: {verified_count}")
    print(f"Fetch failed: {fetch_failed}")
    print(f"Issues found: {issues_count}")
    print(f"Duplicate titles: {len(duplicates)}")
    
    if duplicates:
        print("\nDuplicate titles detected:")
        for d in set(duplicates):
            print(f"  - {d}")
    
    if issues:
        print("\nIssues:")
        for issue in issues:
            print(f"  - {issue}")
    
    print(f"\nVerification report saved to: {VERIFICATION_REPORT}")

if __name__ == "__main__":
    main()
