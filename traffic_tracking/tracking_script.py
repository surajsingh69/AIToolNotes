#!/usr/bin/env python3

"""
UTM Click Tracker - Logs referral clicks with full attribution data
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).resolve().parent.parent
TRACKING_DIR = BASE_DIR / "traffic_tracking"
TRACKING_LOG_FILE = TRACKING_DIR / "tracking_log.json"

def extract_utm_data(url):
    """Extract UTM parameters from URL"""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    utm_data = {}
    for key in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']:
        if key in params:
            utm_data[key] = params[key][0]
    
    return utm_data

def log_click(url, referrer=None, user_agent=None):
    """Log a click event with full attribution"""
    utm_data = extract_utm_data(url)
    
    if not utm_data:
        return None
    
    # Load existing log
    if TRACKING_LOG_FILE.exists():
        log_data = json.loads(TRACKING_LOG_FILE.read_text(encoding="utf-8"))
    else:
        log_data = {
            "tracking_start": datetime.now(timezone.utc).isoformat(),
            "total_clicks": 0,
            "by_platform": {},
            "by_article": {},
            "by_category": {},
            "by_subreddit": {},
            "daily": {},
            "events": [],
        }
    
    # Extract article slug
    article_slug = url.split("/")[-1].replace(".html", "").split("?")[0]
    
    # Determine category
    category = "general"
    if any(x in article_slug for x in ["student", "teacher", "education", "educator"]):
        category = "education"
    elif any(x in article_slug for x in ["video", "voice", "image", "creative", "design"]):
        category = "creative"
    elif any(x in article_slug for x in ["coding", "developer", "programming", "automation"]):
        category = "development"
    elif any(x in article_slug for x in ["marketing", "content-marketing", "content_marketing"]):
        category = "marketing"
    elif any(x in article_slug for x in ["business", "startup", "entrepreneur", "freelancer", "small-business", "real-estate", "ecommerce", "e-commerce", "finance", "legal", "healthcare", "customer-service", "hr-"]):
        category = "business"
    
    # Create event
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "utm_data": utm_data,
        "article_slug": article_slug,
        "category": category,
        "referrer": referrer,
        "user_agent": user_agent,
    }
    
    # Update counters
    log_data["total_clicks"] += 1
    
    platform = utm_data.get("utm_source", "unknown")
    log_data["by_platform"][platform] = log_data["by_platform"].get(platform, 0) + 1
    
    log_data["by_article"][article_slug] = log_data["by_article"].get(article_slug, 0) + 1
    
    log_data["by_category"][category] = log_data["by_category"].get(category, 0) + 1
    
    if "utm_term" in utm_data:
        subreddit = utm_data["utm_term"]
        log_data["by_subreddit"][subreddit] = log_data["by_subreddit"].get(subreddit, 0) + 1
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_data["daily"][today] = log_data["daily"].get(today, 0) + 1
    
    # Add event (keep last 1000)
    log_data["events"].append(event)
    if len(log_data["events"]) > 1000:
        log_data["events"] = log_data["events"][-1000:]
    
    # Save log
    TRACKING_LOG_FILE.write_text(json.dumps(log_data, indent=2), encoding="utf-8")
    
    return event

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tracking_script.py <url> [referrer] [user_agent]")
        sys.exit(1)
    
    url = sys.argv[1]
    referrer = sys.argv[2] if len(sys.argv) > 2 else None
    user_agent = sys.argv[3] if len(sys.argv) > 3 else None
    
    event = log_click(url, referrer, user_agent)
    if event:
        print(f"Logged click: {event['utm_data'].get('utm_source', 'unknown')} -> {event['article_slug']}")
    else:
        print("No UTM data in URL")
