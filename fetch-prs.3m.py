#!/usr/bin/python3

import json
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Credentials
GITHUB_USERNAME = "your-github-username"
KEYCHAIN_ACCOUNT = "your-keychain-account"
KEYCHAIN_TOKEN = "your-keychain-token"

GITHUB_SEARCH_URL = "https://api.github.com/search/issues"

# Colors for the UI
ORANGE = "#FF8000"
ORANGE_LIGHT = "#FFA64D"
GREEN = "#2E9E4F"
GREEN_LIGHT = "#6FC98A"
GRAY = "#8E8E93"

# Header and row font styles
HEADER = "font=HelveticaNeue-Bold size=13"
ROW = "font=HelveticaNeue size=13"


def get_token():
    """Fetch the GitHub token from the macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_TOKEN, "-w"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def shorten(title, max_len=40):
    """Truncate long PR titles, adding an ellipsis when needed."""
    return f"{title[:max_len - 1]}…" if len(title) > max_len else title


def safe(text):
    """Make a string safe to sit inside a double-quoted SwiftBar param value."""
    return text.replace('"', "'")


def parse_time(iso):
    """Parse a GitHub ISO 8601 timestamp into an aware datetime."""
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def age(iso):
    """Rounded age since an ISO timestamp, using the largest single unit."""
    mins = int((datetime.now(timezone.utc) - parse_time(iso)).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 1)}m"

    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h"

    days = hrs // 24
    if days < 7:
        return f"{days}d"

    return f"{days // 7}w"


def search(*qualifiers):
    """Build an issue-search query scoped to open PRs not authored by you."""
    return " ".join(("is:open", "is:pr", f"-author:{GITHUB_USERNAME}", *qualifiers))


def get_query(query, headers):
    """Return a list of PR items, or None if the request failed."""
    try:
        url = f"{GITHUB_SEARCH_URL}?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.load(res).get("items", [])
    except Exception:
        return None


def error_menu(message):
    """Print a menu bar warning with an error line."""
    print("PRs ⚠️ | color=red")
    print("---")
    print(f"{message} | color=red")
    print("Refresh | refresh=true")


def print_row(pr, color):
    print(f'{shorten(pr["title"])} ({age(pr["created_at"])}) | '
          f'href={pr["html_url"]} tooltip="{safe(pr["title"])}" color={color} {ROW}')


def print_section(title, title_color, prs, row_color, empty_text):
    """Print a bold header followed by its PR rows (or an empty-state line)."""
    print(f"{title} | color={title_color} {HEADER} refresh=true")
    if not prs:
        print(f"{empty_text} | color={GRAY} {ROW}")
        return
    for pr in sorted(prs, key=lambda pr: parse_time(pr["created_at"])):
        print_row(pr, row_color)


def fetch_prs():
    token = get_token()
    if not token:
        error_menu("Token not found in Keychain")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "swiftbar-github-plugin",
    }

    # Pending review: open PRs requesting your review and not yet approved.
    for_review = get_query(search(f"review-requested:{GITHUB_USERNAME}", "-review:approved"), headers)
    # Approved: open PRs assigned to you that are approved by anyone. GitHub drops
    # you from `review-requested` once you submit a review, so we union two queries
    # to catch both PRs still awaiting your review and ones you already reviewed.
    approved_requested = get_query(search(f"review-requested:{GITHUB_USERNAME}", "review:approved"), headers)
    approved_reviewed = get_query(search(f"reviewed-by:{GITHUB_USERNAME}", "review:approved"), headers)

    results = (for_review, approved_requested, approved_reviewed)
    if any(r is None for r in results):
        error_menu("Could not reach GitHub")
        return

    # Merge the two approved queries, de-duping by PR id (dict keeps order).
    approved = list({pr["id"]: pr for pr in approved_requested + approved_reviewed}.values())

    # Menu bar title
    print(f"PRs ({len(for_review)}) | font=SFProText-Medium size=14")
    print("---")

    # Print sections for needs review and approved PRs
    print_section("Needs Review", ORANGE, for_review, ORANGE_LIGHT, "No PRs waiting")
    print("---")
    print_section("Approved", GREEN, approved, GREEN_LIGHT, "Nothing approved")
    print("---")
    print("Refresh | refresh=true")


if __name__ == "__main__":
    fetch_prs()
