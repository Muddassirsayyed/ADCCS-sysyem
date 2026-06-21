"""
ADCC — News Tool
=================
Fetches disaster-related news articles from trusted sources.

Primary:  NewsAPI   (https://newsapi.org) — requires NEWS_API_KEY in .env
Fallback: Google News RSS (https://news.google.com/rss) — free, no key needed

Used by (future):
    - verification_agent.py → finds news evidence to confirm disaster reports
    - data_collection_agent.py → collects news alongside GDACS/USGS data
    - confidence_engine.py → uses news count to compute confidence score

Functions:
    get_disaster_news(query, country, days)   → NewsResponse
    get_news_by_country(country, days)         → NewsResponse
    get_news_by_keyword(keyword, days)         → NewsResponse
"""

import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

import requests
from loguru import logger
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEWSAPI_URL   = "https://newsapi.org/v2/everything"
GNEWS_RSS_URL = "https://news.google.com/rss/search"

TIMEOUT     = 12
MAX_RETRIES = 3
RETRY_DELAY = 2

# Keywords used to detect disaster type from headlines
DISASTER_KEYWORDS: dict[str, list[str]] = {
    "Flood":      ["flood", "flooding", "inundation", "deluge", "waterlogging", "flash flood"],
    "Cyclone":    ["cyclone", "hurricane", "typhoon", "tropical storm", "landfall"],
    "Earthquake": ["earthquake", "quake", "tremor", "seismic", "richter", "aftershock"],
    "Wildfire":   ["wildfire", "forest fire", "bushfire", "blaze", "inferno"],
    "Landslide":  ["landslide", "mudslide", "rockslide", "landfall", "debris flow"],
    "Heatwave":   ["heatwave", "heat wave", "extreme heat", "temperature record"],
    "Tsunami":    ["tsunami", "tidal wave"],
    "Drought":    ["drought", "water scarcity", "dry spell"],
}

# General disaster search keywords for broad queries
DISASTER_SEARCH_TERMS = (
    "flood OR cyclone OR earthquake OR disaster OR emergency "
    "OR landslide OR wildfire OR tsunami OR heatwave"
)


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================


class NewsArticle(BaseModel):
    """Normalized news article record."""

    title: str = Field(..., description="Article headline")
    source: str = Field(..., description="Publisher name")
    source_type: str = Field("NewsAPI", description="Which API provided this article")
    country: str = Field("Unknown", description="Country mentioned or inferred")
    published_at: str = Field(..., description="ISO 8601 publish timestamp")
    url: str = Field(..., description="Full article URL")
    description: Optional[str] = Field(None, description="Article summary/snippet")
    disaster_type: Optional[str] = Field(
        None,
        description="Detected disaster type from keywords: Flood, Cyclone, Earthquake, etc."
    )
    relevance_score: float = Field(
        0.0,
        description="0.0–1.0 relevance to the search query (keyword match count)"
    )

    class Config:
        from_attributes = True


class NewsResponse(BaseModel):
    """Container for a news query result."""

    query: str
    country: Optional[str]
    total_fetched: int
    unique_articles: int = Field(..., description="After deduplication by URL")
    articles: list[NewsArticle]
    source_used: str = Field(..., description="'NewsAPI' or 'Google News RSS'")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================


