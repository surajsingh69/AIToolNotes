"""One-time / idempotent Blogger AdSense trust-page & off-topic cleanup helper."""

from __future__ import annotations

import argparse
import os

from blog_automation import BASE_DIR, BLOG_ID, get_blogger_service
from seo_utils import is_off_topic_candidate


PAGES_DIR = os.path.join(BASE_DIR, "adsense_seo_kit", "pages")

REQUIRED_PAGES: list[tuple[str, str]] = [
    ("About", "about.html"),
    ("Contact", "contact.html"),
    ("Privacy Policy", "privacy_policy.html"),
    ("Terms & Editorial Disclosure", "terms_disclaimer.html"),
]


def load_page_html(filename: str, contact_email: str = "") -> str:
    path = os.path.join(PAGES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if contact_email:
        content = content.replace("[REPLACE_WITH_YOUR_EMAIL@example.com]", contact_email)
    return content


def ensure_trust_pages(
    service,
    blog_id: str,
    dry_run: bool = False,
    contact_email: str = "",
) -> dict[str, list[str]]:
    """Create missing AdSense-required trust pages on Blogger idempotently."""
    existing_resp = service.pages().list(blogId=blog_id, status="live").execute()
    existing_titles = {
        (p.get("title") or "").strip().lower()
        for p in existing_resp.get("items", [])
    }

    created: list[str] = []
    skipped: list[str] = []

    for title, filename in REQUIRED_PAGES:
        if title.lower() in existing_titles:
            skipped.append(title)
            continue

        body_html = load_page_html(filename, contact_email=contact_email)
        if dry_run:
            print(f"  [DRY RUN] Would create Blogger page: {title}")
            created.append(title)
            continue

        service.pages().insert(
            blogId=blog_id,
            body={
                "kind": "blogger#page",
                "title": title,
                "content": body_html,
            },
            isDraft=False,
        ).execute()
        print(f"  Created Blogger page: {title}")
        created.append(title)

    return {"created": created, "skipped": skipped}


def cleanup_off_topic_posts(
    service,
    blog_id: str,
    dry_run: bool = False,
) -> list[str]:
    """Revert published off-topic posts (non-AI-tool articles) back to draft."""
    reverted: list[str] = []
    page_token = None

    while True:
        req = service.posts().list(
            blogId=blog_id,
            status="live",
            maxResults=50,
            pageToken=page_token,
        )
        resp = req.execute()
        for post in resp.get("items", []):
            title = post.get("title", "")
            url = post.get("url", "")
            post_id = post.get("id", "")
            if not post_id:
                continue

            if is_off_topic_candidate(title, url):
                if dry_run:
                    print(f"  [DRY RUN] Would revert off-topic post to draft: {title}")
                else:
                    service.posts().revert(blogId=blog_id, postId=post_id).execute()
                    print(f"  Reverted off-topic post to draft: {title}")
                reverted.append(title)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return reverted


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Set up Blogger AdSense trust pages and clean up off-topic posts."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying Blogger.")
    parser.add_argument(
        "--cleanup-offtopic",
        action="store_true",
        help="Revert existing off-topic live posts to draft.",
    )
    parser.add_argument(
        "--contact-email",
        default=os.getenv("CONTACT_EMAIL", "").strip(),
        help="Optional email to replace the placeholder on the Contact page.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    blog_id = BLOG_ID or os.getenv("BLOG_ID", "").strip()
    if not blog_id:
        raise RuntimeError("BLOG_ID environment variable is required.")

    service = get_blogger_service()
    print("Checking Blogger AdSense trust pages...")
    page_summary = ensure_trust_pages(
        service,
        blog_id,
        dry_run=args.dry_run,
        contact_email=args.contact_email,
    )
    print(
        f"Pages summary: created={len(page_summary['created'])}, "
        f"already_present={len(page_summary['skipped'])}"
    )

    if args.cleanup_offtopic:
        print("\nScanning live posts for off-topic articles...")
        reverted = cleanup_off_topic_posts(service, blog_id, dry_run=args.dry_run)
        print(f"Off-topic posts reverted to draft: {len(reverted)}")


if __name__ == "__main__":
    main()
