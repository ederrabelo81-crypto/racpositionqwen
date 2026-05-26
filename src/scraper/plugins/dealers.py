"""
Scraper de dealers especializados.
Suporta múltiplas plataformas: VTEX, WooCommerce, Oracle Commerce, Next.js
"""
from typing import AsyncIterator, List, Dict, Any, Optional
from bs4 import BeautifulSoup
import json
import re
from loguru import logger

from src.scraper.base import BaseScraper, ProductRecord, PlatformType


class DealerConfig:
    """Configuração de um dealer individual"""
    
    def __init__(
        self,
        name: str,
        base_url: str,
        search_path: str,
        platform_type: str = "generic",
        selectors: Optional[Dict[str, str]] = None,
        pagination_type: str = "param",
        **kwargs
    ):
        self.name = name
        self.base_url = base_url
        self.search_path = search_path
        self.platform_type = platform_type  # vtex, woocommerce, oracle, nextjs, generic
        self.selectors = selectors or {}
        self.pagination_type = pagination_type
        self.extra_config = kwargs
    
    def build_search_url(self, keyword: str, page: int = 0) -> str:
        """Constrói URL de busca específica do dealer"""
        if self.pagination_type == "vtex":
            # VTEX usa _q_ e page
            return f"{self.base_url}{self.search_path}?_q={keyword}&page={page}"
        elif self.pagination_type == "param_zero":
            # some_oracle_commerce usa from=0&to=12
            step = self.extra_config.get('step', 12)
            from_idx = page * step
            to_idx = from_idx + step - 1
            return f"{self.base_url}{self.search_path}?q={keyword}&from={from_idx}&to={to_idx}"
        elif self.pagination_type == "woocommerce":
            # WooCommerce usa query param page
            return f"{self.base_url}{self.search_path}?s={keyword}&paged={page + 1}"
        else:
            # Genérico: apenas adiciona keyword
            return f"{self.base_url}{self.search_path}?q={keyword}"


# Configuração dos principais dealers
DEALER_CONFIGS = {
    'frigelar': DealerConfig(
        name='Frigelar',
        base_url='https://www.frigelar.com.br',
        search_path='/ar-condicionado',
        platform_type='oracle',
        pagination_type='param_zero',
        step=12,
        inject_cep='01310-100',  # CEP para habilitar preços
    ),
    'casarin': DealerConfig(
        name='Casarin',
        base_url='https://www.casarin.com.br',
        search_path='/busca?q=',
        platform_type='vtex',
        pagination_type='vtex',
    ),
    'politec': DealerConfig(
        name='Politec',
        base_url='https://www.politec.com.br',
        search_path='/ar-condicionado',
        platform_type='generic',
    ),
    'refrisom': DealerConfig(
        name='Refrisom',
        base_url='https://www.refrisom.com.br',
        search_path='/ar-condicionado',
        platform_type='woocommerce',
        pagination_type='woocommerce',
    ),
}


