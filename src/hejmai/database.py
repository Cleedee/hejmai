import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Carrega variáveis do arquivo .env (se existir)
load_dotenv()

# DATABASE_URL deve estar no formato: sqlite:///./estoque.db ou sqlite:////app/data/estoque.db
# Prioriza variável de ambiente do sistema (Docker) sobre o .env
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///./estoque.db"

# O connect_args é necessário apenas para o SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
