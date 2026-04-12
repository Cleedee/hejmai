from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from hejmai.database import Base
import datetime


class Categoria(Base):
    __tablename__ = "categorias"
    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)
    # Ex: "Hortifruti", "Limpeza", "Proteína"


class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    categoria = Column(String, unique=True)
    valor_limite = Column(Float)
    mes_referencia = Column(Integer)  # 4 para Abril
    ano_referencia = Column(Integer)  # 2026


class Produto(Base):
    """O Catálogo: Representa a identidade do que você consome."""

    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, index=True)
    categoria = Column(String)
    unidade_medida = Column(String)  # kg, un, l
    estoque_atual = Column(Float, default=0.0)
    ultima_validade = Column(Date)

    # Relação com o histórico de preços
    historico_compras = relationship("ItemCompra", back_populates="produto")

    movimentacoes = relationship("Movimentacao", back_populates="produto")

class Compra(Base):
    """O Evento: Representa a ida ao mercado (Nota Fiscal)."""

    __tablename__ = "compras"

    id = Column(Integer, primary_key=True)
    local_compra = Column(String)  # Onde foi comprado (Mercado A, B)
    data_compra = Column(Date, default=datetime.date.today)
    valor_total_nota = Column(Float)
    excluida = Column(Integer, default=0)  # 0 = ativa, 1 = excluída (exclusão lógica)
    data_exclusao = Column(DateTime(timezone=True), nullable=True)  # Data da exclusão lógica

    itens = relationship("ItemCompra", back_populates="compra")


class ItemCompra(Base):
    """A Transação: O elo entre o Produto e a Compra específica."""

    __tablename__ = "itens_compra"

    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"))
    compra_id = Column(Integer, ForeignKey("compras.id"))

    quantidade = Column(Float)
    preco_unitario = Column(Float)
    validade_especifica = Column(Date)

    produto = relationship("Produto", back_populates="historico_compras")
    compra = relationship("Compra", back_populates="itens")

class Movimentacao(Base):
    __tablename__ = "movimentacoes"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Float, nullable=False)  # Negativo para saída, Positivo para entrada
    tipo = Column(String, nullable=False)       # 'COMPRA', 'CONSUMO', 'PERDA', 'AJUSTE'
    data_movimento = Column(DateTime(timezone=True), server_default=func.now())

    produto = relationship("Produto", back_populates="movimentacoes")


class Receita(Base):
    """Receitas predefinidas vinculadas ao estoque."""

    __tablename__ = "receitas"

    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)  # "Marmota", "Omelete"
    descricao = Column(String, nullable=True)             # Descrição opcional
    modo_preparo = Column(String, nullable=True)         # Como preparar
    porcoes = Column(Integer, default=1)                 # Quantas porções
    tags = Column(String, nullable=True)                 # Tags: "rapida", "fit", "barata"
    ativa = Column(Integer, default=1)                    # 1 = ativa, 0 = desativada
    criada_em = Column(DateTime(timezone=True), server_default=func.now())

    itens = relationship("ItemReceita", back_populates="receita", cascade="all, delete-orphan")


class ItemReceita(Base):
    """Item de uma receita, vinculado a um produto do estoque."""

    __tablename__ = "itens_receita"

    id = Column(Integer, primary_key=True)
    receita_id = Column(Integer, ForeignKey("receitas.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade_porcao = Column(Float, nullable=False)    # Quanto usa por porção (g, un, ml)
    observacao = Column(String, nullable=True)           # Opcional: "bem frito", "sem sal"

    receita = relationship("Receita", back_populates="itens")
    produto = relationship("Produto")
