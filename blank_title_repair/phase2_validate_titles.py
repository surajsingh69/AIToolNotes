#!/usr/bin/env python3
"""
AIToolNotes Blank Title Repair - Phase 2.5: Validate and dedupe titles
"""
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
AUDIT_DIR = BASE_DIR / "blank_title_audit_2026-11-02"
PROPOSED_FILE = AUDIT_DIR / "proposed_titles.json"
FINAL_FILE = AUDIT_DIR / "final_titles.json"

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def main():
    with open(PROPOSED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    posts = data["posts"]
    final = []
    duplicates = []
    flagged = []
    
    # Check for exact duplicates and near-duplicates
    seen_exact = {}
    for post in posts:
        title = post["proposed_title"]
        post_id = post["post_id"]
        
        # Flag exact duplicates
        if title in seen_exact:
            duplicates.append({
                "post_id": post_id,
                "title": title,
                "duplicate_of": seen_exact[title],
                "action": "flag_for_review"
            })
            flagged.append(post)
            continue
        
        seen_exact[title] = post_id
        
        # Check for near-duplicates
        for existing_title, existing_id in seen_exact.items():
            if existing_title == title:
                continue
            sim = similar(title, existing_title)
            if sim >= 0.80:
                duplicates.append({
                    "post_id": post_id,
                    "title": title,
                    "similar_to": existing_title,
                    "similarity": round(sim, 3),
                    "action": "flag_for_review"
                })
                flagged.append(post)
                break
        
        final.append(post)
    
    # Fix flagged posts with disambiguated titles
    for post in flagged:
        slug = post["slug"]
        labels = post.get("labels", [])
        
        # Add disambiguation based on URL suffix or labels
        if post["post_id"] == "8804828117508302666":
            post["proposed_title"] = "ElevenLabs vs Murf AI: Which Text-to-Speech Tool Is Best"
        elif post["post_id"] == "7743974473471335125":
            post["proposed_title"] = "AI Video Editor Comparison: Best Tools"
        elif post["post_id"] == "25153271652846870":
            post["proposed_title"] = "Best Free AI Video Generator 2026: Top Picks"
        elif similar(post["proposed_title"], "Best Free AI Voice Generator: Top Tools") >= 0.8:
            post["proposed_title"] = "Best Free AI Voice Generator: Top Picks and Features"
        elif similar(post["proposed_title"], "CapCut AI Video Tutorial: Practical Guide") >= 0.8:
            post["proposed_title"] = "CapCut AI Video Tutorial: Practical Step-by-Step Guide"
        elif similar(post["proposed_title"], "HeyGen Free Plan: Limitations and Features") >= 0.8:
            post["proposed_title"] = "HeyGen Free Plan: Features, Limits, and What to Expect"
        else:
            # Generic disambiguation
            post["proposed_title"] = post["proposed_title"] + " (Review)"
    
    # Re-check for duplicates after fixes
    seen_exact = {}
    for post in final + flagged:
        title = post["proposed_title"]
        if title in seen_exact:
            post["proposed_title"] = title + " - Detailed Guide"
        else:
            seen_exact[title] = post["post_id"]
    
    all_posts = final + flagged
    
    with open(FINAL_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total_posts": len(all_posts),
            "ready_for_update": len(final),
            "flagged": len(flagged),
            "duplicates_detected": len(duplicates),
            "posts": all_posts
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Total posts: {len(all_posts)}")
    print(f"Ready for update: {len(final)}")
    print(f"Flagged for disambiguation: {len(flagged)}")
    print(f"Duplicate pairs detected: {len(duplicates)}")
    print(f"\nFinal titles saved to: {FINAL_FILE}")
    
    if duplicates:
        print("\nDuplicate/near-duplicate titles:")
        for d in duplicates:
            print(f"  {d['post_id']}: {d['title']}")
            if 'duplicate_of' in d:
                print(f"    Exact duplicate of: {d['duplicate_of']}")
            if 'similar_to' in d:
                print(f"    Similar to: {d['similar_to']} ({d['similarity']})")

if __name__ == "__main__":
    main()
