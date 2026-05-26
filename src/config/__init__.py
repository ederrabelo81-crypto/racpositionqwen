"""
Configuration module.
Settings, keywords, and dealer configs.
"""
from src.config.settings import (
    get_scraper_config,
    get_supabase_config,
    get_telegram_config,
    get_claude_config,
    ScraperConfig,
    SupabaseConfig,
    TelegramConfig,
    ClaudeConfig,
    PriorityLevel,
)
from src.config.keywords import KeywordsManager, KeywordConfig

__all__ = [
    'get_scraper_config',
    'get_supabase_config',
    'get_telegram_config',
    'get_claude_config',
    'ScraperConfig',
    'SupabaseConfig',
    'TelegramConfig',
    'ClaudeConfig',
    'PriorityLevel',
    'KeywordsManager',
    'KeywordConfig',
]
