import datetime
from typing import List, Dict
import os
from difflib import SequenceMatcher


from fastapi import Body, FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

from hejmai import models, schemas, database, nlp, crud
from hejmai.validator import SanityChecker
from hejmai.analista_ia import AnalistaEstoque

load_dotenv()

MODEL = os.getenv("MODEL") or "llama3"

# Cria as tabelas no SQLite ao iniciar
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Agente de Economia Doméstica")

processador_compras = nlp.ProcessadorCompras(model=MODEL)
processador_receitas = nlp.Receitas(model=MODEL)
analista_ia = AnalistaEstoque(model=MODEL)


@app.get("/")
def read_root():
    return {"status": "Agente Online", "ano": 2026}

@app.post("/ia/perguntar")
async def processar_pergunta_ia(payload: schemas.PerguntaIA, db: Session = Depends(database.get_db)):
    """
    Recebe uma pergunta em linguagem natural, converte para SQL,
    executa no SQLite e retorna a interpretação da IA.
    """
    try:
        # 1. O Analista faz a mágica (SQL -> Execução -> Resposta)
        resposta, query_gerada = await analista_ia.responder_pergunta(payload.pergunta, db)
        
        # Log para debug no terminal do container
        print(f"🤖 Pergunta: {payload.pergunta}")
        print(f"💾 SQL Gerado: {query_gerada}")
        
        return {
            "status": "sucesso",
            "resposta": resposta,
            "query": query_gerada  # Enviamos de volta para o Bot mostrar se for modo debug
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno no processamento da IA: {str(e)}"
        )


@app.get("/estoque/resumo-geral")
async def resumo_estoque(db: Session = Depends(database.get_db)):
    # Buscamos todos os produtos com estoque positivo, ordenados por categoria
    produtos = (
        db.query(models.Produto)
        .filter(models.Produto.estoque_atual > 0)
        .order_by(models.Produto.categoria, models.Produto.ultima_validade)
        .all()
    )

    return produtos


@app.post("/categoria", status_code=status.HTTP_201_CREATED)
async def create_categoria(
    categoria: schemas.CategoriaCreate, db: Session = Depends(database.get_db)
):
    nova_categoria = models.Categoria(nome=categoria.nome)
    db.add(nova_categoria)
    db.commit()
    return nova_categoria


@app.get("/categorias")
async def lista_todas_categorias(db: Session = Depends(database.get_db)):
    categorias = crud.traga_todas_categorias(db)
    return categorias


@app.get("/relatorios/performance-budget")
async def performance_budget(db: Session = Depends(database.get_db)):
    mes_atual = 4  # Abril
    ano_atual = 2026

    # 1. Busca os limites definidos
    limites = (
        db.query(models.Budget).filter(models.Budget.mes_referencia == mes_atual).all()
    )

    performance = []
    for lim in limites:
        # 2. Soma quanto já foi gasto nessa categoria no mês
        gasto_real = (
            db.query(func.sum(models.ItemCompra.preco_pago))
            .join(models.Compra)
            .filter(
                models.Produto.categoria == lim.categoria,
                func.extract("month", models.Compra.data_compra) == mes_atual,
                func.extract("year", models.Compra.data_compra) == ano_atual,
            )
            .scalar()
            or 0.0
        )

        performance.append(
            {
                "categoria": lim.categoria,
                "limite": lim.valor_limite,
                "real": gasto_real,
                "porcentagem": (
                    (gasto_real / lim.valor_limite) * 100 if lim.valor_limite > 0 else 0
                ),
            }
        )

    return performance


@app.get("/produtos/todos")
async def listar_todos_produtos(db: Session = Depends(database.get_db)):
    produtos = db.query(models.Produto).all()
    return produtos


