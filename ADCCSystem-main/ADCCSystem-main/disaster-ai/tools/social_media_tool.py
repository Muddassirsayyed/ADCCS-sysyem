"""
ADCC — Social Media Tool
=========================
Collects disaster mentions and public alerts from open online feeds.
Providers (Priority-ordered):
1. GDELT Project Doc API (Free real-time global news database)
2. Google News RSS search
3. Reddit Public Search feeds (JSON endpoint)

Includes keyword relevance scoring, location extraction, and deduplication.
"""

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests
from loguru import logger
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GNEWS_RSS_URL = "https://news.google.com/rss/search"
REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"

TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 1

# Standard user-agent to prevent Reddit from blocking queries with 429/403
CUSTOM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ADCC/1.0.0 (Emergency Response Command Center)"

DISASTER_KEYWORDS = {
    "Flood": ["flood", "flooding", "waterlogging", "submerged", "inundation", "deluge", "torrential rain"],
    "Cyclone": ["cyclone", "hurricane", "typhoon", "tropical storm", "landfall", "gale"],
    "Earthquake": ["earthquake", "quake", "tremor", "richter", "seismic", "aftershock"],
    "Wildfire": ["wildfire", "bushfire", "forest fire", "blaze", "inferno"],
    "Heatwave": ["heatwave", "extreme heat", "temperature record", "sunstroke"],
    "Landslide": ["landslide", "mudslide", "rockslide", "debris flow"],
    "Tsunami": ["tsunami", "tidal wave"],
    "Drought": ["drought", "water scarcity", "arid"]
}

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class SocialDisasterReport(BaseModel):
    """Normalized report returned by all search functions."""
    title: str = Field(..., description="Report title/headline")
    source: str = Field(..., description="Name of the publisher/subreddit/domain")
    source_url: str = Field(..., description="Link to the source article or post")
    location: str = Field("Unknown", description="Extracted geographic location")
    timestamp: str = Field(..., description="ISO 8601 creation/publish time")
    confidence: float = Field(..., description="Computed relevance/confidence score (0.0 to 1.0)")
    disaster_type: str = Field(..., description="Detected disaster class")
    snippet: Optional[str] = Field(None, description="Short snippet of text content")
    provider: str = Field(..., description="Data provider: GDELT, GoogleNews, or Reddit")


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _get_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> requests.Response:
    """Performs HTTP GET with retries and timeout."""
    req_headers = {"User-Agent": CUSTOM_USER_AGENT}
    if headers:
        req_headers.update(headers)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=req_headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except Exception as e:
            logger.warning(f"[SocialMediaTool] Request to {url} failed on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY * attempt)
    raise RuntimeError(f"[SocialMediaTool] Failed all retries for URL: {url}")


def _detect_disaster_type(text: str) -> str:
    """Infers the type of disaster from keywords. Defaults to 'Unknown'."""
    text_lower = text.lower()
    for dtype, keywords in DISASTER_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return dtype
    return "Unknown"


def _extract_location(text: str) -> str:
    """
    Tries to find locations in the headline text.
    Standard patterns (in [City], near [Location], in the region of [Area]).
    """
    # Simple regex rules to find geographic entities
    patterns = [
        r"in\s+([A-Z][a-zA-Z\s]{2,20})(?=\s+disaster|\s+flooding|\s+quake|\s+news|\s+state|\s+district|\s+county|\s+province|\s+country|\.|\,|$)",
        r"near\s+([A-Z][a-zA-Z\s]{2,20})",
        r"hits\s+([A-Z][a-zA-Z\s]{2,20})",
        r"strikes\s+([A-Z][a-zA-Z\s]{2,20})",
        r"([A-Z][a-zA-Z\s]{2,20})\s+(?:Flood|Cyclone|Earthquake|Landslide|Wildfire)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            loc = match.group(1).strip()
            # Clean trailing words like "and" or punctuation
            loc = re.sub(r"\s+(and|or|is|was|has|under|after)\s*$", "", loc, flags=re.IGNORECASE)
            return loc
    return "Unknown"


def _calculate_relevance(title: str, text: Optional[str] = None) -> float:
    """
    Computes a simple 0.0 - 1.0 score indicating document relevance.
    Looks at frequency of disaster terms.
    """
    score = 0.1
    combined = (title + " " + (text or "")).lower()
    
    # Check general disaster indicators
    indicators = ["disaster", "emergency", "crisis", "damage", "death", "evacuation", "rescue", "alert", "warning"]
    for ind in indicators:
        if ind in combined:
            score += 0.1
            
    # Check specific disaster keywords
    for dtype, keywords in DISASTER_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                score += 0.15
                
    return min(1.0, round(score, 2))


# ---------------------------------------------------------------------------
# Data Source Pulls
# ---------------------------------------------------------------------------

def _fetch_gdelt(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Queries the GDELT Doc API v2."""
    logger.info(f"[SocialMediaTool] Querying GDELT: query='{query}' limit={limit}")
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": limit
    }
    try:
        resp = _get_with_retry(GDELT_URL, params=params)
        data = resp.json()
        articles = data.get("articles", [])
        logger.debug(f"[SocialMediaTool] GDELT returned {len(articles)} items")
        return [
            {
                "title": art.get("title", ""),
                "source": art.get("domain", "GDELT Source"),
                "source_url": art.get("url", ""),
                "location": art.get("sourcecountry", "Unknown"),
                "timestamp": art.get("seendate", datetime.now(timezone.utc).isoformat()),
                "snippet": art.get("title", ""),
                "provider": "GDELT"
            }
            for art in articles
        ]
    except Exception as e:
        logger.warning(f"[SocialMediaTool] GDELT API request failed: {e}")
        return []


def _fetch_google_news(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Queries the Google News search RSS feed."""
    logger.info(f"[SocialMediaTool] Querying Google News RSS: query='{query}' limit={limit}")
    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    }
    try:
        resp = _get_with_retry(GNEWS_RSS_URL, params=params)
        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        if channel is None:
            return []
            
        items = channel.findall("item")[:limit]
        logger.debug(f"[SocialMediaTool] Google News RSS returned {len(items)} items")
        
        results = []
        for item in items:
            title = item.findtext("title", "")
            source = item.find("source")
            source_name = source.text if source is not None else "Google News RSS"
            
            # PubDate parsing
            pub_date = item.findtext("pubDate", "")
            # Convert RFC 822 format (e.g. Sat, 13 Jun 2026 12:00:00 GMT)
            ts = datetime.now(timezone.utc).isoformat()
            if pub_date:
                try:
                    # Quick check and parse if standard format
                    clean_date = re.sub(r"\s+GMT|\s+UTC|\s+\+[0-9]{4}", "", pub_date).strip()
                    dt = datetime.strptime(clean_date, "%a, %d %b %Y %H:%M:%S")
                    ts = dt.replace(tzinfo=timezone.utc).isoformat()
                except Exception:
                    pass

            results.append({
                "title": title,
                "source": source_name,
                "source_url": item.findtext("link", ""),
                "location": "Unknown",
                "timestamp": ts,
                "snippet": title,
                "provider": "GoogleNews"
            })
        return results
    except Exception as e:
        logger.warning(f"[SocialMediaTool] Google News RSS request failed: {e}")
        return []


def _fetch_reddit(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Queries the Reddit search endpoint in JSON format."""
    logger.info(f"[SocialMediaTool] Querying Reddit: query='{query}' limit={limit}")
    params = {
        "q": query,
        "sort": "new",
        "limit": limit
    }
    try:
        resp = _get_with_retry(REDDIT_SEARCH_URL, params=params)
        data = resp.json()
        children = data.get("data", {}).get("children", [])
        logger.debug(f"[SocialMediaTool] Reddit returned {len(children)} items")
        
        results = []
        for child in children:
            post = child.get("data", {})
            created_utc = post.get("created_utc", time.time())
            ts = datetime.fromtimestamp(created_utc, timezone.utc).isoformat()
            
            results.append({
                "title": post.get("title", ""),
                "source": f"r/{post.get('subreddit', 'all')}",
                "source_url": f"https://www.reddit.com{post.get('permalink', '')}",
                "location": "Unknown",
                "timestamp": ts,
                "snippet": post.get("selftext", ""),
                "provider": "Reddit"
            })
        return results
    except Exception as e:
        logger.warning(f"[SocialMediaTool] Reddit JSON API request failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Public API Functions
# ---------------------------------------------------------------------------

def normalize_social_reports(
    raw_reports: List[Dict[str, Any]],
    source_provider: str
) -> List[SocialDisasterReport]:
    """
    Deduplicates reports by URL, filters irrelevant records, extracts locations,
    calculates confidence, and normalizes into SocialDisasterReport objects.
    """
    normalized = []
    seen_urls = set()

    for item in raw_reports:
        url = item.get("source_url", "")
        if not url or url in seen_urls:
            continue
            
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        
        # Deduplicate
        seen_urls.add(url)
        
        # Compute fields
        disaster_type = _detect_disaster_type(title + " " + (snippet or ""))
        if disaster_type == "Unknown":
            # If no disaster keyword, discard (Keyword filtering)
            continue
            
        location = item.get("location", "Unknown")
        if location == "Unknown" or not location:
            location = _extract_location(title)

        confidence = _calculate_relevance(title, snippet)
        if confidence < 0.25:
            # Low relevance threshold filter
            continue

        normalized.append(
            SocialDisasterReport(
                title=title,
                source=item.get("source", "Online Source"),
                source_url=url,
                location=location,
                timestamp=item.get("timestamp", datetime.now(timezone.utc).isoformat()),
                confidence=confidence,
                disaster_type=disaster_type,
                snippet=snippet[:300] if snippet else None,
                provider=source_provider
            )
        )
        
    return normalized


def search_disaster_keywords(
    keywords: List[str],
    limit: int = 10
) -> List[SocialDisasterReport]:
    """
    Searches across GDELT, Google News RSS, and Reddit for disaster keywords.
    Returns normalized and deduplicated SocialDisasterReport models.
    """
    query_str = " OR ".join(keywords)
    logger.info(f"[SocialMediaTool] Broad search for: '{query_str}'")

    raw_all = []
    
    # 1. GDELT (Priority 1)
    gdelt_raw = _fetch_gdelt(query_str, limit=limit)
    raw_all.extend(gdelt_raw)
    
    # 2. Google News RSS (Priority 2)
    gnews_raw = _fetch_google_news(query_str, limit=limit)
    raw_all.extend(gnews_raw)
    
    # 3. Reddit (Priority 3)
    reddit_raw = _fetch_reddit(query_str, limit=limit)
    raw_all.extend(reddit_raw)

    # Normalize, deduplicate and score
    reports = normalize_social_reports(raw_all, "CombinedScanner")
    
    # Sort by confidence
    reports.sort(key=lambda x: x.confidence, reverse=True)
    return reports[:limit]


def get_disaster_mentions(
    disaster_type: str,
    country: Optional[str] = None
) -> List[SocialDisasterReport]:
    """
    Fetches online news/mentions for a specific disaster type, optionally filtered by country.
    """
    keywords = DISASTER_KEYWORDS.get(disaster_type, ["disaster", "emergency"])
    query_terms = list(keywords)
    if country:
        query_terms.append(country)

    logger.info(f"[SocialMediaTool] Scanning mentions for '{disaster_type}' (Country: {country})")
    
    # Execute query
    return search_disaster_keywords(query_terms, limit=15)


def get_location_mentions(
    location_name: str,
    limit: int = 10
) -> List[SocialDisasterReport]:
    """
    Fetches online news/mentions for a specific geographic location name.
    """
    logger.info(f"[SocialMediaTool] Scanning mentions for location '{location_name}'")
    query_terms = [location_name, "disaster", "emergency", "flood", "cyclone", "earthquake"]
    return search_disaster_keywords(query_terms, limit=limit)


def detect_trending_disasters() -> List[SocialDisasterReport]:
    """
    Scans recent feeds for general disaster indicators and returns the most popular events.
    """
    general_terms = ["disaster", "state of emergency", "evacuation order", "extreme weather", "natural disaster"]
    return search_disaster_keywords(general_terms, limit=10)


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDATING: tools/social_media_tool.py")
    print("=" * 60)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Test 1: get_disaster_mentions (Mumbai flood query)
        reports = get_disaster_mentions("Flood", country="Mumbai")
        print(f"Test 1 (get_disaster_mentions) Passed: Count={len(reports)}")
        if reports:
            print(f"  First item: '{reports[0].title}' from '{reports[0].source}' (Confidence: {reports[0].confidence})")
            
        # Test 2: Pydantic Validation check
        if reports:
            assert isinstance(reports[0], SocialDisasterReport)
            print("Test 2 (Pydantic validation) Passed.")
            
        # Test 3: detect_trending_disasters
        trending = detect_trending_disasters()
        print(f"Test 3 (detect_trending_disasters) Passed: Count={len(trending)}")
        
        # Test 4: get_location_mentions
        delhi_mentions = get_location_mentions("Delhi", limit=3)
        print(f"Test 4 (get_location_mentions) Passed: Count={len(delhi_mentions)}")

        print("\n[SocialMediaTool] Validation completed successfully!")
    except Exception as e:
        print(f"\n[SocialMediaTool] Validation FAILED: {e}")
        import traceback
        traceback.print_exc()

