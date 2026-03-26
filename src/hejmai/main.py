import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from hejmai import models, schemas, database

# Cria as tabelas no SQLite ao iniciar
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Agente de Economia Doméstica")


@app.get("/")
def read_root():
    return {"status": "Agente Online", "ano": 2026}


@app.post("/itens/", response_model=schemas.Item)
def criar_item(item: schemas.ItemCreate, db: Session = Depends(database.get_db)):
    db_item = models.Item(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.patch("/itens/{item_id}/consumir")
def consumir_item(
    item_id: int,
    quantidade: float | None = None,
    db: Session = Depends(database.get_db),
):
    db_item: models.Item | None = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    assert db_item is not None

    db_item.quantidade = 0.0
    db_item.status = "consumido"
    db_item.data_fim = datetime.date.today()

    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/itens/", response_model=List[schemas.Item])
def listar_itens(db: Session = Depends(database.get_db)):
    return db.query(models.Item).filter(models.Item.status == "ativo").all()


@app.get("/itens/vencendo/")
def listar_itens_vencendo(db: Session = Depends(database.get_db)):
    hoje = datetime.date.today()
    proxima_semana = hoje + datetime.timedelta(days=7)
    return (
        db.query(models.Item).filter(models.Item.data_validade <= proxima_semana).all()
    )


@app.get("/itens/alertas-validade/")
def buscar_alertas(dias: int = 5, db: Session = Depends(database.get_db)):
    limite = datetime.date.today() + datetime.timedelta(days=dias)
    # Busca itens que vencem entre hoje e o limite de dias
    itens = (
        db.query(models.Item)
        .filter(
            models.Item.data_validade <= limite,
            models.Item.data_validade >= datetime.date.today(),
        )
        .all()
    )
    return itens

@app.get("/itens/historico-consumo/")
def obter_historico(dias: int = 30, db: Session = Depends(database.get_db)):
    data_limite = datetime.date.today() - datetime.timedelta(days=dias)
    itens = db.query(models.Item).filter(
        models.Item.status != "ativo",
        models.Item.data_fim >= data_limite
    ).all()
    return itens

def start():
    import uvicorn

    uvicorn.run(
        "hejmai.main:app", host="127.0.0.1", port=8081, reload=True, app_dir="src"
    )
