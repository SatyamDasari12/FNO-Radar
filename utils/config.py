import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass
class GroqConfig:
    api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    # llama3-8b-8192 was decommissioned Aug 2025. Current production replacements:
    #   llama-3.3-70b-versatile  (best quality, recommended)
    #   llama-3.1-8b-instant     (fastest, lower cost)
    model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    temperature: float = float(os.getenv("GROQ_TEMPERATURE", "0.2"))


@dataclass
class NewsConfig:
    api_key: Optional[str] = os.getenv("NEWS_API_KEY")
    provider: str = os.getenv("NEWS_PROVIDER", "newsapi")  # or rss


@dataclass
class AppConfig:
    groq: GroqConfig = field(default_factory=GroqConfig)
    news: NewsConfig = field(default_factory=NewsConfig)


def get_app_config() -> AppConfig:
    return AppConfig()

