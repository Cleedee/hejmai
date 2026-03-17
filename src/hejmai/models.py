from sqlalchemy import Column, Integer, String, Float, Date
from hejmai.database import Base
import datetime


class Item(Base):
    __tablename__ = "itens"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    categoria = Column(String)  # Ex: Laticínios, Proteínas, Limpeza
    quantidade_inicial = Column(Float, default=1.0)
    quantidade_atual = Column(Float)
    unidade = Column(String)  # Ex: kg, un, ml
    data_validade = Column(Date)
    preco_pago = Column(Float)
    status = Column(String, default="ativo")  # ativo, consumido, desperdiçado
    data_registro = Column(Date, default=datetime.date.today)
    data_fim = Column(Date, nullable=True)
    estabelecimento = Column(String, nullable=True)

class Personagem(Base):
    __tablename__ = "personagens"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    xp = Column(Integer, default=0)
    nivel = Column(Integer, default=1)
