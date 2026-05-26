"""
Browser pool module.
Reutilização de browsers para melhor performance.
"""
from src.scraper.pool.browser_pool import BrowserPool, get_browser_pool, BrowserWrapper

__all__ = ['BrowserPool', 'get_browser_pool', 'BrowserWrapper']
