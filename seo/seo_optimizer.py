#!/usr/bin/env python3
"""
SEO OPTIMIZER — AIToolNotes
Injects schema markup, meta descriptions, and optimizes HTML for search.
"""

import json
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")
KEYWORD_MAP = BASE_DIR / "seo" / "keyword_map.json"


def load_keyword_map():
    if KEYWORD_MAP.exists():
        return json.loads(KEYWORD_MAP.read_text(encoding="utf-8"))
    return {}


def extract_title(md_text: str) -> str:
    match = re.search(r'^# (.+)$', md_text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def generate_meta_description(title: str, content: str) -> str:
    """Generate a 150-160 char meta description from title + first paragraph."""
    # Remove markdown formatting
    clean = re.sub(r'[#*_\-]+', '', content)
    sentences = re.split(r'[.!?\n]', clean)
    first_sentence = next((s.strip() for s in sentences if len(s.strip()) > 50), "")
    
    if first_sentence:
        desc = f"{title}. {first_sentence}"
    else:
        desc = title
    
    # Truncate to ~155 chars at word boundary
    if len(desc) > 155:
        desc = desc[:152].rsplit(' ', 1)[0] + '...'
    return desc


def generate_schema(title: str, description: str, slug: str, published: str | None = None) -> str:
    """Generate JSON-LD Article schema."""
    url = f"https://aitoolnotes.blogspot.com/2026/11/{slug}.html"
    published_date = published or datetime.utcnow().strftime("%Y-%m-%d")
    
    schema = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title}",
  "description": "{description}",
  "url": "{url}",
  "datePublished": "{published_date}",
  "dateModified": "{published_date}",
  "publisher": {{
    "@type": "Organization",
    "name": "AIToolNotes",
    "url": "https://aitoolnotes.blogspot.com"
  }}
}}
</script>"""
    return schema


def inject_schema(html: str, schema: str) -> str:
    """Inject schema markup after opening body tag or at start of content."""
    if '<body>' in html.lower():
        # For full HTML pages
        idx = html.lower().find('<body>')
        if idx != -1:
            return html[:idx+6] + '\n' + schema + '\n' + html[idx+6:]
    else:
        # For content fragments, prepend schema
        return schema + '\n' + html
    return html


def optimize_content(md_text: str, slug: str) -> tuple[str, str]:
    """Return (optimized_html, meta_description)."""
    title = extract_title(md_text)
    description = generate_meta_description(title, md_text)
    
    # Convert markdown to HTML (basic)
    html = markdown_to_html(md_text)
    
    # Add schema
    schema = generate_schema(title, description, slug)
    html = inject_schema(html, schema)
    
    return html, description


def markdown_to_html(md_text: str) -> str:
    """Convert markdown to HTML."""
    lines = md_text.split('\n')
    html_parts = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('# '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h2>{stripped[2:]}</h2>')
        elif stripped.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h3>{stripped[3:]}</h3>')
        elif stripped.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h4>{stripped[4:]}</h4>')
        elif stripped.startswith('- '):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append(f'<li>{stripped[2:]}</li>')
        elif stripped.startswith('1. ') or stripped.startswith('2. ') or stripped.startswith('3. '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p>{stripped}</p>')
        elif stripped == '':
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append('<br>')
        elif stripped.startswith('**') and '**' in stripped[2:]:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p><strong>{stripped.replace("**", "")}</strong></p>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if stripped:
                html_parts.append(f'<p>{stripped}</p>')
    
    if in_list:
        html_parts.append('</ul>')
    
    return '\n'.join(html_parts)


def get_seo_data(slug: str) -> dict:
    """Get SEO data for a specific article."""
    keyword_map = load_keyword_map()
    return keyword_map.get(slug, {})


if __name__ == "__main__":
    # Test with one article
    test_file = BASE_DIR / "articles" / "best-free-ai-tools-for-developers-2026.md"
    if test_file.exists():
        md = test_file.read_text(encoding="utf-8")
        html, desc = optimize_content(md, "best-free-ai-tools-for-developers-2026")
        print(f"Meta description: {desc}")
        print(f"\nSchema + HTML preview (first 500 chars):")
        print(html[:500])
