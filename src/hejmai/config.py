"""
Configurações centralizadas do Hejmai.

Este módulo deve ser a única fonte de verdade para configurações
do projeto. Todos os outros módulos devem importar daqui.

Uso:
    from hejmai.config import MODEL, OLLAMA_BASE_URL
    # ou
    from hejmai.config import config
"""

import os
from functools import lru_cache
from typing import Optional


DEFAULT_MODEL: str = "qwen2.5:0.5b"


@lru_cache()
def get_config() -> dict:
    """Retorna todas as configurações como um dicionário (com cache)."""
    return {
        "MODEL": os.getenv("MODEL", DEFAULT_MODEL),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "API_URL": os.getenv("API_URL", "http://api:8081"),
        "DATABASE_PATH": os.getenv("DATABASE_PATH", "/app/data/estoque.db"),
        "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN"),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
    }


class Config:
    DEFAULT_MODEL = DEFAULT_MODEL
    
    @staticmethod
    def MODEL() -> str:
        return os.getenv("MODEL", DEFAULT_MODEL)
    
    @staticmethod
    def OLLAMA_BASE_URL() -> str:
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    @staticmethod
    def API_URL() -> str:
        return os.getenv("API_URL", "http://api:8081")
    
    @staticmethod
    def DATABASE_PATH() -> str:
        return os.getenv("DATABASE_PATH", "/app/data/estoque.db")
    
    @staticmethod
    def TELEGRAM_TOKEN() -> Optional[str]:
        return os.getenv("TELEGRAM_TOKEN")
    
    @staticmethod
    def TELEGRAM_CHAT_ID() -> Optional[str]:
        return os.getenv("TELEGRAM_CHAT_ID")


config = Config()