@app.get("/produtos/similar")
async def encontrar_produtos_similares(
    limite_similaridade: float = Query(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Limiar de similaridade (0.0 a 1.0). Valores mais altos retornam apenas produtos muito similares."
    ),
    db: Session = Depends(database.get_db)
):
    """
    Encontra grupos de produtos com nomes similares para possível unificação.
    
    Usa SequenceMatcher para calcular similaridade entre nomes de produtos.
    Retorna grupos de produtos que têm similaridade acima do limiar configurado.
    """
    produtos = db.query(models.Produto).all()
    
    if not produtos:
        return {"grupos": []}
    
    # Lista de produtos já processados
    processados = set()
    grupos_similares = []
    
    for i, produto_a in enumerate(produtos):
        if produto_a.id in processados:
            continue
            
        grupo = {
            "produto_base": {
                "id": produto_a.id,
                "nome": produto_a.nome,
                "categoria": produto_a.categoria,
                "estoque_atual": produto_a.estoque_atual,
            },
            "similares": []
        }
        
        for j, produto_b in enumerate(produtos):
            if i >= j:  # Pula o próprio e já comparados
                continue
                
            if produto_b.id in processados:
                continue
            
            # Calcula similaridade entre os nomes (case-insensitive)
            similaridade = SequenceMatcher(
                None, 
                produto_a.nome.lower(), 
                produto_b.nome.lower()
            ).ratio()
            
            if similaridade >= limite_similaridade:
                grupo["similares"].append({
                    "id": produto_b.id,
                    "nome": produto_b.nome,
                    "categoria": produto_b.categoria,
                    "estoque_atual": produto_b.estoque_atual,
                    "similaridade": round(similaridade, 2)
                })
                processados.add(produto_b.id)
        
        # Adiciona o grupo apenas se houver similares
        if grupo["similares"]:
            grupos_similares.append(grupo)
            processados.add(produto_a.id)
    
    return {"grupos": grupos_similares}


@app.get("/produtos/lista-compras-detalhada")
async def gerar_lista_detalhada(db: Session = Depends(database.get_db)):
    # 1. Busca produtos com estoque baixo
    itens = db.query(models.Produto).filter(models.Produto.estoque_atual < 1.0).all()

    lista_final = []
    for p in itens:
        # Busca o último preço pago para servir de âncora
        ultimo_item = (
            db.query(models.ItemCompra)
            .filter(models.ItemCompra.produto_id == p.id)
            .order_by(models.ItemCompra.id.desc())
            .first()
        )

        preco_ref = ultimo_item.preco_unitario if ultimo_item else 0.0

        lista_final.append(
            {
                "nome": p.nome,
                "categoria": p.categoria,
                "preco_referencia": preco_ref,
                "estoque": p.estoque_atual,
                "unidade": p.unidade_medida,
            }
        )

    return lista_final


@app.get("/relatorios/historico-precos/{produto_id}")
async def historico_precos(produto_id: int, db: Session = Depends(database.get_db)):
    # Buscamos todos os itens de compra vinculados ao produto, ordenados por data
    historico = (
        db.query(models.ItemCompra)
        .join(models.Compra)
        .filter(models.ItemCompra.produto_id == produto_id)
        .order_by(models.Compra.data_compra)
        .all()
    )

    return [
        {
            "data": item.compra.data_compra,
            "preco": item.preco_unitario,
            "local": item.compra.local_compra,
        }
        for item in historico
    ]


@app.get("/relatorios/previsao-gastos")
async def prever_gastos(db: Session = Depends(database.get_db)):
    # 1. Busca produtos que estão abaixo do limite (estoque < 1.0)
    itens_em_falta = (
        db.query(models.Produto).filter(models.Produto.estoque_atual < 1.0).all()
    )

    previsao_total = 0.0
    detalhes = []

    for produto in itens_em_falta:
        # 2. Busca o PREÇO MÉDIO ou ÚLTIMO PREÇO desse produto no histórico
        ultimo_item = (
            db.query(models.ItemCompra)
            .filter(models.ItemCompra.produto_id == produto.id)
            .order_by(models.ItemCompra.id.desc())
            .first()
        )

        preco_base = ultimo_item.preco_unitario if ultimo_item else 0.0

        # Simulamos a compra de uma "unidade padrão" (ex: 1kg ou 1 pack)
        # Você pode ajustar isso para a 'quantidade_ideal' se tiver esse campo
        quantidade_estimada = 1.0
        custo_estimado = preco_base * quantidade_estimada

        previsao_total += custo_estimado
        detalhes.append(
            {
                "produto": produto.nome,
                "ultimo_preco": preco_base,
                "custo_estimado": custo_estimado,
            }
        )

    return {"valor_total_estimado": round(previsao_total, 2), "itens": detalhes}


