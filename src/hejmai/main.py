import datetime
from typing import List

from fastapi import Body, FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from hejmai import models, schemas, database, nlp
from hejmai.validator import SanityChecker

# Cria as tabelas no SQLite ao iniciar
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Agente de Economia Doméstica")

processador_compras = nlp.ProcessadorCompras("mistral:latest")
processador_receitas = nlp.Receitas("mistral:latest")

@app.get("/")
def read_root():
    return {"status": "Agente Online", "ano": 2026}

@app.get("/produtos/lista-compras-detalhada")
async def gerar_lista_detalhada(db: Session = Depends(database.get_db)):
    # 1. Busca produtos com estoque baixo
    itens = db.query(models.Produto).filter(models.Produto.estoque_atual < 1.0).all()
    
    lista_final = []
    for p in itens:
        # Busca o último preço pago para servir de âncora
        ultimo_item = db.query(models.ItemCompra).filter(
            models.ItemCompra.produto_id == p.id
        ).order_by(models.ItemCompra.id.desc()).first()
        
        preco_ref = ultimo_item.preco_unitario if ultimo_item else 0.0
        
        lista_final.append({
            "nome": p.nome,
            "categoria": p.categoria,
            "preco_referencia": preco_ref,
            "estoque": p.estoque_atual,
            "unidade": p.unidade_medida
        })
    
    return lista_final

@app.get("/relatorios/historico-precos/{produto_id}")
async def historico_precos(produto_id: int, db: Session = Depends(database.get_db)):
    # Buscamos todos os itens de compra vinculados ao produto, ordenados por data
    historico = db.query(models.ItemCompra).join(models.Compra).filter(
        models.ItemCompra.produto_id == produto_id
    ).order_by(models.Compra.data_compra).all()
    
    return [
        {
            "data": item.compra.data_compra,
            "preco": item.preco_unitario,
            "local": item.compra.local_compra
        } for item in historico
    ]

@app.get("/relatorios/previsao-gastos")
async def prever_gastos(db: Session = Depends(database.get_db)):
    # 1. Busca produtos que estão abaixo do limite (estoque < 1.0)
    itens_em_falta = db.query(models.Produto).filter(models.Produto.estoque_atual < 1.0).all()
    
    previsao_total = 0.0
    detalhes = []

    for produto in itens_em_falta:
        # 2. Busca o PREÇO MÉDIO ou ÚLTIMO PREÇO desse produto no histórico
        ultimo_item = db.query(models.ItemCompra).filter(
            models.ItemCompra.produto_id == produto.id
        ).order_by(models.ItemCompra.id.desc()).first()

        preco_base = ultimo_item.preco_unitario if ultimo_item else 0.0
        
        # Simulamos a compra de uma "unidade padrão" (ex: 1kg ou 1 pack)
        # Você pode ajustar isso para a 'quantidade_ideal' se tiver esse campo
        quantidade_estimada = 1.0 
        custo_estimado = preco_base * quantidade_estimada
        
        previsao_total += custo_estimado
        detalhes.append({
            "produto": produto.nome,
            "ultimo_preco": preco_base,
            "custo_estimado": custo_estimado
        })

    return {
        "valor_total_estimado": round(previsao_total, 2),
        "itens": detalhes
    }

@app.post("/processar-entrada-livre")
async def processar_texto_bot(payload: dict = Body(...), db: Session = Depends(database.get_db)):
    texto_bruto = payload.get("texto")
    
    # 1. Inteligência Artificial: Transforma texto em dados
    dados_extraidos = await processador_compras.extrair_dados(texto_bruto)

    # 2. Realiza o Sanity Check
    todos_alertas = []
    for item in dados_extraidos['itens']:
        alertas = SanityChecker.validar_item(item)
        todos_alertas.extend(alertas)

    # 3. Persistência Relacional: Salva em Produto, Compra e ItemCompra
    # Reaproveitamos a lógica de registrar_compra_lote que criamos antes
    resultado = await registrar_compra_lote(
        schemas.CompraEntrada(**dados_extraidos), 
        db
    )
    
    status_msg = "✅ Registro concluído."
    if todos_alertas:
        # Se houver alertas, mudamos o tom da mensagem para o Bot avisar você
        status_msg = "⚠️ Registro feito com OBSERVAÇÕES:\n- " + "\n- ".join(todos_alertas)

    return {
        "status": "sucesso",
        "dados_processados": dados_extraidos,
        "mensagem_bot": f"{status_msg}\nRegistrado: {len(dados_extraidos['itens'])} itens no {dados_extraidos['local_compra'] or 'estoque'}."
    }

