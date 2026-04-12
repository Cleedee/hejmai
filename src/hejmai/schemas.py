from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import List, Optional, Union


class CategoriaBase(BaseModel):
    nome: str


class CategoriaCreate(CategoriaBase):
    pass


class Categoria(CategoriaBase):
    id: int

    class Config:
        from_attributes = True


class ItemReceitaBase(BaseModel):
    produto_id: int
    quantidade_porcao: float
    observacao: Optional[str] = None


class ItemReceitaCreate(ItemReceitaBase):
    pass


class ItemReceitaResponse(ItemReceitaBase):
    id: int
    produto_nome: Optional[str] = None

    class Config:
        from_attributes = True


class ReceitaBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    modo_preparo: Optional[str] = None
    porcoes: int = 1
    tags: Optional[Union[str, List[str]]] = None

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        if isinstance(v, list):
            return ",".join(v)
        return v  # Keep string as-is


class ReceitaCreate(ReceitaBase):
    itens: List[ItemReceitaCreate]


class ReceitaUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    modo_preparo: Optional[str] = None
    porcoes: Optional[int] = None
    tags: Optional[Union[str, List[str]]] = None
    ativa: Optional[int] = None

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        if isinstance(v, list):
            return ",".join(v)
        return v


class ReceitaResponse(ReceitaBase):
    id: int
    itens: List[ItemReceitaResponse] = []
    itens_faltantes: List[str] = []  # Produtos que não tem em estoque

    class Config:
        from_attributes = True


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


class CompraUpdate(BaseModel):
    local_compra: Optional[str] = None
    data_compra: Optional[date] = None


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
