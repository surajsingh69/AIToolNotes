# AIToolNotes Directory Submission Kit
# Use this to submit the tools directory to free AI directories

import requests
import json
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Acer\techsansar_v2")

# Directory information
DIRECTORY_INFO = {
    "name": "AIToolNotes Free AI Tools Directory",
    "url": "https://surajsingh69.github.io/tools",
    "description": "A searchable directory of 180+ genuinely free AI tools with honest reviews, actual limitations documented, and no affiliate links. Updated weekly.",
    "one_line": "180+ free AI tools compared and tested",
    "category": "AI Tools",
    "pricing": "Free",
    "contact_email": "surajjsingh0111@gmail.com",
    "logo_url": "https://surajsingh69.github.io/tools/logo.png",  # Placeholder
    "screenshot_url": "https://surajsingh69.github.io/tools/screenshot.png",  # Placeholder
}

# List of directories to submit to
DIRECTORIES = [
    {
        "name": "AI Tools Directory",
        "url": "https://aitoolsdirectory.com/submit",
        "method": "form",
        "requires_auth": False,
        "priority": 1,
    },
    {
        "name": "AI Valley",
        "url": "https://aivalley.ai/submit-tool/",
        "method": "form",
        "requires_auth": False,
        "priority": 2,
    },
    {
        "name": "FutureTools",
        "url": "https://futuretools.io/submit-a-tool",
        "method": "form",
        "requires_auth": False,
        "priority": 3,
    },
    {
        "name": "Altern",
        "url": "https://altern.ai/submit",
        "method": "form",
        "requires_auth": True,  # Requires Google/GitHub login
        "priority": 4,
    },
    {
        "name": "ToolScout",
        "url": "https://toolscout.ai/submit-tool",
        "method": "form",
        "requires_auth": False,
        "priority": 5,
    },
]

def get_submission_data():
    """Prepare submission data for directories."""
    return {
        "name": DIRECTORY_INFO["name"],
        "url": DIRECTORY_INFO["url"],
        "description": DIRECTORY_INFO["description"],
        "one_line": DIRECTORY_INFO["one_line"],
        "category": DIRECTORY_INFO["category"],
        "pricing": DIRECTORY_INFO["pricing"],
        "contact_email": DIRECTORY_INFO["contact_email"],
    }

def submit_to_directory(directory_url, data):
    """Submit to a directory via form."""
    # This would need to be customized per directory
    # Most directories have web forms that require browser interaction
    print(f"Submission data prepared for {directory_url}")
    print(f"  Name: {data['name']}")
    print(f"  URL: {data['url']}")
    print(f"  Category: {data['category']}")
    return True

def main():
    data = get_submission_data()
    
    print("=== AIToolNotes Directory Submission Kit ===\n")
    print("Manual submission required for most directories.")
    print("Use the data below to fill out forms.\n")
    
    print("Directory Information:")
    print(f"  Name: {data['name']}")
    print(f"  URL: {data['url']}")
    print(f"  Description: {data['description']}")
    print(f"  Category: {data['category']}")
    print(f"  Pricing: {data['pricing']}")
    print(f"  Contact: {data['contact_email']}")
    
    print("\nDirectories to submit to:")
    for i, directory in enumerate(DIRECTORIES, 1):
        print(f"  {i}. {directory['name']}")
        print(f"     URL: {directory['url']}")
        print(f"     Priority: {directory['priority']}")
        print(f"     Requires auth: {directory['requires_auth']}")
    
    print("\nNext steps:")
    print("1. Visit each directory URL")
    print("2. Fill out the submission form with the data above")
    print("3. Upload a logo (128x128px) and screenshot (1200x400px)")
    print("4. Submit and track approval status")
    
    # Save submission data to file
    output_file = BASE_DIR / "directory_submission_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "directory_info": DIRECTORY_INFO,
            "directories": DIRECTORIES,
            "submission_data": data,
        }, f, indent=2)
    
    print(f"\nSubmission data saved to: {output_file}")

if __name__ == "__main__":
    main()
