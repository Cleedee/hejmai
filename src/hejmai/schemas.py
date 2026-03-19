from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


# Classe base com os campos comuns
class ItemBase(BaseModel):
    nome: str
    categoria: str
    quantidade_inicial: float = Field(
        ..., gt=0, description="A quantidade deve ser maior que zero"
    )
    quantidade_atual: Optional[float] = None
    unidade: str  # un, kg, pacote, etc.
    data_validade: date
    preco_pago: Optional[float] = None
    estabelecimento: Optional[str] = None


# Esquema para criação (o que o Bot do Telegram envia)
class ItemCreate(ItemBase):
    pass


# Esquema para leitura (o que a API retorna, incluindo o ID do banco)
class Item(ItemBase):
    id: int
    data_registro: date

    class Config:
        from_attributes = True  # Permite que o Pydantic leia modelos do SQLAlchemy
