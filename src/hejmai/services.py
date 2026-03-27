import datetime

from sqlalchemy.orm import Session

from hejmai import models

def registrar_compra_completa(dados_compra, db: Session):
    # 1. Criar a Compra (Cabeçalho)
    nova_compra = models.Compra(
        local_compra=dados_compra['local_compra'],
        valor_total_nota=sum(item['preco_pago'] for item in dados_compra['itens'])
    )
    db.add(nova_compra)
    db.flush() # Para gerar o ID da compra sem dar commit ainda

    for item_data in dados_compra['itens']:
        # 2. Buscar ou Criar o Produto (Normalização)
        produto = db.query(models.Produto).filter(models.Produto.nome == item_data['nome']).first()
        if not produto:
            produto = models.Produto(
                nome=item_data['nome'],
                categoria=item_data['categoria'],
                unidade_medida=item_data['unidade']
            )
            db.add(produto)
            db.flush()

        # 3. Criar o vínculo ItemCompra
        novo_item_compra = models.ItemCompra(
            produto_id=produto.id,
            compra_id=nova_compra.id,
            quantidade=item_data['quantidade'],
            preco_unitario=item_data['preco_pago'] / item_data['quantidade'],
            validade_especifica=datetime.datetime.strptime(item_data['data_validade'], "%Y-%m-%d").date()
        )
        db.add(novo_item_compra)

        # 4. Atualizar o Estado Atual do Produto (Denormalização para performance)
        produto.estoque_atual += item_data['quantidade']
        produto.ultima_validade = novo_item_compra.validade_especifica

    db.commit()
    return {"status": "Compra e estoque atualizados"}
