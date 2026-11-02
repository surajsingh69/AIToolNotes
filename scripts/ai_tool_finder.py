#!/usr/bin/env python3
"""
AIToolNotes AI Tool Finder
Quick reference for free AI tools by category.

Usage:
    python ai_tool_finder.py --category video
    python ai_tool_finder.py --category voice
    python ai_tool_finder.py --list
"""

import argparse
import sys

TOOLS = {
    "video": [
        {"name": "CapCut", "free": "Unlimited exports", "watermark": "No", "best_for": "Social videos, YouTube, TikTok"},
        {"name": "Pika Labs", "free": "80 credits/month", "watermark": "No", "best_for": "Creative AI clips"},
        {"name": "Runway ML", "free": "Limited credits", "watermark": "No", "best_for": "Testing and experimentation"},
        {"name": "HeyGen", "free": "1-3 videos/month", "watermark": "Yes", "best_for": "AI avatar presenters"},
    ],
    "voice": [
        {"name": "TTSMaker", "free": "Limited chars/month", "watermark": "No", "best_for": "Quick voiceovers"},
        {"name": "CapCut TTS", "free": "Unlimited", "watermark": "No", "best_for": "Editing workflow"},
        {"name": "ElevenLabs", "free": "10,000 chars/month", "watermark": "No", "best_for": "Natural-sounding voices"},
        {"name": "Murf AI", "free": "Limited credits", "watermark": "No", "best_for": "Professional voiceovers"},
    ],
    "content": [
        {"name": "Claude", "free": "Free tier available", "watermark": "No", "best_for": "Scripting, long-form writing"},
        {"name": "Canva AI", "free": "Limited designs/month", "watermark": "No", "best_for": "Thumbnails, social graphics"},
        {"name": "Pika Labs", "free": "80 credits/month", "watermark": "No", "best_for": "AI B-roll"},
        {"name": "CapCut", "free": "Unlimited", "watermark": "No", "best_for": "Editing, captions, TTS"},
    ],
    "study": [
        {"name": "Quizlet AI", "free": "Limited AI sets", "watermark": "No", "best_for": "Flashcards, test prep"},
        {"name": "NotebookLM", "free": "100 notebooks", "watermark": "No", "best_for": "PDF/lecture summaries"},
        {"name": "Perplexity", "free": "Free with limits", "watermark": "No", "best_for": "Research with citations"},
        {"name": "Anki", "free": "Unlimited", "watermark": "No", "best_for": "Spaced repetition"},
        {"name": "Claude", "free": "Free tier", "watermark": "No", "best_for": "Essay writing, coding help"},
    ],
    "agents": [
        {"name": "n8n", "free": "Self-hosted free", "watermark": "No", "best_for": "Workflow automation"},
        {"name": "Make", "free": "1,000 ops/month", "watermark": "No", "best_for": "Visual automation"},
        {"name": "CrewAI", "free": "Open source", "watermark": "No", "best_for": "Multi-agent frameworks"},
        {"name": "Dify", "free": "Self-hosted free", "watermark": "No", "best_for": "RAG pipelines, agents"},
    ],
}

def list_categories():
    print("Available categories:")
    for cat in TOOLS:
        print(f"  - {cat}")

def show_tools(category):
    if category not in TOOLS:
        print(f"Unknown category: {category}")
        print("Use --list to see available categories")
        sys.exit(1)
    
    tools = TOOLS[category]
    print(f"\nFree AI {category.title()} Tools (2026)")
    print("=" * 60)
    for tool in tools:
        print(f"\n{tool['name']}")
        print(f"  Free: {tool['free']}")
        print(f"  Watermark: {tool['watermark']}")
        print(f"  Best for: {tool['best_for']}")
    print("\nFor detailed reviews: https://aitoolnotes.blogspot.com/")

def main():
    parser = argparse.ArgumentParser(description="AIToolNotes AI Tool Finder")
    parser.add_argument("--category", help="Tool category (video, voice, content, study, agents)")
    parser.add_argument("--list", action="store_true", help="List all categories")
    
    args = parser.parse_args()
    
    if args.list:
        list_categories()
    elif args.category:
        show_tools(args.category)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
