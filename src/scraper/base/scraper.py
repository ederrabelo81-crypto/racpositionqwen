"""
Classe base abstrata para todos os scrapers.
Define contrato e provê helpers compartilhados.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncIterator
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth.stealth import Stealth
import asyncio
import random
import hashlib
from datetime import datetime
from loguru import logger

from src.config.settings import get_scraper_config, ScraperConfig
from src.scraper.base.models import ProductRecord, PlatformType


async def stealth_async(page, **kwargs):
    """Wrapper compatível com playwright_stealth"""
    stealth = Stealth(**kwargs) if kwargs else Stealth()
    await stealth.apply_stealth_async(page)


class BaseScraper(ABC):
    """
    Classe base para scrapers de plataformas.
    
    Gerencia:
    - Ciclo de vida do Playwright (browser context, stealth)
    - Helpers compartilhados (scroll humano, delay aleatório, network idle wait)
    - Padronização do schema de saída
    - Captura de screenshots opcionais
    """
    
    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or get_scraper_config()
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._collection_id: str = ""
        
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Nome da plataforma (ex: 'Mercado Livre', 'Amazon')"""
        pass
    
    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        """Tipo da plataforma (enum)"""
        pass
    
    @abstractmethod
    async def search(self, keyword: str, **kwargs) -> AsyncIterator[ProductRecord]:
        """
        Executa busca por keyword e yield dos produtos encontrados.
        
        Args:
            keyword: Termo de busca
            **kwargs: Parâmetros específicos da plataforma
            
        Yields:
            ProductRecord para cada produto encontrado
        """
        pass
    
    async def __aenter__(self):
        """Context manager: inicializa browser"""
        await self.init_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager: fecha browser"""
        await self.close_browser()
    
    async def init_browser(self):
        """Inicializa browser com stealth"""
        if self._browser is not None:
            return
        
        playwright = await async_playwright().start()
        
        self._browser = await playwright.chromium.launch(
            headless=self.config.HEADLESS,
            timeout=self.config.BROWSER_TIMEOUT,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        
        self._context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=self._get_user_agent(),
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
        )
        
        self._page = await self._context.new_page()
        
        # Inject stealth
        await stealth_async(self._page)
        
        logger.info(f"Browser initialized for {self.platform_name}")
    
    async def close_browser(self):
        """Fecha browser e limpa recursos"""
        if self._page:
            await self._page.close()
            self._page = None
        
        if self._context:
            await self._context.close()
            self._context = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        logger.info(f"Browser closed for {self.platform_name}")
    
    def _get_user_agent(self) -> str:
        """Retorna user-agent aleatório para evitar fingerprinting"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        return random.choice(user_agents)
    
    async def _random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None):
        """Aplica delay aleatório entre ações"""
        min_d = min_delay or self.config.MIN_DELAY
        max_d = max_delay or self.config.MAX_DELAY
        delay = random.uniform(min_d, max_d)
        await asyncio.sleep(delay)
    
    async def _human_scroll(self, times: int = 3):
        """Simula scroll humano para carregar conteúdo dinâmico"""
        if not self._page:
            return
        
        for _ in range(times):
            scroll_distance = random.randint(300, 800)
            await self._page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # Scroll back to top
        await self._page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)
    
    async def _wait_for_network_idle(self, timeout: Optional[int] = None):
        """Aguarda rede ficar ociosa"""
        if not self._page:
            return
        
        try:
            await self._page.wait_for_load_state('networkidle', timeout=timeout or self.config.PAGE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Network idle timeout: {e}")
    
    async def _wait_for_selector_chain(
        self,
        selectors: List[str],
        timeout: int = 10000,
        state: str = "attached"
    ) -> Optional[str]:
        """
        Tenta múltiplos seletores em cadeia até encontrar um que funcione.
        
        Args:
            selectors: Lista de seletores CSS para tentar
            timeout: Timeout por tentativa
            state: Estado esperado (attached, visible, hidden, detached)
            
        Returns:
            O selector que funcionou, ou None se todos falharam
        """
        if not self._page:
            return None
        
        for selector in selectors:
            try:
                await self._page.wait_for_selector(selector, state=state, timeout=timeout)
                logger.debug(f"Selector chain succeeded: {selector}")
                return selector
            except Exception:
                logger.debug(f"Selector chain failed: {selector}")
                continue
        
        return None
    
    def _generate_record_id(self, platform_url: str, collected_at: datetime) -> str:
        """Gera ID único para o registro baseado em URL + timestamp"""
        content = f"{platform_url}:{collected_at.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _build_record(
        self,
        data: Dict[str, Any],
        url: str,
        extraction_method: str = "dom",
        selector_used: Optional[str] = None,
    ) -> ProductRecord:
        """
        Constrói ProductRecord padronizado a partir de dados extraídos.
        
        Args:
            data: Dados extraídos do scraper específico
            url: URL do produto
            extraction_method: Método usado (dom, jsonld, api, etc)
            selector_used: Selector CSS/JSON-LD utilizado
            
        Returns:
            ProductRecord validado
        """
        now = datetime.utcnow()
        
        record_data = {
            'id': self._generate_record_id(url, now),
            'collection_id': self._collection_id,
            'collected_at': now,
            'platform': self.platform_type,
            'platform_url': url,
            'platform_name': self.platform_name,
            'product_name': data.get('name', ''),
            'brand': data.get('brand'),
            'model': data.get('model'),
            'sku': data.get('sku'),
            'price': float(data.get('price', 0)),
            'original_price': data.get('original_price'),
            'discount_percentage': data.get('discount_percentage'),
            'currency': data.get('currency', 'BRL'),
            'availability': data.get('availability', 'in_stock'),
            'seller_name': data.get('seller_name'),
            'seller_rating': data.get('seller_rating'),
            'is_sponsored': data.get('is_sponsored', False),
            'is_fulfilled_by_platform': data.get('is_fulfilled_by_platform', False),
            'rating': data.get('rating'),
            'reviews_count': data.get('reviews_count'),
            'image_url': data.get('image_url'),
            'extraction_method': extraction_method,
            'selector_used': selector_used,
        }
        
        # Adiciona campos opcionais se presentes
        optional_fields = ['capacity', 'energy_efficiency', 'product_type', 
                          'shipping_cost', 'installments', 'features', 'description']
        for field in optional_fields:
            if field in data:
                record_data[field] = data[field]
        
        return ProductRecord(**record_data)
    
    async def _capture_screenshot(self, name: str = "error"):
        """Captura screenshot para debug"""
        if not self.config.ENABLE_SCREENSHOTS or not self._page:
            return None
        
        try:
            from pathlib import Path
            screenshot_dir = Path(self.config.SCREENSHOT_DIR)
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = screenshot_dir / filename
            
            await self._page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None
    
    def set_collection_id(self, collection_id: str):
        """Define ID da coleta atual"""
        self._collection_id = collection_id
        logger.info(f"Collection ID set: {collection_id}")
