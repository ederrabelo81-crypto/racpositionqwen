"""
Modelos de dados para keywords.
Carrega configurações de arquivos YAML com validação.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml
from src.config.settings import PriorityLevel


class KeywordConfig(BaseModel):
    """Configuração de uma keyword individual"""
    
    id: str = Field(..., description="ID único da keyword")
    term: str = Field(..., description="Termo de busca")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM)
    category: str = Field(default="geral", description="Categoria do produto")
    brands: List[str] = Field(default_factory=list, description="Marcas relacionadas")
    enabled: bool = Field(default=True, description="Se está ativa para coleta")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais")
    
    class Config:
        extra = "allow"


class KeywordsManager:
    """Gerencia keywords carregadas de YAML"""
    
    def __init__(self, config_dir: str = "configs/keywords"):
        self.config_dir = Path(config_dir)
        self._keywords: Dict[str, KeywordConfig] = {}
        self._load_all()
    
    def _load_all(self):
        """Carrega todos os arquivos YAML do diretório"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self._create_default_configs()
        
        for yaml_file in self.config_dir.glob("*.yaml"):
            self._load_file(yaml_file)
    
    def _load_file(self, filepath: Path):
        """Carrega um arquivo YAML específico"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or 'keywords' not in data:
            return
        
        for kw_data in data['keywords']:
            try:
                keyword = KeywordConfig(**kw_data)
                if keyword.enabled:
                    self._keywords[keyword.id] = keyword
            except Exception as e:
                print(f"Erro ao carregar keyword {kw_data.get('id', 'unknown')}: {e}")
    
    def _create_default_configs(self):
        """Cria configurações padrão se não existirem"""
        default_keywords = {
            'split': {
                'keywords': [
                    {'id': 'ar-condicionado-split', 'term': 'ar condicionado split', 'priority': 'alta', 'category': 'split'},
                    {'id': 'ar-condicionado-split-inverter', 'term': 'ar condicionado split inverter', 'priority': 'alta', 'category': 'split'},
                    {'id': 'ar-condicionado-split-quente-frio', 'term': 'ar condicionado split quente frio', 'priority': 'media', 'category': 'split'},
                ]
            },
            'window': {
                'keywords': [
                    {'id': 'ar-condicionado-window', 'term': 'ar condicionado window', 'priority': 'media', 'category': 'window'},
                    {'id': 'ar-condicionado-window-quente-frio', 'term': 'ar condicionado window quente frio', 'priority': 'baixa', 'category': 'window'},
                ]
            },
            'portatil': {
                'keywords': [
                    {'id': 'ar-condicionado-portatil', 'term': 'ar condicionado portatil', 'priority': 'media', 'category': 'portatil'},
                    {'id': 'climatizador-portatil', 'term': 'climatizador portatil', 'priority': 'baixa', 'category': 'portatil'},
                ]
            },
            'brands': {
                'keywords': [
                    {'id': 'springer-midea', 'term': 'ar condicionado springer midea', 'priority': 'alta', 'category': 'marca', 'brands': ['Springer Midea']},
                    {'id': 'lg-dual-inverter', 'term': 'ar condicionado lg dual inverter', 'priority': 'alta', 'category': 'marca', 'brands': ['LG']},
                    {'id': 'samsung-windfree', 'term': 'ar condicionado samsung windfree', 'priority': 'alta', 'category': 'marca', 'brands': ['Samsung']},
                    {'id': 'gree', 'term': 'ar condicionado gree', 'priority': 'media', 'category': 'marca', 'brands': ['Gree']},
                    {'id': 'elgin', 'term': 'ar condicionado elgin', 'priority': 'media', 'category': 'marca', 'brands': ['Elgin']},
                ]
            }
        }
        
        for filename, data in default_keywords.items():
            filepath = self.config_dir / f"{filename}.yaml"
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            
            # Carrega imediatamente
            self._load_file(filepath)
    
    def get_all(self) -> List[KeywordConfig]:
        """Retorna todas as keywords ativas"""
        return list(self._keywords.values())
    
    def get_by_priority(self, priority: PriorityLevel) -> List[KeywordConfig]:
        """Filtra keywords por prioridade"""
        return [kw for kw in self._keywords.values() if kw.priority == priority]
    
    def get_by_category(self, category: str) -> List[KeywordConfig]:
        """Filtra keywords por categoria"""
        return [kw for kw in self._keywords.values() if kw.category == category]
    
    def get_by_brand(self, brand: str) -> List[KeywordConfig]:
        """Filtra keywords por marca"""
        return [kw for kw in self._keywords.values() if brand.lower() in [b.lower() for b in kw.brands]]
    
    def get_enabled(self) -> List[KeywordConfig]:
        """Retorna apenas keywords habilitadas"""
        return [kw for kw in self._keywords.values() if kw.enabled]
    
    def reload(self):
        """Recarrega todas as configurações (hot reload)"""
        self._keywords.clear()
        self._load_all()
