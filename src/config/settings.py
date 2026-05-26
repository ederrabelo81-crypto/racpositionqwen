"""
Configuração principal do sistema.
Centraliza settings via Pydantic com validação automática.
"""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import List, Dict, Optional
from enum import Enum


class PriorityLevel(str, Enum):
    HIGH = "alta"
    MEDIUM = "media"
    LOW = "baixa"


class ScraperConfig(BaseSettings):
    """Configurações gerais do scraper"""
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore",  # Ignora variáveis de outras classes
        "case_sensitive": True
    }
    
    # Browser settings
    MAX_BROWSERS: int = Field(default=3, ge=1, le=10, description="Máximo de browsers no pool")
    BROWSER_TIMEOUT: int = Field(default=30000, ge=5000, description="Timeout do browser em ms")
    PAGE_TIMEOUT: int = Field(default=25000, ge=3000, description="Timeout de navegação em ms")
    HEADLESS: bool = Field(default=True, description="Executar browser em modo headless")
    
    # Timing & delays
    MIN_DELAY: float = Field(default=1.0, ge=0.1, description="Delay mínimo entre requisições (s)")
    MAX_DELAY: float = Field(default=3.0, ge=0.1, description="Delay máximo entre requisições (s)")
    REQUEST_TIMEOUT: int = Field(default=30, ge=10, description="Timeout de requisição HTTP (s)")
    
    @field_validator('MAX_DELAY')
    @classmethod
    def validate_max_delay(cls, v, info):
        # Validação simplificada sem acesso a outros campos
        if v < 0.1:
            raise ValueError('MAX_DELAY deve ser >= 0.1')
        return v
    
    # Pagination
    MAX_PAGES: int = Field(default=5, ge=1, le=20, description="Máximo de páginas por keyword")
    ITEMS_PER_PAGE: int = Field(default=24, ge=10, description="Itens esperados por página")
    
    # Retry policy
    MAX_RETRIES: int = Field(default=3, ge=1, le=10, description="Tentativas máximas por falha")
    RETRY_BACKOFF: float = Field(default=2.0, ge=1.0, description="Backoff exponencial base")
    
    # Screenshot
    ENABLE_SCREENSHOTS: bool = Field(default=False, description="Capturar screenshots de erro")
    SCREENSHOT_DIR: str = Field(default="logs/screenshots", description="Diretório de screenshots")


class SupabaseConfig(BaseSettings):
    """Configurações do Supabase"""
    
    SUPABASE_URL: str = Field(..., description="URL do projeto Supabase")
    SUPABASE_KEY: str = Field(..., description="Chave de API do Supabase")
    BATCH_SIZE: int = Field(default=500, ge=100, le=1000, description="Batch size para upload")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


class TelegramConfig(BaseSettings):
    """Configurações do Telegram"""
    
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None, description="Token do bot")
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None, description="Chat ID para notificações")
    ENABLE_NOTIFICATIONS: bool = Field(default=True, description="Habilitar notificações")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


class ClaudeConfig(BaseSettings):
    """Configurações da API Claude (Competitive Intelligence)"""
    
    CLAUDE_API_KEY: Optional[str] = Field(default=None, description="API key da Anthropic")
    CLAUDE_MODEL: str = Field(default="claude-3-sonnet-20240229", description="Modelo a usar")
    ENABLE_AI_INSIGHTS: bool = Field(default=False, description="Habilitar análise com IA")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Singleton instances
_scraper_config: Optional[ScraperConfig] = None
_supabase_config: Optional[SupabaseConfig] = None
_telegram_config: Optional[TelegramConfig] = None
_claude_config: Optional[ClaudeConfig] = None


def get_scraper_config() -> ScraperConfig:
    global _scraper_config
    if _scraper_config is None:
        _scraper_config = ScraperConfig()
    return _scraper_config


def get_supabase_config() -> SupabaseConfig:
    global _supabase_config
    if _supabase_config is None:
        _supabase_config = SupabaseConfig()
    return _supabase_config


def get_telegram_config() -> TelegramConfig:
    global _telegram_config
    if _telegram_config is None:
        _telegram_config = TelegramConfig()
    return _telegram_config


def get_claude_config() -> ClaudeConfig:
    global _claude_config
    if _claude_config is None:
        _claude_config = ClaudeConfig()
    return _claude_config
