"""
Configurações centralizadas da interface Streamlit.

Todas as configurações e constantes devem ser definidas aqui,
permitindo fácil manutenção e externalização via variáveis de ambiente.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """
    Configurações da interface Hejmai.
    
    Atributos:
        API_URL: URL base da API FastAPI
        API_TIMEOUT: Timeout padrão para chamadas de API (segundos)
        NLP_TIMEOUT: Timeout para processamento NLP (segundos)
        ORCAMENTO_LIMITE_PADRAO: Limite de orçamento padrão (R$)
        CACHE_TTL_SEGUNDOS: Tempo de vida do cache (segundos)
        MAX_RETRY_TENTATIVAS: Número máximo de tentativas de retry
    """
    
    # URL da API FastAPI
    API_URL: str = os.getenv("API_URL", "http://localhost:8081")
    
    # Timeouts (em segundos)
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "30"))
    NLP_TIMEOUT: int = int(os.getenv("NLP_TIMEOUT", "60"))
    
    # Orçamento padrão (R$)
    ORCAMENTO_LIMITE_PADRAO: float = float(os.getenv("ORCAMENTO_LIMITE", "500.00"))
    
    # Cache TTL (segundos)
    CACHE_TTL_SEGUNDOS: int = int(os.getenv("CACHE_TTL", "300"))
    
    # Retry
    MAX_RETRY_TENTATIVAS: int = int(os.getenv("MAX_RETRY", "3"))


# Instância singleton para uso em toda a aplicação
config = Config()