@app.get("/sugerir-receita")
async def sugerir_receita(db: Session = Depends(database.get_db)):

    vencendo = listar_itens_vencendo(db)

    receita = await processador_receitas.sugerir_receita(vencendo)

    return {
        "status": "sucesso",
        "receita": receita
    }


@app.get("/produtos/lista-compras")
async def gerar_dados_lista(db: Session = Depends(database.get_db)):
    # Filtramos produtos que estão abaixo de um limite aceitável (ex: 1.0)
    # e ordenamos por categoria para facilitar a navegação no mercado
    itens_em_falta = db.query(models.Produto).filter(
        models.Produto.estoque_atual < 1.0
    ).order_by(models.Produto.categoria).all()
    
    return itens_em_falta

@app.patch("/produtos/consumir/{produto_id}")
async def consumir_produto(
    produto_id: int, 
    quantidade: float, 
    db: Session = Depends(database.get_db)
):
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    if produto.estoque_atual < quantidade:
        raise HTTPException(
            status_code=400, 
            detail=f"Estoque insuficiente. Disponível: {produto.estoque_atual}"
        )

    # Subtrai do estoque global do produto
    produto.estoque_atual -= quantidade

    db.commit()
    db.refresh(produto)
    
    return {
        "mensagem": f"{quantidade} {produto.unidade_medida} de {produto.nome} consumidos.",
        "estoque_restante": produto.estoque_atual
    }

@app.post("/compras/registrar-lote", status_code=status.HTTP_201_CREATED)
async def registrar_compra_lote(compra_data: schemas.CompraEntrada, db: Session = Depends(database.get_db)):
    try:
        # 1. Criar o Registro da Compra (Cabeçalho)
        nova_compra = models.Compra(
            local_compra=compra_data.local_compra,
            valor_total_nota=sum(item.preco_pago for item in compra_data.itens)
        )
        db.add(nova_compra)
        db.flush() # Gera o ID da compra para usar nos itens

        for item_in in compra_data.itens:
            # 2. Lógica de Produto (Busca ou Cria)
            # Usamos o nome normalizado para evitar duplicatas
            nome_normalizado = item_in.nome.strip().title()
            produto = db.query(models.Produto).filter(models.Produto.nome == nome_normalizado).first()
            
            if not produto:
                produto = models.Produto(
                    nome=nome_normalizado,
                    categoria=item_in.categoria,
                    unidade_medida=item_in.unidade,
                    estoque_atual=0.0
                )
                db.add(produto)
                db.flush()

            # 3. Criar o Item da Compra (Histórico de Preço)
            preco_uni = item_in.preco_pago / item_in.quantidade if item_in.quantidade > 0 else 0
            
            novo_item_compra = models.ItemCompra(
                produto_id=produto.id,
                compra_id=nova_compra.id,
                quantidade=item_in.quantidade,
                preco_unitario=preco_uni,
                validade_especifica=item_in.data_validade
            )
            db.add(novo_item_compra)

            # 4. Atualizar o Estado do Produto (Estoque e Validade)
            produto.estoque_atual += item_in.quantidade
            produto.ultima_validade = item_in.data_validade

        db.commit()
        return {"message": "Compra registrada e estoque atualizado!", "itens": len(compra_data.itens)}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao processar compra: {str(e)}")

@app.get("/produtos/alertas")
async def listar_alertas(db: Session = Depends(database.get_db)):
    hoje = datetime.date.today()
    proxima_semana = hoje + datetime.timedelta(days=7)
    
    # 1. Produtos com estoque baixo (ex: menos de 1 unidade/kg)
    estoque_baixo = db.query(models.Produto).filter(
        models.Produto.estoque_atual < 1.0,
        models.Produto.estoque_atual > 0 # Para não listar o que você já sabe que acabou
    ).all()
    
    # 2. Produtos vencendo em breve
    vencendo = db.query(models.Produto).filter(
        models.Produto.ultima_validade <= proxima_semana,
        models.Produto.ultima_validade >= hoje,
        models.Produto.estoque_atual > 0
    ).all()
    
    return {
        "estoque_baixo": estoque_baixo,
        "vencendo_em_breve": vencendo
    }

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
        "hejmai.main:app", host="0.0.0.0", port=8081, reload=True, app_dir="src"
    )