@app.post("/processar-entrada-livre")
async def processar_texto_bot(
    payload: dict = Body(...), db: Session = Depends(database.get_db)
):
    texto_bruto = payload.get("texto")

    # 1. Inteligência Artificial: Transforma texto em dados
    dados_extraidos = await processador_compras.extrair_dados(texto_bruto)

    # 2. Realiza o Sanity Check
    todos_alertas = []
    for item in dados_extraidos["itens"]:
        # Refina a categoria vinda do Ollama
        item["categoria"] = await nlp.refinamento_categoria(item["categoria"], db)
        alertas = SanityChecker.validar_item(item)
        todos_alertas.extend(alertas)

    # 3. Persistência Relacional: Salva em Produto, Compra e ItemCompra
    # Reaproveitamos a lógica de registrar_compra_lote que criamos antes
    resultado = await registrar_compra_lote(
        schemas.CompraEntrada(**dados_extraidos), db
    )

    status_msg = "✅ Registro concluído."
    if todos_alertas:
        # Se houver alertas, mudamos o tom da mensagem para o Bot avisar você
        status_msg = "⚠️ Registro feito com OBSERVAÇÕES:\n- " + "\n- ".join(
            todos_alertas
        )

    return {
        "status": "sucesso",
        "dados_processados": dados_extraidos,
        "mensagem_bot": f"{status_msg}\nRegistrado: {len(dados_extraidos['itens'])} itens no {dados_extraidos['local_compra'] or 'estoque'}.",
    }


@app.get("/sugerir-receita")
async def sugerir_receita(db: Session = Depends(database.get_db)):

    vencendo = listar_itens_vencendo(db)

    receita = await processador_receitas.sugerir_receita(vencendo)

    return {"status": "sucesso", "receita": receita}


@app.get("/produtos/lista-compras")
async def gerar_dados_lista(db: Session = Depends(database.get_db)):
    # Filtramos produtos que estão abaixo de um limite aceitável (ex: 1.0)
    # e ordenamos por categoria para facilitar a navegação no mercado
    itens_em_falta = (
        db.query(models.Produto)
        .filter(models.Produto.estoque_atual < 1.0)
        .order_by(models.Produto.categoria)
        .all()
    )

    return itens_em_falta


@app.patch("/produtos/consumir/{produto_id}")
async def consumir_produto(
    produto_id: int, quantidade: float, db: Session = Depends(database.get_db)
):
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    if produto.estoque_atual < quantidade:
        raise HTTPException(
            status_code=400,
            detail=f"Estoque insuficiente. Disponível: {produto.estoque_atual}",
        )

    produto.estoque_atual -= quantidade

    nova_mov = models.Movimentacao(
        produto_id=produto_id,
        quantidade=-quantidade,
        tipo="CONSUMO"
    )

    db.add(nova_mov)

    db.commit()
    db.refresh(produto)

    return {
        "mensagem": f"{quantidade} {produto.unidade_medida} de {produto.nome} consumidos.",
        "estoque_restante": produto.estoque_atual,
    }


@app.patch("/produtos/{produto_id}")
async def editar_produto(
    produto_id: int,
    update: schemas.ProdutoUpdate,
    db: Session = Depends(database.get_db),
):
    dados = update.model_dump(exclude_unset=True)
    if not dados:
        raise HTTPException(
            status_code=400, detail="Nenhum dado fornecido para atualização"
        )

    produto = crud.atualizar_produto(db, produto_id, dados)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    return produto


