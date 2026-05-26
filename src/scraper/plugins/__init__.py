"""
Scraper plugins module.
Auto-discovers and registers all scraper implementations.
"""
from src.scraper.plugins.mercado_livre import MercadoLivreScraper
from src.scraper.plugins.dealers import DealersScraper, DEALER_CONFIGS

# Registry de scrapers disponíveis
SCRAPER_REGISTRY = {
    'mercado_livre': MercadoLivreScraper,
    'dealers': DealersScraper,
}

__all__ = ['SCRAPER_REGISTRY', 'MercadoLivreScraper', 'DealersScraper', 'DEALER_CONFIGS']
