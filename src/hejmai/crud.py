from sqlalchemy.orm import Session

from hejmai import models


def traga_todas_categorias(db: Session):
    return db.query(models.Categoria).all()