@app.post("/produtos/unificar")
async def unificar_produtos(
    unificacao: schemas.UnificacaoProdutos,
    db: Session = Depends(database.get_db)
):
    """
    Unifica múltiplos produtos em um único produto principal.
    
    - Soma os estoques de todos os produtos no produto principal
    - Atualiza a validade para a mais recente entre todos
    - Transfere o histórico de compras (itens_compra) para o produto principal
    - Remove os produtos unificados do banco
    
    Útil para consolidar produtos duplicados com nomes ligeiramente diferentes.
    """
    produto_principal_id = unificacao.produto_principal_id
    produtos_para_unificar_ids = unificacao.produtos_para_unificar
    
    # Validações iniciais
    if not produtos_para_unificar_ids:
        raise HTTPException(
            status_code=400, 
            detail="Nenhum produto foi especificado para unificação"
        )
    
    if produto_principal_id in produtos_para_unificar_ids:
        raise HTTPException(
            status_code=400,
            detail="O produto principal não pode estar na lista de produtos para unificar"
        )
    
    # Busca o produto principal
    produto_principal = db.query(models.Produto).filter(
        models.Produto.id == produto_principal_id
    ).first()
    
    if not produto_principal:
        raise HTTPException(
            status_code=404,
            detail=f"Produto principal (ID {produto_principal_id}) não encontrado"
        )
    
    # Busca todos os produtos que serão unificados
    produtos_secundarios = (
        db.query(models.Produto)
        .filter(models.Produto.id.in_(produtos_para_unificar_ids))
        .all()
    )
    
    if len(produtos_secundarios) != len(produtos_para_unificar_ids):
        raise HTTPException(
            status_code=404,
            detail="Um ou mais produtos para unificar não foram encontrados"
        )
    
    try:
        estoque_total = produto_principal.estoque_atual or 0.0
        validade_mais_recente = produto_principal.ultima_validade
        
        for produto_sec in produtos_secundarios:
            # 1. Somar estoques
            estoque_total += produto_sec.estoque_atual or 0.0
            
            # 2. Manter a validade mais recente
            if produto_sec.ultima_validade:
                if not validade_mais_recente or produto_sec.ultima_validade > validade_mais_recente:
                    validade_mais_recente = produto_sec.ultima_validade
            
            # 3. Transferir histórico de compras (ItemCompra)
            itens_compra = db.query(models.ItemCompra).filter(
                models.ItemCompra.produto_id == produto_sec.id
            ).all()
            
            for item in itens_compra:
                item.produto_id = produto_principal_id
            
            # 4. Transferir movimentações
            movimentacoes = db.query(models.Movimentacao).filter(
                models.Movimentacao.produto_id == produto_sec.id
            ).all()
            
            for mov in movimentacoes:
                mov.produto_id = produto_principal_id
            
            # 5. Remover produto secundário
            db.delete(produto_sec)
        
        # Atualiza produto principal com estoque consolidado e validade
        produto_principal.estoque_atual = estoque_total
        produto_principal.ultima_validade = validade_mais_recente
        
        # Cria registro de movimentação para auditoria
        total_unificado = sum(p.estoque_atual or 0.0 for p in produtos_secundarios)
        if total_unificado > 0:
            mov_unificacao = models.Movimentacao(
                produto_id=produto_principal_id,
                quantidade=total_unificado,
                tipo="UNIFICACAO",
            )
            db.add(mov_unificacao)
        
        db.commit()
        
        return {
            "status": "sucesso",
            "mensagem": f"{len(produtos_secundarios)} produtos unificados em '{produto_principal.nome}'",
            "estoque_consolidado": estoque_total,
            "produtos_removidos": len(produtos_secundarios),
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao unificar produtos: {str(e)}"
        )


@app.post("/compras/registrar-lote", status_code=status.HTTP_201_CREATED)
async def registrar_compra_lote(
    compra_data: schemas.CompraEntrada, db: Session = Depends(database.get_db)
):
    try:
        # 1. Criar o Registro da Compra (Cabeçalho)
        nova_compra = models.Compra(
            local_compra=compra_data.local_compra,
            valor_total_nota=sum(item.preco_pago for item in compra_data.itens),
        )
        db.add(nova_compra)
        db.flush()  # Gera o ID da compra para usar nos itens

        for item_in in compra_data.itens:
            # 2. Lógica de Produto (Busca ou Cria)
            # Usamos o nome normalizado para evitar duplicatas
            nome_normalizado = item_in.nome.strip().title()
            produto = (
                db.query(models.Produto)
                .filter(models.Produto.nome == nome_normalizado)
                .first()
            )

            if not produto:
                produto = models.Produto(
                    nome=nome_normalizado,
                    categoria=item_in.categoria,
                    unidade_medida=item_in.unidade,
                    estoque_atual=0.0,
                )
                db.add(produto)
                db.flush()

            # 3. Criar o Item da Compra (Histórico de Preço)
            preco_uni = (
                item_in.preco_pago / item_in.quantidade if item_in.quantidade > 0 else 0
            )

            novo_item_compra = models.ItemCompra(
                produto_id=produto.id,
                compra_id=nova_compra.id,
                quantidade=item_in.quantidade,
                preco_unitario=preco_uni,
                validade_especifica=item_in.data_validade,
            )
            db.add(novo_item_compra)

            # 4. Atualizar o Estado do Produto (Estoque e Validade)
            produto.estoque_atual += item_in.quantidade
            produto.ultima_validade = item_in.data_validade

        db.commit()
        return {
            "message": "Compra registrada e estoque atualizado!",
            "itens": len(compra_data.itens),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Erro ao processar compra: {str(e)}"
        )


