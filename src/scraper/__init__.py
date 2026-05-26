"""
Scraper package.
Sistema de scraping baseado em plugins com browser pool.
"""
from src.scraper.base import BaseScraper, ProductRecord, PlatformType
from src.scraper.plugins import SCRAPER_REGISTRY

__all__ = ['BaseScraper', 'ProductRecord', 'PlatformType', 'SCRAPER_REGISTRY']
