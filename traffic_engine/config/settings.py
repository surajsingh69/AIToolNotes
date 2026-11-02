"""AIToolNotes Traffic Engine - Core Configuration"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "traffic_engine" / "config"

# Site definitions
SITES = {
    "blog": "https://aitoolnotes.blogspot.com/",
    "landing": "https://surajsingh69.github.io/",
    "tools": "https://surajsingh69.github.io/tools.html",
    "blog_feed": "https://surajsingh69.github.io/blog.html",
}

# Traffic targets
TARGETS = {
    "monthly_views_min": 50000,
    "daily_actions_max": 3,  # publishing/distribution actions per day
    "weekly_new_articles": 2,  # max new articles per week
}

# Module enable/disable flags
MODULES = {
    "opportunity_discovery": True,
    "content_optimization": True,
    "tool_acquisition": True,
    "distribution": True,
    "conversion_optimization": True,
    "measurement": True,
    "autonomous_optimization": True,
}

# Rate limits and safety
SAFETY = {
    "max_posts_per_run": 2,
    "min_hours_between_posts": 48,
    "max_retries": 3,
    "request_timeout": 30,
    "user_agent": "AIToolNotes-TrafficEngine/1.0 (legitimate traffic acquisition; contact: surajjsingh0111@gmail.com)",
}

# Data directories
PATHS = {
    "reports": BASE_DIR / "traffic_engine" / "reports",
    "data": BASE_DIR / "traffic_engine" / "data",
    "logs": BASE_DIR / "traffic_engine" / "logs",
}

# Ensure directories exist
for p in PATHS.values():
    p.mkdir(parents=True, exist_ok=True)


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default."""
    return os.environ.get(key, default)


def is_module_enabled(module_name: str) -> bool:
    """Check if a module is enabled in config."""
    return MODULES.get(module_name, False)
