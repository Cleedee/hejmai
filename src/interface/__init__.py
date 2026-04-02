"""
Interface Streamlit do Hejmai.

Módulos principais:
- config: Configurações centralizadas
- api_client: Cliente HTTP com tratamento de erros
- components: Componentes reutilizáveis (em desenvolvimento)
- utils: Utilitários (em desenvolvimento)
"""

from .config import config, Config
from .api_client import (
    APIClient,
    APIError,
    ConnectionError,
    NotFoundError,
    ServerError,
    BadRequestError,
    UnauthorizedError,
)

__all__ = [
    "config",
    "Config",
    "APIClient",
    "APIError",
    "ConnectionError",
    "NotFoundError",
    "ServerError",
    "BadRequestError",
    "UnauthorizedError",
]