class DealersScraper(BaseScraper):
    """
    Scraper multi-dealer com suporte a várias plataformas de e-commerce.
    
    Features:
    - Extração via JSON-LD (prioritário)
    - Fallback para window.RUNTIME / window.__STATE__
    - Fallback final para DOM parsing
    - Debug HTML automático quando 0 produtos
    - CEP injection para dealers Oracle Commerce
    """
    
    @property
    def platform_name(self) -> str:
        return "Dealers"
    
    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.DEALER
    
    async def search(
        self,
        keyword: str,
        dealers: Optional[List[str]] = None,
        max_pages: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[ProductRecord]:
        """
        Busca produtos em múltiplos dealers.
        
        Args:
            keyword: Termo de busca
            dealers: Lista de IDs de dealers (default: todos ativos)
            max_pages: Máximo de páginas por dealer
            
        Yields:
            ProductRecord para cada produto encontrado
        """
        dealers = dealers or list(DEALER_CONFIGS.keys())
        max_pages = max_pages or 3  # Dealers geralmente têm menos páginas
        
        for dealer_id in dealers:
            if dealer_id not in DEALER_CONFIGS:
                logger.warning(f"Unknown dealer: {dealer_id}")
                continue
            
            config = DEALER_CONFIGS[dealer_id]
            logger.info(f"Scraping dealer: {config.name}")
            
            try:
                async for product in self._scrape_dealer(config, keyword, max_pages):
                    yield product
            except Exception as e:
                logger.error(f"Error scraping dealer {config.name}: {e}")
                screenshot = await self._capture_screenshot(f"dealer_{dealer_id}_error")
                continue
    
    async def _scrape_dealer(
        self,
        config: DealerConfig,
        keyword: str,
        max_pages: int
    ) -> AsyncIterator[ProductRecord]:
        """Scrape um dealer específico"""
        
        for page in range(max_pages):
            url = config.build_search_url(keyword, page)
            logger.debug(f"Scraping {config.name} page {page + 1}: {url}")
            
            try:
                products = await self._scrape_page(config, url)
                
                if not products:
                    if page == 0:
                        logger.warning(f"No products found on first page for {config.name}")
                    break
                
                for product in products:
                    yield product
                
                # Se não tem paginação, para após primeira página
                if config.pagination_type == "generic":
                    break
                
                await self._random_delay()
                
            except Exception as e:
                logger.error(f"Error on page {page} for {config.name}: {e}")
                break
    
    async def _scrape_page(self, config: DealerConfig, url: str) -> List[ProductRecord]:
        """Scrape uma página de dealer com múltiplas estratégias"""
        
        if not self._page:
            raise RuntimeError("Browser not initialized")
        
        # Navega para URL
        await self._page.goto(url, timeout=self.config.PAGE_TIMEOUT, wait_until='domcontentloaded')
        await self._wait_for_network_idle()
        
        # Aguarda alguns elementos específicos se configurado
        if config.selectors.get('product_container'):
            try:
                await self._page.wait_for_selector(
                    config.selectors['product_container'],
                    timeout=5000
                )
            except:
                pass  # Continua mesmo sem encontrar
        
        # Estratégia 1: JSON-LD (prioritário)
        products = await self._extract_jsonld(config)
        if products:
            logger.info(f"Extracted {len(products)} products from {config.name} via JSON-LD")
            return products
        
        # Estratégia 2: window.RUNTIME / window.__STATE__ (VTEX/Oracle)
        products = await self._extract_window_state(config)
        if products:
            logger.info(f"Extracted {len(products)} products from {config.name} via window state")
            return products
        
        # Estratégia 3: DOM fallback
        products = await self._extract_dom(config)
        if products:
            logger.info(f"Extracted {len(products)} products from {config.name} via DOM")
            return products
        
        # Debug: salva HTML se 0 produtos
        logger.warning(f"No products extracted from {config.name}, saving debug HTML")
        await self._save_debug_html(config.name, url)
        
        return []
    
    async def _extract_jsonld(self, config: DealerConfig) -> List[ProductRecord]:
        """Extrai produtos via JSON-LD"""
        
        try:
            jsonld_data = await self._page.evaluate('''
                () => {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    const results = [];
                    
                    scripts.forEach(script => {
                        try {
                            const data = JSON.parse(script.textContent);
                            results.push(data);
                        } catch (e) {}
                    });
                    
                    return results;
                }
            ''')
            
            products = []
            
            for data in jsonld_data:
                # Produto individual
                if data.get('@type') == 'Product' or 'Product' in str(data.get('@type', '')):
                    product_data = self._parse_product_jsonld(data, config)
                    if product_data and product_data.get('price', 0) > 0:
                        record = self._build_record(
                            data=product_data,
                            url=product_data.get('url', ''),
                            extraction_method='jsonld',
                            selector_used='application/ld+json'
                        )
                        products.append(record)
                
                # Lista de produtos (ItemList)
                elif data.get('@type') == 'ItemList':
                    for item in data.get('itemListElement', []):
                        if isinstance(item, dict) and 'item' in item:
                            product_data = self._parse_product_jsonld(item['item'], config)
                            if product_data and product_data.get('price', 0) > 0:
                                record = self._build_record(
                                    data=product_data,
                                    url=product_data.get('url', ''),
                                    extraction_method='jsonld',
                                    selector_used='ItemList'
                                )
                                products.append(record)
            
            return products
            
        except Exception as e:
            logger.debug(f"JSON-LD extraction failed for {config.name}: {e}")
            return []
    
    def _parse_product_jsonld(self, data: Dict, config: DealerConfig) -> Optional[Dict[str, Any]]:
        """Parseia objeto JSON-LD de produto"""
        
        try:
            # Nome
            name = data.get('name', '')
            
            # Preço
            price = 0.0
            if 'offers' in data:
                offers = data['offers']
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                
                price_str = offers.get('price', data.get('price', '0'))
                if isinstance(price_str, (int, float)):
                    price = float(price_str)
                else:
                    price = float(str(price_str).replace(',', '.').replace('R$', '').strip())
            
            # URL
            url = data.get('url', '')
            
            # Marca
            brand = None
            if 'brand' in data:
                brand_data = data['brand']
                if isinstance(brand_data, dict):
                    brand = brand_data.get('name')
                else:
                    brand = str(brand_data)
            
            # SKU
            sku = data.get('sku', data.get('productID'))
            
            # Imagem
            image_url = data.get('image')
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else None
            
            # Disponibilidade
            availability = 'in_stock'
            if 'offers' in data and isinstance(data['offers'], dict):
                avail = data['offers'].get('availability', '')
                if 'OutOfStock' in avail:
                    availability = 'out_of_stock'
            
            return {
                'name': name,
                'price': price,
                'url': url,
                'brand': brand,
                'sku': sku,
                'image_url': image_url,
                'availability': availability,
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse JSON-LD product: {e}")
            return None
    
    async def _extract_window_state(self, config: DealerConfig) -> List[ProductRecord]:
        """Extrai produtos de window.RUNTIME ou window.__STATE__"""
        
        try:
            # Tenta diferentes padrões de estado global
            state_data = await self._page.evaluate('''
                () => {
                    // VTEX
                    if (window.__STATE__) {
                        return window.__STATE__;
                    }
                    // Oracle Commerce Cloud
                    if (window.RUNTIME) {
                        return window.RUNTIME;
                    }
                    // Outros
                    if (window.APP_STATE) {
                        return window.APP_STATE;
                    }
                    return null;
                }
            ''')
            
            if not state_data:
                return []
            
            products = []
            
            # Procura por arrays de produtos no estado
            # Estrutura comum: products.items, catalog.products, etc
            for key in ['products', 'items', 'catalog', 'productList']:
                if key in state_data:
                    items = state_data[key]
                    if isinstance(items, dict) and 'items' in items:
                        items = items['items']
                    
                    if isinstance(items, list):
                        for item in items:
                            product_data = self._parse_window_item(item, config)
                            if product_data and product_data.get('price', 0) > 0:
                                record = self._build_record(
                                    data=product_data,
                                    url=product_data.get('url', config.base_url),
                                    extraction_method='window_state',
                                    selector_used=key
                                )
                                products.append(record)
            
            return products
            
        except Exception as e:
            logger.debug(f"Window state extraction failed for {config.name}: {e}")
            return []
    
    def _parse_window_item(self, item: Dict, config: DealerConfig) -> Optional[Dict[str, Any]]:
        """Parseia item de window state"""
        
        try:
            name = item.get('name', item.get('productName', ''))
            price = float(item.get('price', item.get('sellingPrice', 0)))
            
            url = item.get('link', item.get('url', ''))
            if url and url.startswith('/'):
                url = f"{config.base_url}{url}"
            
            brand = item.get('brand', item.get('manufacturer'))
            sku = item.get('sku', item.get('productId', item.get('code')))
            
            image_url = item.get('image', item.get('imageUrl'))
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else None
            
            # Verifica disponibilidade
            availability = 'in_stock'
            if item.get('availability') == 'out_of_stock' or item.get('stock', 1) <= 0:
                availability = 'out_of_stock'
            
            return {
                'name': name,
                'price': price,
                'url': url,
                'brand': brand,
                'sku': sku,
                'image_url': image_url,
                'availability': availability,
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse window item: {e}")
            return None
    
    async def _extract_dom(self, config: DealerConfig) -> List[ProductRecord]:
        """Fallback: extrai via DOM parsing tradicional"""
        
        html = await self._page.content()
        soup = BeautifulSoup(html, 'lxml')
        
        # Usa seletores customizados se disponíveis
        container_selector = config.selectors.get('product_container', '.product-item, .product-card, [data-product]')
        
        items = soup.select(container_selector)
        logger.debug(f"Found {len(items)} DOM items for {config.name}")
        
        products = []
        
        for item in items:
            try:
                # Extrai dados básicos
                title_elem = item.select_one(config.selectors.get('title', 'h3, .product-name, .product-title'))
                price_elem = item.select_one(config.selectors.get('price', '.price, .product-price, [data-price]'))
                link_elem = item.select_one('a[href*="/produto"], a[href*="/p/"]')
                
                if not title_elem or not price_elem:
                    continue
                
                name = title_elem.get_text(strip=True)
                
                # Parseia preço
                price_text = price_elem.get_text(strip=True)
                price = self._parse_price_string(price_text)
                
                if price <= 0:
                    continue
                
                url = link_elem.get('href', '') if link_elem else ''
                if url and url.startswith('/'):
                    url = f"{config.base_url}{url}"
                
                product_data = {
                    'name': name,
                    'price': price,
                    'url': url,
                }
                
                record = self._build_record(
                    data=product_data,
                    url=url or config.base_url,
                    extraction_method='dom',
                    selector_used=container_selector
                )
                products.append(record)
                
            except Exception as e:
                logger.debug(f"Failed to extract DOM product: {e}")
                continue
        
        return products
    
    def _parse_price_string(self, price_text: str) -> float:
        """Parseia string de preço para float"""
        
        try:
            # Remove caracteres indesejados
            clean = re.sub(r'[^\d,.]', '', price_text)
            
            # Detecta formato (1.234,56 vs 1,234.56)
            if ',' in clean and '.' in clean:
                if clean.rfind(',') > clean.rfind('.'):
                    # Formato brasileiro: 1.234,56
                    clean = clean.replace('.', '').replace(',', '.')
                else:
                    # Formato americano: 1,234.56
                    clean = clean.replace(',', '')
            elif ',' in clean:
                # Apenas vírgula: assume brasileiro
                clean = clean.replace(',', '.')
            
            return float(clean)
            
        except:
            return 0.0
    
    async def _save_debug_html(self, dealer_name: str, url: str):
        """Salva HTML para debug"""
        
        try:
            from pathlib import Path
            from datetime import datetime
            
            debug_dir = Path('logs/debug_html')
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"{dealer_name}_{timestamp}.html"
            filepath = debug_dir / filename
            
            html = await self._page.content()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(html)
            
            logger.info(f"Debug HTML saved: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save debug HTML: {e}")
