from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import feedparser

from utils.logging import logger

# Optional RAG stack (Chroma + sentence-transformers)
_CHROMA_CLIENT = None
_EMBEDDING_MODEL = None
_RAG_COLLECTION_NAME = "market_news"
_RAG_PERSIST_DIR: Optional[Path] = None


def _get_rag_persist_dir() -> Path:
    global _RAG_PERSIST_DIR
    if _RAG_PERSIST_DIR is None:
        _RAG_PERSIST_DIR = Path(__file__).resolve().parent.parent / "data" / "chroma_news"
        _RAG_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return _RAG_PERSIST_DIR


def _init_rag():
    """Lazy init of Chroma client and embedding model. Returns True if both available."""
    global _CHROMA_CLIENT, _EMBEDDING_MODEL
    if _CHROMA_CLIENT is not None and _EMBEDDING_MODEL is not None:
        return True
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer

        persist_dir = str(_get_rag_persist_dir())
        _CHROMA_CLIENT = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        return True
    except Exception as exc:
        logger.debug(f"RAG init skipped: {exc}")
        return False


def _fetch_rss_corpus(max_items_per_feed: int = 50) -> List[dict]:
    """Fetch recent items from market RSS feeds for indexing (no symbol filter)."""
    feeds = [
        "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
        "https://www.moneycontrol.com/rss/MCtopnews.xml",
    ]
    items: List[dict] = []
    seen_links: set = set()

    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:max_items_per_feed]:
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                link = getattr(entry, "link", "")
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                text = f"{title} {summary}".strip()
                if not text:
                    continue
                items.append({"id": link, "text": text, "title": title, "link": link})
        except Exception as exc:
            logger.exception(f"Failed to parse RSS feed {url}: {exc}")

    return items


def _ensure_rag_collection():
    """Create or get collection; optionally backfill from RSS if empty."""
    if not _init_rag():
        return None
    coll = _CHROMA_CLIENT.get_or_create_collection(
        name=_RAG_COLLECTION_NAME,
        metadata={"description": "Market news for RAG"},
    )
    if coll.count() == 0:
        corpus = _fetch_rss_corpus(max_items_per_feed=80)
        if not corpus:
            return coll
        ids = [c["id"] for c in corpus]
        texts = [c["text"] for c in corpus]
        embeddings = _EMBEDDING_MODEL.encode(texts).tolist()
        coll.add(ids=ids, embeddings=embeddings, documents=texts)
        logger.info(f"RAG: indexed {len(corpus)} news items into Chroma.")
    return coll


def get_symbol_news_summaries(symbol: str, top_k: int = 5) -> List[str]:
    """
    Return news summaries relevant to the symbol.
    Priority:
    1. yfinance news (most relevant, real-time)
    2. Chroma + sentence-transformers RAG (when available)
    3. RSS keyword filter fallback
    """
    bare = symbol.split(".")[0].upper()  # Strip .NS / .BO if present

    # 1. Try yfinance news first — most direct and relevant
    yf_items = _fetch_yfinance_news(bare, max_items=top_k)
    if yf_items:
        return [f"**{i.title}** — {i.summary}" if i.summary else i.title for i in yf_items]

    # 2. Try RAG if available
    query = f"{bare} stock share price market news India"
    coll = _ensure_rag_collection()
    if coll is not None and _EMBEDDING_MODEL is not None:
        try:
            q_emb = _EMBEDDING_MODEL.encode([query]).tolist()
            n = min(top_k, coll.count())
            if n > 0:
                results = coll.query(
                    query_embeddings=q_emb,
                    n_results=n,
                    include=["documents"],
                )
                if results and results["documents"] and results["documents"][0]:
                    return list(results["documents"][0])
        except Exception as exc:
            logger.warning(f"RAG query failed, falling back to RSS: {exc}")

    # 3. Keyword-based RSS fallback
    rss_items = _fetch_rss_keyword_items(bare, max_items=top_k)
    if rss_items:
        return [f"**{i.title}** — {i.summary}" if i.summary else i.title for i in rss_items]

    return []


@dataclass
class NewsItem:
    title: str
    summary: str
    link: str


def _fetch_yfinance_news(symbol: str, max_items: int = 5) -> List[NewsItem]:
    """
    Fetch news directly from Yahoo Finance for the specific stock symbol.
    Handles the yfinance >= 0.2.x news data structure.
    """
    items: List[NewsItem] = []
    try:
        import yfinance as yf
        # Try with .NS suffix first for Indian stocks, then bare symbol
        for sym in [f"{symbol}.NS", f"{symbol}.BO", symbol]:
            try:
                ticker = yf.Ticker(sym)
                news_data = ticker.news
                if not news_data:
                    continue
                for n in news_data[:max_items]:
                    # yfinance >= 0.2.x wraps content under 'content' key
                    if isinstance(n, dict):
                        content = n.get("content", n)
                        if isinstance(content, dict):
                            title = content.get("title", n.get("title", ""))
                            summary = content.get("summary", content.get("description", ""))
                            link = (
                                content.get("canonicalUrl", {}).get("url", "")
                                or n.get("link", "")
                            )
                        else:
                            title = n.get("title", "")
                            summary = n.get("publisher", "")
                            link = n.get("link", "")
                        if title:
                            items.append(NewsItem(title=title, summary=summary, link=link))
                if items:
                    break
            except Exception:
                continue
    except Exception as exc:
        logger.exception(f"Failed to fetch yfinance news for {symbol}: {exc}")
    return items


def _fetch_rss_keyword_items(symbol: str, max_items: int = 5) -> List[NewsItem]:
    """
    Keyword-filtered fallback: fetch RSS feeds and return items mentioning the symbol.
    """
    feeds = [
        "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
        "https://www.moneycontrol.com/rss/MCtopnews.xml",
    ]
    items: List[NewsItem] = []
    sym_lower = symbol.lower()

    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries:
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                link = getattr(entry, "link", "")
                text = f"{title} {summary}".lower()
                if sym_lower in text:
                    items.append(NewsItem(title=title, summary=summary, link=link))
                    if len(items) >= max_items:
                        return items
        except Exception as exc:
            logger.exception(f"RSS fallback failed for {url}: {exc}")

    return items
