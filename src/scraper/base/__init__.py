"""
Base module for scrapers.
Exports base scraper class and models.
"""
from src.scraper.base.scraper import BaseScraper
from src.scraper.base.models import ProductRecord, PlatformType

__all__ = ['BaseScraper', 'ProductRecord', 'PlatformType']
