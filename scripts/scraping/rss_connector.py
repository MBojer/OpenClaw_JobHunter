"""
scripts/scraping/rss_connector.py
Generic RSS/Atom feed parser used by Tier 1 connectors.
Handles fetching, parsing, and basic field extraction.
"""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from scripts.scraping.base_connector import JobListing


NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _text(el, *tags) -> str:
    """Try multiple tag names, return first non-empty text found."""
    for tag in tags:
        child = el.find(tag)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def fetch_rss(url: str, timeout: int = 15) -> list[dict]:
    """
    Fetch and parse an RSS/Atom feed.
    Returns a list of raw dicts with normalised keys.
    """
    headers = {"User-Agent": "JobHunter/2.0 (+https://github.com)"}
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)

    # Detect Atom vs RSS
    if root.tag.endswith("}feed") or root.tag == "feed":
        return _parse_atom(root)
    else:
        return _parse_rss(root)


def _parse_rss(root: ET.Element) -> list[dict]:
    items = []
    for item in root.findall(".//item"):
        items.append({
            "url":         _text(item, "link", "guid"),
            "title":       _text(item, "title"),
            "description": _text(item, "description",
                                  "{%s}encoded" % NAMESPACES["content"]),
            "company":     _text(item, "author",
                                  "{%s}creator" % NAMESPACES["dc"]),
            "pubDate":     _text(item, "pubDate"),
        })
    return items


def _parse_atom(root: ET.Element) -> list[dict]:
    ns = "http://www.w3.org/2005/Atom"
    items = []
    for entry in root.findall(f"{{{ns}}}entry"):
        link_el = entry.find(f"{{{ns}}}link")
        url = link_el.get("href", "") if link_el is not None else ""
        items.append({
            "url":         url,
            "title":       _text(entry, f"{{{ns}}}title"),
            "description": _text(entry, f"{{{ns}}}summary", f"{{{ns}}}content"),
            "company":     _text(entry, f"{{{ns}}}author"),
            "pubDate":     _text(entry, f"{{{ns}}}updated", f"{{{ns}}}published"),
        })
    return items


def rss_to_listings(items: list[dict], board_config: dict) -> list[JobListing]:
    """Convert raw RSS dicts to JobListing objects."""
    listings = []
    for item in items:
        if not item.get("url"):
            continue
        listings.append(JobListing(
            url             = item["url"],
            title           = item.get("title", ""),
            company         = item.get("company", ""),
            description_raw = item.get("description", ""),
        ))
    return listings
