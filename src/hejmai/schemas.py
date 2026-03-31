from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional


class CategoriaBase(BaseModel):
    nome: str


class CategoriaCreate(CategoriaBase):
    pass


class Categoria(CategoriaBase):
    id: int

    class Config:
        from_attributes = True  # Permite que o Pydantic leia modelos do SQLAlchemy


class ItemEntrada(BaseModel):
    nome: str
    categoria: str
    unidade: str
    quantidade: float
    preco_pago: float
    data_validade: date


class CompraEntrada(BaseModel):
    local_compra: Optional[str] = "Mercado Desconhecido"
    itens: List[ItemEntrada]


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    unidade_medida: Optional[str] = None
    estoque_atual: Optional[float] = None
    ultima_validade: Optional[date] = None


class UnificacaoProdutos(BaseModel):
    """Schema para unificação de produtos similares."""
    produto_principal_id: int = Field(description="ID do produto que será mantido")
    produtos_para_unificar: List[int] = Field(
        description="Lista de IDs de produtos que serão fundidos no produto principal"
    )


# Schema para validação da entrada
class PerguntaIA(BaseModel):
    pergunta: str
