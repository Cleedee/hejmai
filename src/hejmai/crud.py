from sqlalchemy.orm import Session
from typing import Optional

from hejmai import models


def traga_todas_categorias(db: Session):
    return db.query(models.Categoria).all()


def atualizar_produto(
    db: Session, produto_id: int, dados: dict
) -> Optional[models.Produto]:
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not produto:
        return None

    for campo, valor in dados.items():
        if valor is not None:
            setattr(produto, campo, valor)

    db.commit()
    db.refresh(produto)
    return produto
