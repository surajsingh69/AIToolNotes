#!/usr/bin/env python3
"""
AIToolNotes Blank Title Repair - Phase 2: Generate Titles
Reads audit data and generates proposed titles for blank-title posts.
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
AUDIT_DIR = BASE_DIR / "blank_title_audit_2026-11-02"
PROPOSED_FILE = AUDIT_DIR / "proposed_titles.json"

def slug_to_title(slug):
    """Convert URL slug to a readable title."""
    # Remove numeric suffixes (Blogger duplicate markers)
    slug = re.sub(r'_[0-9a-f]+$', '', slug)
    # Replace hyphens with spaces
    text = slug.replace('-', ' ')
    # Capitalize words
    words = text.split()
    title_words = []
    for word in words:
        # Don't capitalize common prepositions/articles unless first word
        if word.lower() in {'for', 'and', 'the', 'of', 'to', 'in', 'on', 'with', 'vs', 'best'}:
            title_words.append(word.lower())
        else:
            title_words.append(word.capitalize())
    # Capitalize first word always
    if title_words:
        title_words[0] = title_words[0].capitalize()
    return ' '.join(title_words)

def improve_title(slug, labels):
    """Generate an improved title based on slug and labels."""
    base = slug_to_title(slug)
    
    # Specific improvements based on common patterns
    improvements = {
        'ai-content-repurposing-workflow-turn': 'AI Content Repurposing Workflow: Turn Content Into Multiple Formats',
        'vps-for-ai-automation-best-hosting-for': 'VPS for AI Automation: Best Hosting Options',
        'runway-ml-free-tier-what-you-actually': 'Runway ML Free Tier: What You Actually Get',
        'capcut-ai-video-tutorial-practical': 'CapCut AI Video Tutorial: A Practical Guide',
        'best-free-ai-voice-generator-top-tools': 'Best Free AI Voice Generator: Top Tools Reviewed',
        'heygen-free-plan-limitations-what-you': 'HeyGen Free Plan: Limitations and What You Get',
        'ai-video-editor-comparison-best-tools': 'AI Video Editor Comparison: Best Tools for Creators',
        'best-free-ai-video-generator-2026-top': 'Best Free AI Video Generator 2026: Top Picks',
        'ai-productivity-tools-2026-best-tools': 'AI Productivity Tools 2026: Best Picks for Work',
        'best-free-ai-tools-for-students-10': 'Best Free AI Tools for Students: Top Picks',
        'ai-image-generation-for-beginners-best': 'AI Image Generation for Beginners: Best Tools to Start',
        'faceless-youtube-ai-tools-complete': 'Faceless YouTube AI Tools: Complete Guide',
        'ai-tools-for-youtube-creators-best-ai': 'AI Tools for YouTube Creators: Best AI Assistants',
        'ai-coding-agents-comparison-best-tools': 'AI Coding Agents Comparison: Best Tools for Developers',
        'ai-prompt-engineering-for-video': 'AI Prompt Engineering for Video Generation',
        'ai-avatar-video-for-marketing-best': 'AI Avatar Video for Marketing: Best Tools',
        'ai-video-thumbnail-generator-best-tools': 'AI Video Thumbnail Generator: Best Tools',
        'ai-agents-for-business-workflow': 'AI Agents for Business Workflow Automation',
        'ai-video-translation-tools-accuracy': 'AI Video Translation Tools: Accuracy and Use Cases',
        'heygen-vs-synthesia-for-training-videos': 'HeyGen vs Synthesia for Training Videos',
        'elevenlabs-vs-murf-for-podcasts-voice': 'ElevenLabs vs Murf for Podcasts and Voiceovers',
        'ai-script-to-video-workflow-complete': 'AI Script to Video Workflow: Complete Guide',
        'ai-workflow-automation-examples-10': 'AI Workflow Automation Examples: 10 Use Cases',
        'best-free-ai-voice-generator-top-tools': 'Best Free AI Voice Generator: Top Tools',
        'heygen-free-plan-limitations-what-you': 'HeyGen Free Plan: Limitations and Features',
        'capcut-ai-video-tutorial-practical': 'CapCut AI Video Tutorial: Practical Guide',
        'elevenlabs-vs-murf-ai-which-text-to': 'ElevenLabs vs Murf AI: Which Text-to-Speech Tool Is Best',
        'n8n-vs-make-vs-zapier-which-automation': 'n8n vs Make vs Zapier: Which Automation Tool Is Right for You',
        'heygen-vs-synthesia-which-ai-video-tool': 'HeyGen vs Synthesia: Which AI Video Tool Is Best',
        'ibm-granite-timeseries-ensemble': 'IBM Granite Timeseries Ensemble: Overview',
        'openais-decisions-api-faster-lowcost': 'OpenAI\'s Decisions API: Faster and Low-Cost AI',
        'how-third-moment-runs-10000-ai-agents': 'How Third Moment Runs 10,000 AI Agents',
        'thinkingbox-reveals-hidden-consistency': 'ThinkingBox Reveals Hidden Consistency in AI',
        'beyond-facts-new-tool-checks-source': 'Beyond Facts: New Tool Checks Source Credibility',
        'how-chatgpts-new-visual-ad-format-could': 'How ChatGPT\'s New Visual Ad Format Could Change Marketing',
        'how-v7s-context-graph-gives-ai-agents': 'How V7\'s Context Graph Gives AI Agents Memory',
        'ai-for-everyone-in-every-language': 'AI for Everyone in Every Language: Global Access',
        'building-ai-to-accelerate-science-and': 'Building AI to Accelerate Science and Research',
        'ai-for-societal-impact': 'AI for Societal Impact: Applications and Challenges',
        'how-fyxer-built-ai-executive-assistant': 'How Fyxer Built an AI Executive Assistant',
        'the-ai-policy-window-is-open-we-need-to': 'The AI Policy Window Is Open: What We Need to Do',
        'research-acceleration-view-inside-openai': 'Research Acceleration: A View Inside OpenAI',
        'supporting-independent-journalism-in': 'Supporting Independent Journalism in the AI Age',
        'converge-bio-raises-25m-backed-by': 'Converge Bio Raises $25M for AI Drug Discovery',
        'as-ai-safety-concerns-mount-three': 'As AI Safety Concerns Mount: Three Key Challenges',
        'give-your-coding-agents-memory-you-own': 'Give Your Coding Agents Memory You Own and Control',
        'try-google-pics-easy-image-creation-and': 'Try Google Pics: Easy Image Creation in Google Workspace',
        'the-latest-ai-news-we-announced-in': 'The Latest AI News We Announced: Key Updates',
    }
    
    if slug in improvements:
        return improvements[slug]
    
    # Fallback: use labels to enhance title
    if labels:
        primary = labels[0] if labels else ''
        if 'comparison' in slug.lower() or 'vs' in slug.lower():
            return base
        if 'best' in slug.lower() or 'top' in slug.lower():
            return base + ': Top Picks'
        if 'how' in slug.lower():
            return base
        if 'free' in slug.lower():
            return base + ': Free Options'
    
    return base

def main():
    print("=== AIToolNotes Blank Title Repair - Phase 2: Generate Titles ===\n")
    
    audit_file = AUDIT_DIR / "blank_posts_audit.json"
    with open(audit_file, "r", encoding="utf-8") as f:
        audit_data = json.load(f)
    
    posts = audit_data["posts"]
    proposed = []
    
    for post in posts:
        slug = post["slug"]
        labels = post.get("labels", [])
        proposed_title = improve_title(slug, labels)
        
        record = {
            "post_id": post["post_id"],
            "url": post["url"],
            "slug": slug,
            "current_title": "",  # blank
            "proposed_title": proposed_title,
            "labels": labels,
            "classification": post["classification"],
            "word_count": post["word_count"],
            "status": "ready_for_review"
        }
        proposed.append(record)
        print(f"Post {post['post_id']}")
        print(f"  Slug: {slug}")
        print(f"  Proposed title: {proposed_title}")
        print()
    
    # Save proposed titles
    with open(PROPOSED_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total_proposed": len(proposed),
            "posts": proposed
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Proposed titles saved to: {PROPOSED_FILE}")
    print(f"Total titles generated: {len(proposed)}")

if __name__ == "__main__":
    main()