@app.delete("/compras/{compra_id}", status_code=status.HTTP_200_OK)
async def excluir_compra(
    compra_id: int,
    db: Session = Depends(database.get_db)
):
    """
    Exclui uma compra registrada e reverte o estoque dos produtos afetados.
    
    - Remove os itens da compra (ItemCompra)
    - Subtrai as quantidades do estoque dos produtos
    - Remove a compra (Compra)
    - Cria movimentação de ajuste para auditoria
    
    Útil para corrigir registros incorretos ou duplicados.
    """
    # Busca a compra
    compra = db.query(models.Compra).filter(
        models.Compra.id == compra_id
    ).first()
    
    if not compra:
        raise HTTPException(
            status_code=404,
            detail=f"Compra (ID {compra_id}) não encontrada"
        )
    
    try:
        # Busca os itens da compra para reverter o estoque
        itens_compra = (
            db.query(models.ItemCompra)
            .filter(models.ItemCompra.compra_id == compra_id)
            .all()
        )
        
        produtos_afetados = []
        
        for item in itens_compra:
            # Busca o produto
            produto = db.query(models.Produto).filter(
                models.Produto.id == item.produto_id
            ).first()
            
            if produto:
                # Reverte o estoque (subtrai a quantidade que foi adicionada)
                produto.estoque_atual = max(0, produto.estoque_atual - item.quantidade)
                produtos_afetados.append({
                    "nome": produto.nome,
                    "quantidade_removida": item.quantidade,
                    "estoque_anterior": produto.estoque_atual + item.quantidade,
                    "estoque_atual": produto.estoque_atual,
                })
            
            # Remove o item da compra
            db.delete(item)
        
        # Remove a compra
        db.delete(compra)
        
        # Cria movimentação de ajuste para auditoria
        if itens_compra:
            mov_ajuste = models.Movimentacao(
                produto_id=itens_compra[0].produto_id if len(itens_compra) == 1 else None,
                quantidade=-sum(item.quantidade for item in itens_compra),
                tipo="AJUSTE",
            )
            db.add(mov_ajuste)
        
        db.commit()
        
        return {
            "status": "sucesso",
            "mensagem": f"Compra {compra_id} excluída com sucesso",
            "compra_excluida": {
                "id": compra_id,
                "local": compra.local_compra,
                "data": compra.data_compra,
                "valor_total": compra.valor_total_nota,
            },
            "produtos_afetados": produtos_afetados,
            "itens_removidos": len(itens_compra),
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao excluir compra: {str(e)}"
        )


@app.get("/produtos/alertas")
async def listar_alertas(db: Session = Depends(database.get_db)):
    hoje = datetime.date.today()
    proxima_semana = hoje + datetime.timedelta(days=7)

    # 1. Produtos com estoque baixo (ex: menos de 1 unidade/kg)
    estoque_baixo = (
        db.query(models.Produto)
        .filter(
            models.Produto.estoque_atual < 1.0,
            models.Produto.estoque_atual
            > 0,  # Para não listar o que você já sabe que acabou
        )
        .all()
    )

    # 2. Produtos vencendo em breve
    vencendo = (
        db.query(models.Produto)
        .filter(
            models.Produto.ultima_validade <= proxima_semana,
            models.Produto.ultima_validade >= hoje,
            models.Produto.estoque_atual > 0,
        )
        .all()
    )

    return {"estoque_baixo": estoque_baixo, "vencendo_em_breve": vencendo}


def start():
    import uvicorn

    uvicorn.run(
        "hejmai.main:app", host="0.0.0.0", port=8081, reload=True, app_dir="src"
    )
