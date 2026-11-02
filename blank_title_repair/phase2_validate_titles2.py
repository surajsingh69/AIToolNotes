#!/usr/bin/env python3
"""
AIToolNotes Blank Title Repair - Phase 2.6: Final Title Validation
Check for exact duplicates in the existing blog and flag ambiguous cases.
"""
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
AUDIT_DIR = BASE_DIR / "blank_title_audit_2026-11-02"
FINAL_FILE = AUDIT_DIR / "final_titles.json"
VALIDATED_FILE = AUDIT_DIR / "validated_titles.json"

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def main():
    with open(FINAL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    posts = data["posts"]
    
    # Load posted_titles.json to check for existing titles
    posted_file = BASE_DIR / "posted_titles.json"
    with open(posted_file, "r", encoding="utf-8") as f:
        posted = json.load(f)
    
    existing_titles = set()
    for p in posted:
        if isinstance(p, dict) and p.get("title"):
            existing_titles.add(p["title"].strip())
        elif isinstance(p, str):
            existing_titles.add(p.strip())
    
    print(f"Loaded {len(existing_titles)} existing titles from posted_titles.json")
    
    validated = []
    flagged = []
    
    for post in posts:
        title = post["proposed_title"]
        slug = post["slug"]
        
        # Check if exact title already exists
        if title in existing_titles:
            flagged.append({
                "post_id": post["post_id"],
                "slug": slug,
                "proposed_title": title,
                "reason": "exact_title_exists",
                "recommendation": "Add disambiguation or use alternative title"
            })
            post["status"] = "flagged_duplicate"
            post["final_title"] = title + " (Detailed Guide)"
        else:
            # Check near-duplicates
            is_near_dup = False
            for existing in existing_titles:
                if similar(title, existing) >= 0.80:
                    is_near_dup = True
                    flagged.append({
                        "post_id": post["post_id"],
                        "slug": slug,
                        "proposed_title": title,
                        "similar_to": existing,
                        "similarity": round(similar(title, existing), 3),
                        "reason": "near_duplicate_title",
                        "recommendation": "Consider alternative phrasing"
                    })
                    post["status"] = "flagged_near_duplicate"
                    post["final_title"] = title + " - Complete Guide"
                    break
            
            if not is_near_dup:
                post["status"] = "approved"
                post["final_title"] = title
        
        validated.append(post)
    
    with open(VALIDATED_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total_posts": len(validated),
            "approved": len([p for p in validated if p["status"] == "approved"]),
            "flagged": len(flagged),
            "posts": validated
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nValidated: {len(validated)} posts")
    print(f"Approved: {len([p for p in validated if p['status'] == 'approved'])}")
    print(f"Flagged: {len(flagged)}")
    print(f"Validated titles saved to: {VALIDATED_FILE}")
    
    if flagged:
        print("\nFlagged posts:")
        for f in flagged:
            print(f"  {f['post_id']}: {f['proposed_title']}")
            print(f"    Reason: {f['reason']}")
            print(f"    Recommendation: {f['recommendation']}")

if __name__ == "__main__":
    main()