def _get_with_retry(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> requests.Response:
    """HTTP GET with exponential backoff retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(f"[NewsTool] GET attempt {attempt}/{MAX_RETRIES} → {url}")
            resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("[NewsTool] 401 Unauthorized — check NEWS_API_KEY in .env")
                raise
            if e.response.status_code == 429:
                logger.warning(f"[NewsTool] 429 Rate limited on attempt {attempt}")
            else:
                logger.error(f"[NewsTool] HTTP {e.response.status_code}: {e}")
                raise
        except requests.exceptions.Timeout:
            logger.warning(f"[NewsTool] Timeout on attempt {attempt}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"[NewsTool] Connection error on attempt {attempt}")
        except Exception as e:
            logger.error(f"[NewsTool] Unexpected error: {e}")
            raise

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            logger.info(f"[NewsTool] Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"[NewsTool] All {MAX_RETRIES} retries failed for {url}")


def _detect_disaster_type(text: str) -> Optional[str]:
    """
    Detects disaster type from article title/description using keyword matching.
    Returns the first matched disaster type, or None.
    """
    text_lower = text.lower()
    for disaster_type, keywords in DISASTER_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return disaster_type
    return None


def _compute_relevance(text: str, query_terms: list[str]) -> float:
    """
    Computes a simple relevance score based on how many query terms appear in text.
    Returns 0.0–1.0.
    """
    if not query_terms:
        return 0.5
    text_lower = text.lower()
    matched = sum(1 for term in query_terms if term.lower() in text_lower)
    return round(min(matched / len(query_terms), 1.0), 3)


def _deduplicate(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Removes duplicate articles by URL (case-insensitive). Preserves order."""
    seen_urls: set[str] = set()
    unique: list[NewsArticle] = []
    for article in articles:
        url_key = article.url.strip().lower()
        if url_key not in seen_urls:
            seen_urls.add(url_key)
            unique.append(article)
    return unique


def _days_to_from_date(days: int) -> str:
    """Returns ISO date string N days ago (for NewsAPI 'from' param)."""
    from_dt = datetime.now(timezone.utc) - timedelta(days=days)
    return from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ===========================================================================
# NEWSAPI (Primary)
# ===========================================================================


def _fetch_from_newsapi(
    query: str,
    country: Optional[str],
    days: int,
    api_key: str,
    limit: int = 30,
) -> list[NewsArticle]:
    """
    Fetches articles from NewsAPI v2 /everything endpoint.
    Returns list of NewsArticle or empty list on error.
    """
    params = {
        "q":        query,
        "language": "en",
        "sortBy":   "publishedAt",
        "pageSize": min(limit, 100),
        "from":     _days_to_from_date(days),
        "apiKey":   api_key,
    }

    logger.debug(f"[NewsTool] NewsAPI query='{query}' from={params['from']}")

    try:
        resp = _get_with_retry(NEWSAPI_URL, params=params)
        data = resp.json()

        if data.get("status") != "ok":
            logger.warning(f"[NewsTool] NewsAPI non-ok status: {data.get('message')}")
            return []

        raw_articles = data.get("articles", [])
        query_terms = query.lower().split()

        articles: list[NewsArticle] = []
        for raw in raw_articles:
            title       = raw.get("title") or ""
            description = raw.get("description") or ""
            url         = raw.get("url") or ""
            published   = raw.get("publishedAt") or datetime.now(timezone.utc).isoformat()
            source_name = (raw.get("source") or {}).get("name", "Unknown")

            if not title or not url or title == "[Removed]":
                continue

            combined_text  = f"{title} {description}"
            disaster_type  = _detect_disaster_type(combined_text)
            relevance      = _compute_relevance(combined_text, query_terms)

            # Country inference: check if country name appears in text
            inferred_country = country or "Global"
            if country and country.lower() not in combined_text.lower():
                inferred_country = "Global"

            articles.append(NewsArticle(
                title=title.strip(),
                source=source_name,
                source_type="NewsAPI",
                country=inferred_country,
                published_at=published,
                url=url,
                description=description[:300] if description else None,
                disaster_type=disaster_type,
                relevance_score=relevance,
            ))

        logger.info(f"[NewsTool] NewsAPI returned {len(articles)} articles")
        return articles

    except Exception as e:
        logger.error(f"[NewsTool] NewsAPI fetch failed: {e}")
        return []


# ===========================================================================
# GOOGLE NEWS RSS (Fallback)
# ===========================================================================


def _fetch_from_google_rss(
    query: str,
    country: Optional[str],
    limit: int = 20,
) -> list[NewsArticle]:
    """
    Fallback: Fetches from Google News RSS feed.
    Free, no API key needed.
    """
    rss_query = query.replace(" OR ", " | ")
    params = {
        "q":    rss_query,
        "hl":   "en-IN" if (country or "").lower() == "india" else "en",
        "gl":   "IN" if (country or "").lower() == "india" else "US",
        "ceid": "IN:en" if (country or "").lower() == "india" else "US:en",
    }

    logger.info(f"[NewsTool] Falling back to Google News RSS for query='{query}'")

    try:
        resp = _get_with_retry(GNEWS_RSS_URL, params=params)
        root = ET.fromstring(resp.text)
        channel = root.find("channel")

        if channel is None:
            logger.warning("[NewsTool] Google RSS: no channel found in XML")
            return []

        items = channel.findall("item")[:limit]
        query_terms = query.lower().split()
        articles: list[NewsArticle] = []

        for item in items:
            title    = item.findtext("title", "")
            link     = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source_el = item.find("{https://news.google.com/}source") or item.find("source")
            source_name = source_el.text if source_el is not None and source_el.text else "Google News"

            if not title or not link:
                continue

            # Parse pubDate to ISO
            try:
                pub_dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                pub_iso = pub_dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pub_iso = datetime.now(timezone.utc).isoformat()

            disaster_type = _detect_disaster_type(title)
            relevance     = _compute_relevance(title, query_terms)

            articles.append(NewsArticle(
                title=title.strip(),
                source=source_name,
                source_type="Google News RSS",
                country=country or "Global",
                published_at=pub_iso,
                url=link,
                description=None,
                disaster_type=disaster_type,
                relevance_score=relevance,
            ))

        logger.info(f"[NewsTool] Google News RSS returned {len(articles)} articles")
        return articles

    except ET.ParseError as e:
        logger.error(f"[NewsTool] RSS XML parse error: {e}")
        return []
    except Exception as e:
        logger.error(f"[NewsTool] Google News RSS fetch failed: {e}")
        return []


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================


def get_disaster_news(
    query: Optional[str] = None,
    country: Optional[str] = "India",
    days: int = 7,
    limit: int = 30,
    disaster_types_filter: Optional[list[str]] = None,
) -> NewsResponse:
    """
    Fetches disaster-related news with automatic API fallback.

    Strategy:
        1. Try NewsAPI (if NEWS_API_KEY set in .env)
        2. Fall back to Google News RSS (always free)

    Args:
        query:                 Custom search query. Default: general disaster terms
        country:               Country filter for context (e.g. "India")
        days:                  Look-back window in days (default 7)
        limit:                 Max articles to return (default 30)
        disaster_types_filter: Optional list to filter by detected type
                               (e.g. ["Flood", "Cyclone"])

    Returns:
        NewsResponse: Deduplicated, normalized list of NewsArticle

    Example:
        >>> result = get_disaster_news(country="India", days=3)
        >>> for art in result.articles:
        ...     print(art.title, art.disaster_type)
    """
    if query is None:
        query = DISASTER_SEARCH_TERMS
        if country:
            query = f"{country} ({query})"

    logger.info(f"[NewsTool] Fetching disaster news | query='{query[:60]}...' | country={country} | days={days}")
    t_start = time.monotonic()

    api_key = os.getenv("NEWS_API_KEY", "")
    articles: list[NewsArticle] = []
    source_used = "Google News RSS"

    # Primary: NewsAPI
    if api_key and api_key != "your_newsapi_key_here":
        articles = _fetch_from_newsapi(query=query, country=country, days=days, api_key=api_key, limit=limit)
        if articles:
            source_used = "NewsAPI"

    # Fallback: Google News RSS
    if not articles:
        if api_key and api_key != "your_newsapi_key_here":
            logger.warning("[NewsTool] NewsAPI returned 0 articles, switching to RSS fallback")
        else:
            logger.info("[NewsTool] NEWS_API_KEY not set — using Google News RSS directly")

        articles = _fetch_from_google_rss(query=query, country=country, limit=limit)

    # Apply disaster type filter
    if disaster_types_filter:
        articles = [
            a for a in articles
            if a.disaster_type in disaster_types_filter
        ]
        logger.debug(f"[NewsTool] After type filter {disaster_types_filter}: {len(articles)} articles remain")

    # Deduplicate
    before_dedup = len(articles)
    articles = _deduplicate(articles)

    # Sort by relevance (desc)
    articles.sort(key=lambda a: a.relevance_score, reverse=True)

    elapsed = round(time.monotonic() - t_start, 2)
    logger.success(
        f"[NewsTool] ✅ Fetched in {elapsed}s | "
        f"Raw={before_dedup} | Unique={len(articles)} | Source={source_used}"
    )

    return NewsResponse(
        query=query,
        country=country,
        total_fetched=before_dedup,
        unique_articles=len(articles),
        articles=articles,
        source_used=source_used,
    )


def get_news_by_country(
    country: str,
    days: int = 7,
    limit: int = 20,
) -> NewsResponse:
    """
    Fetches disaster news specifically for a country.

    Args:
        country: Country name (e.g. "India", "Bangladesh", "Nepal")
        days:    Look-back window (default 7)
        limit:   Max articles (default 20)

    Returns:
        NewsResponse

    Example:
        >>> result = get_news_by_country("India", days=3)
        >>> print(result.unique_articles)
    """
    logger.info(f"[NewsTool] Fetching news by country='{country}'")
    query = f"{country} disaster OR flood OR cyclone OR earthquake OR emergency"
    return get_disaster_news(query=query, country=country, days=days, limit=limit)


def get_news_by_keyword(
    keyword: str,
    country: Optional[str] = None,
    days: int = 7,
    limit: int = 20,
) -> NewsResponse:
    """
    Fetches news for a specific keyword or event title.
    Used by verification_agent to find news evidence for a specific event.

    Args:
        keyword: Search term (e.g. "Mumbai flood", "Gujarat earthquake")
        country: Optional country context
        days:    Look-back window (default 7)
        limit:   Max articles (default 20)

    Returns:
        NewsResponse

    Example:
        >>> result = get_news_by_keyword("Mumbai coastal flooding", country="India")
        >>> print(result.articles[0].title)
    """
    logger.info(f"[NewsTool] Fetching news by keyword='{keyword}'")
    return get_disaster_news(query=keyword, country=country, days=days, limit=limit)
