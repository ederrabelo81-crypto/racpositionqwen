"""
Modelo de dados padronizado para produtos coletados.
19 colunas conforme especificação original.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class PlatformType(str, Enum):
    MERCADO_LIVRE = "mercado_livre"
    AMAZON = "amazon"
    SHOPEE = "shopee"
    MAGAZINE_LUIZA = "magazine_luiza"
    DEALER = "dealer"
    OTHER = "other"


class ProductRecord(BaseModel):
    """Registro padronizado de produto coletado"""
    
    # Identificação única
    id: str = Field(..., description="ID único do registro (hash)")
    collection_id: str = Field(..., description="ID da coleta")
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp da coleta")
    
    # Plataforma
    platform: PlatformType = Field(..., description="Tipo de plataforma")
    platform_url: str = Field(..., description="URL completa do produto")
    platform_name: str = Field(..., description="Nome da plataforma/dealer")
    
    # Produto
    product_name: str = Field(..., description="Nome completo do produto")
    brand: Optional[str] = Field(default=None, description="Marca do produto")
    model: Optional[str] = Field(default=None, description="Modelo específico")
    sku: Optional[str] = Field(default=None, description="SKU ou código do fabricante")
    
    # Preço
    price: float = Field(..., ge=0, description="Preço atual em BRL")
    original_price: Optional[float] = Field(default=None, ge=0, description="Preço original (antes de desconto)")
    discount_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Porcentagem de desconto")
    currency: str = Field(default="BRL", description="Moeda")
    
    # Disponibilidade
    availability: str = Field(default="in_stock", description="Status de disponibilidade")
    stock_level: Optional[str] = Field(default=None, description="Nível de estoque se disponível")
    
    # Seller/Vendedor
    seller_name: Optional[str] = Field(default=None, description="Nome do vendedor")
    seller_rating: Optional[float] = Field(default=None, ge=0, le=5, description="Rating do vendedor")
    seller_reviews_count: Optional[int] = Field(default=None, ge=0, description="Número de reviews")
    
    # Características do produto
    capacity: Optional[str] = Field(default=None, description="Capacidade (BTUs)")
    energy_efficiency: Optional[str] = Field(default=None, description="Classificação energética")
    product_type: Optional[str] = Field(default=None, description="Tipo (split, window, etc)")
    
    # Metadados da plataforma
    is_sponsored: bool = Field(default=False, description="Se é anúncio patrocinado")
    is_fulfilled_by_platform: bool = Field(default=False, description="Entregue pela plataforma (ex: Full ML)")
    shipping_cost: Optional[float] = Field(default=None, description="Custo do frete")
    installments: Optional[Dict[str, Any]] = Field(default=None, description="Parcelamento info")
    
    # Conteúdo extra
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="Avaliação do produto")
    reviews_count: Optional[int] = Field(default=None, ge=0, description="Número de avaliações")
    features: Optional[str] = Field(default=None, description="Características principais")
    description: Optional[str] = Field(default=None, description="Descrição completa")
    
    # Imagens e mídia
    image_url: Optional[str] = Field(default=None, description="URL da imagem principal")
    additional_images: Optional[list] = Field(default_factory=list, description="URLs de imagens adicionais")
    
    # Controle de qualidade
    data_quality_score: float = Field(default=1.0, ge=0, le=1, description="Score de qualidade dos dados")
    extraction_method: str = Field(default="dom", description="Método de extração usado")
    selector_used: Optional[str] = Field(default=None, description="Selector CSS/JSON-LD usado")
    
    # Debug
    raw_html_snapshot: Optional[str] = Field(default=None, description="Snapshot do HTML (opcional)")
    screenshot_path: Optional[str] = Field(default=None, description="Caminho do screenshot se capturado")
    error_message: Optional[str] = Field(default=None, description="Erro na extração se houver")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_supabase_dict(self) -> Dict[str, Any]:
        """Converte para dicionário compatível com schema do Supabase"""
        return {
            'id': self.id,
            'collection_id': self.collection_id,
            'collected_at': self.collected_at.isoformat(),
            'platform': self.platform.value,
            'platform_url': self.platform_url[:2048] if self.platform_url else None,  # Truncate
            'platform_name': self.platform_name[:255] if self.platform_name else None,
            'product_name': self.product_name[:1000] if self.product_name else None,
            'brand': self.brand[:255] if self.brand else None,
            'model': self.model[:255] if self.model else None,
            'sku': self.sku[:255] if self.sku else None,
            'price': self.price,
            'original_price': self.original_price,
            'discount_percentage': self.discount_percentage,
            'currency': self.currency,
            'availability': self.availability,
            'stock_level': self.stock_level[:100] if self.stock_level else None,
            'seller_name': self.seller_name[:255] if self.seller_name else None,
            'seller_rating': self.seller_rating,
            'seller_reviews_count': self.seller_reviews_count,
            'capacity': self.capacity[:50] if self.capacity else None,
            'energy_efficiency': self.energy_efficiency[:50] if self.energy_efficiency else None,
            'product_type': self.product_type[:100] if self.product_type else None,
            'is_sponsored': self.is_sponsored,
            'is_fulfilled_by_platform': self.is_fulfilled_by_platform,
            'shipping_cost': self.shipping_cost,
            'installments': self.installments,
            'rating': self.rating,
            'reviews_count': self.reviews_count,
            'features': self.features[:2000] if self.features else None,
            'description': self.description[:5000] if self.description else None,
            'image_url': self.image_url[:2048] if self.image_url else None,
            'data_quality_score': self.data_quality_score,
            'extraction_method': self.extraction_method,
            'selector_used': self.selector_used[:500] if self.selector_used else None,
            'error_message': self.error_message[:1000] if self.error_message else None,
        }
