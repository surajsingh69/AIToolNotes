"""AIToolNotes AI Tool Finder - Find free AI tools by category."""

__version__ = "0.1.0"

TOOLS = {
    "video": [
        {"name": "CapCut", "free": "Unlimited exports", "watermark": "No", "best_for": "Social videos, YouTube, TikTok"},
        {"name": "Pika Labs", "free": "80 credits/month", "watermark": "No", "best_for": "Creative AI clips"},
        {"name": "Runway ML", "free": "Limited credits", "watermark": "No", "best_for": "Testing and experimentation"},
    ],
    "voice": [
        {"name": "TTSMaker", "free": "Limited chars/month", "watermark": "No", "best_for": "Quick voiceovers"},
        {"name": "CapCut TTS", "free": "Unlimited", "watermark": "No", "best_for": "Editing workflow"},
        {"name": "ElevenLabs", "free": "10,000 chars/month", "watermark": "No", "best_for": "Natural-sounding voices"},
    ],
    "content": [
        {"name": "Claude", "free": "Free tier available", "watermark": "No", "best_for": "Scripting, long-form writing"},
        {"name": "Canva AI", "free": "Limited designs/month", "watermark": "No", "best_for": "Thumbnails, social graphics"},
        {"name": "Pika Labs", "free": "80 credits/month", "watermark": "No", "best_for": "AI B-roll"},
    ],
    "study": [
        {"name": "Quizlet AI", "free": "Limited AI sets", "watermark": "No", "best_for": "Flashcards, test prep"},
        {"name": "NotebookLM", "free": "100 notebooks", "watermark": "No", "best_for": "PDF/lecture summaries"},
        {"name": "Perplexity", "free": "Free with limits", "watermark": "No", "best_for": "Research with citations"},
    ],
    "agents": [
        {"name": "n8n", "free": "Self-hosted free", "watermark": "No", "best_for": "Workflow automation"},
        {"name": "Make", "free": "1,000 ops/month", "watermark": "No", "best_for": "Visual automation"},
        {"name": "CrewAI", "free": "Open source", "watermark": "No", "best_for": "Multi-agent frameworks"},
    ],
}

def find(category=None):
    if category and category in TOOLS:
        return TOOLS[category]
    return TOOLS

def list_categories():
    return list(TOOLS.keys())
