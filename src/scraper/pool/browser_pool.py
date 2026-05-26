"""
Browser Pool para reutilização de browsers.
Reduz overhead de launch/close e limita consumo de recursos.
"""
import asyncio
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
from playwright.async_api import Browser, async_playwright
from playwright_stealth import stealth_async

from src.config.settings import get_scraper_config, ScraperConfig


@dataclass
class BrowserWrapper:
    """Wrapper para browser com metadados de uso"""
    
    browser: Browser
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    use_count: int = 0
    is_healthy: bool = True
    
    def mark_used(self):
        """Marca como utilizado recentemente"""
        self.last_used = datetime.utcnow()
        self.use_count += 1
    
    def age_minutes(self) -> float:
        """Idade do browser em minutos"""
        return (datetime.utcnow() - self.created_at).total_seconds() / 60
    
    def idle_minutes(self) -> float:
        """Tempo ocioso em minutos"""
        return (datetime.utcnow() - self.last_used).total_seconds() / 60


class BrowserPool:
    """
    Pool de browsers reutilizáveis.
    
    Features:
    - Limita número máximo de browsers simultâneos
    - Reutiliza browsers saudáveis
    - Descarta browsers antigos ou corruptos
    - Health check automático
    """
    
    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or get_scraper_config()
        self._pool: List[BrowserWrapper] = []
        self._lock = asyncio.Lock()
        self._playwright = None
        self._max_age_minutes = 30  # Descarta após 30 min
        self._max_idle_minutes = 10  # Descarta após 10 min ocioso
    
    async def initialize(self):
        """Inicializa o pool (chamar uma vez no startup)"""
        self._playwright = await async_playwright().start()
        logger.info(f"Browser pool initialized with max {self.config.MAX_BROWSERS} browsers")
    
    async def shutdown(self):
        """Fecha todos os browsers e limpa recursos"""
        async with self._lock:
            for wrapper in self._pool:
                try:
                    await wrapper.browser.close()
                except:
                    pass
            
            self._pool.clear()
            
            if self._playwright:
                await self._playwright.stop()
        
        logger.info("Browser pool shut down")
    
    async def acquire(self) -> Browser:
        """
        Adquire um browser do pool.
        Cria novo se necessário e possível.
        
        Returns:
            Browser instance pronta para uso
        """
        async with self._lock:
            # Limpa browsers velhos/doentes primeiro
            await self._cleanup_pool()
            
            # Tenta reutilizar browser saudável
            for wrapper in self._pool:
                if wrapper.is_healthy:
                    wrapper.mark_used()
                    logger.debug(f"Reusing browser (age={wrapper.age_minutes():.1f}min, uses={wrapper.use_count})")
                    return wrapper.browser
            
            # Cria novo browser se dentro do limite
            if len(self._pool) < self.config.MAX_BROWSERS:
                browser = await self._create_browser()
                wrapper = BrowserWrapper(browser=browser)
                self._pool.append(wrapper)
                logger.info(f"Created new browser (pool size: {len(self._pool)}/{self.config.MAX_BROWSERS})")
                return browser
            
            # Pool cheio: espera ou usa o mais antigo
            logger.warning("Browser pool at capacity, using oldest browser")
            oldest = min(self._pool, key=lambda w: w.last_used)
            oldest.mark_used()
            return oldest.browser
    
    async def release(self, browser: Browser):
        """
        Libera browser de volta ao pool.
        Na verdade não faz nada - browsers ficam no pool até cleanup.
        """
        # Mark as used to update timestamp
        for wrapper in self._pool:
            if wrapper.browser == browser:
                wrapper.mark_used()
                break
    
    async def _create_browser(self) -> Browser:
        """Cria nova instância de browser com configurações otimizadas"""
        
        browser = await self._playwright.chromium.launch(
            headless=self.config.HEADLESS,
            timeout=self.config.BROWSER_TIMEOUT,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        return browser
    
    async def _cleanup_pool(self):
        """Remove browsers velhos, ociosos ou doentes"""
        
        to_remove = []
        
        for wrapper in self._pool:
            should_remove = False
            reason = ""
            
            # Verifica idade
            if wrapper.age_minutes() > self._max_age_minutes:
                should_remove = True
                reason = f"too old ({wrapper.age_minutes():.1f}min)"
            
            # Verifica ociosidade
            elif wrapper.idle_minutes() > self._max_idle_minutes:
                should_remove = True
                reason = f"too idle ({wrapper.idle_minutes():.1f}min)"
            
            # Verifica saúde
            elif not wrapper.is_healthy:
                should_remove = True
                reason = "unhealthy"
            
            if should_remove:
                to_remove.append((wrapper, reason))
        
        # Remove e fecha browsers marcados
        for wrapper, reason in to_remove:
            try:
                await wrapper.browser.close()
                logger.debug(f"Removed browser from pool: {reason}")
            except:
                pass
            
            self._pool.remove(wrapper)
    
    async def health_check(self, browser: Browser) -> bool:
        """
        Verifica se browser está saudável.
        Pode ser estendido com testes reais (página em branco, etc).
        """
        for wrapper in self._pool:
            if wrapper.browser == browser:
                # Verifica se browser ainda responde
                try:
                    # Teste simples: verifica se contexts ainda funciona
                    _ = browser.contexts
                    wrapper.is_healthy = True
                    return True
                except:
                    wrapper.is_healthy = False
                    return False
        
        return False
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do pool"""
        return {
            'size': len(self._pool),
            'max_size': self.config.MAX_BROWSERS,
            'total_uses': sum(w.use_count for w in self._pool),
            'avg_age_minutes': sum(w.age_minutes() for w in self._pool) / len(self._pool) if self._pool else 0,
            'healthy_count': sum(1 for w in self._pool if w.is_healthy),
        }


# Singleton global
_browser_pool: Optional[BrowserPool] = None


def get_browser_pool(config: Optional[ScraperConfig] = None) -> BrowserPool:
    """Retorna instancia singleton do browser pool"""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(config)
    return _browser_pool
