"""
Interface Streamlit do Hejmai.

Módulos principais:
- config: Configurações centralizadas
- api_client: Cliente HTTP com tratamento de erros
- components: Componentes reutilizáveis (NLP, Charts, Budget)
- utils: Utilitários (validadores)
"""

from interface.config import config, Config
from interface.api_client import (
    APIClient,
    APIError,
    ConnectionError,
    NotFoundError,
    ServerError,
    BadRequestError,
    UnauthorizedError,
)
from interface.components import (
    render_nlp_processor,
    render_price_chart,
    render_budget_manager,
)
from interface.utils import validate_carga_manual

__all__ = [
    # Config
    "config",
    "Config",
    
    # API Client
    "APIClient",
    "APIError",
    "ConnectionError",
    "NotFoundError",
    "ServerError",
    "BadRequestError",
    "UnauthorizedError",
    
    # Componentes
    "render_nlp_processor",
    "render_price_chart",
    "render_budget_manager",
    
    # Utilitários
    "validate_carga_manual",
]
