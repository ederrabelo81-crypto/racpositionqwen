"""
Scraper do Mercado Livre.
Extrai produtos orgânicos e patrocinados com detecção de layout Poly/legado.
"""
from typing import AsyncIterator, List, Dict, Any, Optional
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.scraper.base import BaseScraper, ProductRecord, PlatformType


class MercadoLivreScraper(BaseScraper):
    """
    Scraper especializado para Mercado Livre.
    
    Features:
    - Detecção automática de layout (Poly vs legado)
    - Distinção entre orgânico e patrocinado
    - Extração de preço fragmentado (fraction + cents)
    - Detecção de login gate
    - Paginação por offset (_Desde_)
    """
    
    # Seletores em cadeia com fallback (resiliência a mudanças de layout)
    PRODUCT_SELECTORS = [
        # Layout Poly (mais recente)
        'li.ui-search-layout__item',
        # Layout legado
        '.ui-search-result',
        '.ais-Hits-item',
        # Fallback genérico
        '[data-component="card"]',
    ]
    
    TITLE_SELECTORS = [
        'h2.ui-search-letter h2',
        'h2.ui-search-title',
        '.ui-search-title__text',
        'a.ui-search-link',
    ]
    
    PRICE_FRACTION_SELECTORS = [
        'span.andes-money-amount--fraction',
        '.andes-money-amount__fraction',
        '[class*="money-amount-fraction"]',
    ]
    
    PRICE_CENTS_SELECTORS = [
        'span.andes-money-amount--cents',
        '.andes-money-amount__cents',
        '[class*="money-amount-cents"]',
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_offset = 0
        self._items_per_page = 48
    
    @property
    def platform_name(self) -> str:
        return "Mercado Livre"
    
    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.MERCADO_LIVRE
    
    def _build_search_url(self, keyword: str, page: int = 0) -> str:
        """Constrói URL de busca do ML"""
        base_url = "https://lista.mercadolivre.com.br"
        
        if page == 0:
            return f"{base_url}/{keyword.replace(' ', '-')}"
        else:
            offset = page * self._items_per_page
            return f"{base_url}/{keyword.replace(' ', '-')}_{self._items_per_page}_Desde_{offset}"
    
    async def search(
        self,
        keyword: str,
        max_pages: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[ProductRecord]:
        """
        Busca produtos no Mercado Livre.
        
        Args:
            keyword: Termo de busca
            max_pages: Máximo de páginas (default: config.MAX_PAGES)
            
        Yields:
            ProductRecord para cada produto
        """
        max_pages = max_pages or self.config.MAX_PAGES
        
        for page in range(max_pages):
            url = self._build_search_url(keyword, page)
            logger.info(f"Scraping ML page {page + 1}/{max_pages}: {url}")
            
            try:
                products = await self._scrape_page(url, keyword)
                
                if not products:
                    logger.warning(f"No products found on page {page + 1}, stopping pagination")
                    break
                
                for product in products:
                    yield product
                
                await self._random_delay()
                
            except Exception as e:
                logger.error(f"Error scraping ML page {page}: {e}")
                screenshot = await self._capture_screenshot("ml_error")
                if screenshot:
                    logger.error(f"Screenshot saved: {screenshot}")
                break
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _scrape_page(self, url: str, keyword: str) -> List[ProductRecord]:
        """
        Scrape uma página específica com retry automático.
        
        Returns:
            Lista de ProductRecord encontrados
        """
        if not self._page:
            raise RuntimeError("Browser not initialized")
        
        # Navega para a página
        await self._page.goto(url, timeout=self.config.PAGE_TIMEOUT, wait_until='domcontentloaded')
        await self._wait_for_network_idle()
        
        # Verifica login gate
        if await self._check_login_gate():
            logger.warning("Login gate detected on ML")
            return []
        
        # Aguarda produtos carregarem (selector chain)
        selector_used = await self._wait_for_selector_chain(
            self.PRODUCT_SELECTORS,
            timeout=10000,
            state="attached"
        )
        
        if not selector_used:
            logger.warning("No product selectors found")
            return []
        
        # Parseia HTML
        html = await self._page.content()
        soup = BeautifulSoup(html, 'lxml')
        
        products = []
        
        # Encontra todos os itens usando o selector que funcionou
        items = soup.select(selector_used)
        logger.debug(f"Found {len(items)} product items using selector: {selector_used}")
        
        for item in items:
            try:
                product_data = self._extract_product(item, url)
                if product_data and product_data.get('price', 0) > 0:
                    record = self._build_record(
                        data=product_data,
                        url=product_data.get('url', url),
                        extraction_method="dom",
                        selector_used=selector_used
                    )
                    products.append(record)
            except Exception as e:
                logger.debug(f"Failed to extract product: {e}")
                continue
        
        logger.info(f"Extracted {len(products)} products from ML page")
        return products
    
    def _extract_product(self, item, base_url: str) -> Optional[Dict[str, Any]]:
        """Extrai dados de um único produto"""
        
        # Detecta se é patrocinado
        is_sponsored = bool(item.select_one('[data-label="publicity"]')) or \
                      bool(item.select_one('.ui-search-layout__item--ad'))
        
        # Extrai título
        title_elem = None
        for selector in self.TITLE_SELECTORS:
            title_elem = item.select_one(selector)
            if title_elem:
                break
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        url = title_elem.get('href', '')
        
        if not url:
            return None
        
        # Completa URL se relativo
        if url.startswith('/'):
            url = f"https://www.mercadolivre.com.br{url}"
        
        # Extrai preço
        price = self._extract_price(item)
        
        # Extrai seller info
        seller_elem = item.select_one('.ui-search-profile__description, .ui-search-result__seller')
        seller_name = seller_elem.get_text(strip=True) if seller_elem else None
        
        # Extrai rating
        rating_elem = item.select_one('.ui-search-reviews')
        rating = None
        reviews_count = None
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            # Parse "(123)" ou "4.5"
            if '(' in rating_text and ')' in rating_text:
                try:
                    reviews_count = int(rating_text.split('(')[1].split(')')[0])
                except:
                    pass
        
        # Extrai marca do título (heurística)
        brand = self._extract_brand(title)
        
        # Extrai capacidade (BTUs)
        capacity = self._extract_capacity(title)
        
        # Verifica se é Full
        is_full = bool(item.select_one('[data-label="full"]')) or \
                 bool(item.select_one('.ui-search-layout__full-icon'))
        
        return {
            'name': title,
            'url': url,
            'price': price,
            'brand': brand,
            'capacity': capacity,
            'seller_name': seller_name,
            'rating': rating,
            'reviews_count': reviews_count,
            'is_sponsored': is_sponsored,
            'is_fulfilled_by_platform': is_full,
        }
    
    def _extract_price(self, item) -> float:
        """Extrai preço fragmentado do ML"""
        try:
            # Tenta encontrar preço principal
            price_container = item.select_one('.andes-money-amount, .ui-search-price')
            
            if not price_container:
                return 0.0
            
            # Extrai parte inteira
            fraction_elem = None
            for selector in self.PRICE_FRACTION_SELECTORS:
                fraction_elem = price_container.select_one(selector)
                if fraction_elem:
                    break
            
            # Extrai centavos
            cents_elem = None
            for selector in self.PRICE_CENTS_SELECTORS:
                cents_elem = price_container.select_one(selector)
                if cents_elem:
                    break
            
            fraction = fraction_elem.get_text(strip=True) if fraction_elem else "0"
            cents = cents_elem.get_text(strip=True) if cents_elem else "00"
            
            # Limpa formatação
            fraction = fraction.replace('.', '').replace(',', '')
            cents = cents.ljust(2, '0')[:2]  # Garante 2 dígitos
            
            price = float(f"{fraction}.{cents}")
            return price
            
        except Exception as e:
            logger.debug(f"Failed to extract price: {e}")
            return 0.0
    
    def _extract_brand(self, title: str) -> Optional[str]:
        """Extrai marca do título usando heurística"""
        brands = ['LG', 'Samsung', 'Springer', 'Midea', 'Gree', 'Elgin', 
                  'Fujitsu', 'Daikin', 'Philco', 'Electrolux', 'Bosch']
        
        title_upper = title.upper()
        for brand in brands:
            if brand.upper() in title_upper:
                return brand
        
        return None
    
    def _extract_capacity(self, title: str) -> Optional[str]:
        """Extrai capacidade em BTUs do título"""
        import re
        
        # Padrões comuns: "9000 btus", "12000 btu/h", "18000"
        patterns = [
            r'(\d{4,5})\s*btu',
            r'(\d{4,5})\s*btaus?',
            r'(\d{2,3})\.?\d{2,3}\s*btu',  # "12.000 btu"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return f"{match.group(1)} BTUs"
        
        return None
    
    async def _check_login_gate(self) -> bool:
        """Verifica se página exige login"""
        if not self._page:
            return False
        
        try:
            login_indicators = [
                'login.mercadolivre.com.br',
                'Faça seu login',
                'Entrar na conta',
            ]
            
            current_url = self._page.url
            if any(indicator in current_url for indicator in login_indicators):
                return True
            
            # Verifica elemento de login na página
            login_elem = await self._page.wait_for_selector(
                'a[href*="login"], button[data-testid="login-button"]',
                timeout=3000
            )
            return login_elem is not None
            
        except:
            return False
