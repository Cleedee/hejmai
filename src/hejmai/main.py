import asyncio
import datetime
from typing import List, Dict
import os
import httpx
from difflib import SequenceMatcher

from fastapi import Body, FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from hejmai import models, schemas, database, nlp, crud
from hejmai.validator import SanityChecker
from hejmai.analista_ia import AnalistaEstoque
from hejmai.config import config

# Cria as tabelas no SQLite ao iniciar
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Agente de Economia Doméstica")

processador_compras = nlp.ProcessadorCompras(model=config.MODEL())
processador_receitas = nlp.Receitas(model=config.MODEL())
analista_ia = AnalistaEstoque(model=config.MODEL())


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


@app.post("/ia/agente")
async def agente_hejmai(payload: schemas.PerguntaIA):
    """
    Recebe uma pergunta em linguagem natural e o Agente Coordenador
    decide qual ferramenta usar para responder.
    """
    try:
        from hejmai.agents.coordinator import get_coordinator_agent
        
        agent = get_coordinator_agent()
        resposta = await asyncio.to_thread(agent.run, payload.pergunta)
        
        return {
            "status": "sucesso",
            "resposta": resposta.content if hasattr(resposta, 'content') else str(resposta),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro no agente: {str(e)}"
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
    mes_atual = datetime.datetime.now().month
    ano_atual = datetime.datetime.now().year

    limites = (
        db.query(models.Budget).filter(
            models.Budget.mes_referencia == mes_atual,
            models.Budget.ano_referencia == ano_atual
        ).all()
    )

    performance = []
    for lim in limites:
        gasto_real = (
            db.query(func.sum(models.ItemCompra.preco_unitario * models.ItemCompra.quantidade))
            .join(models.Compra)
            .join(models.Produto)
            .filter(
                models.Produto.categoria == lim.categoria,
                models.Compra.excluida == 0,
                func.extract("month", models.Compra.data_compra) == mes_atual,
                func.extract("year", models.Compra.data_compra) == ano_atual,
            )
            .scalar()
            or 0.0
        )

        performance.append({
            "categoria": lim.categoria,
            "limite": lim.valor_limite,
            "real": gasto_real,
            "porcentagem": (gasto_real / lim.valor_limite) * 100 if lim.valor_limite > 0 else 0,
        })

    return performance


@app.get("/budgets")
async def listar_budgets(db: Session = Depends(database.get_db)):
    """Lista todos os budgets do mês atual."""
    mes_atual = datetime.datetime.now().month
    ano_atual = datetime.datetime.now().year

    budgets = (
        db.query(models.Budget).filter(
            models.Budget.mes_referencia == mes_atual,
            models.Budget.ano_referencia == ano_atual
        ).all()
    )

    return [
        {
            "id": b.id,
            "categoria": b.categoria,
            "valor_limite": b.valor_limite,
            "mes_referencia": b.mes_referencia,
            "ano_referencia": b.ano_referencia,
        }
        for b in budgets
    ]


@app.post("/budgets", status_code=status.HTTP_201_CREATED)
async def criar_budget(
    categoria: str,
    valor_limite: float,
    db: Session = Depends(database.get_db)
):
    """Cria ou atualiza um budget para categoria no mês atual."""
    mes_atual = datetime.datetime.now().month
    ano_atual = datetime.datetime.now().year

    existente = db.query(models.Budget).filter(
        models.Budget.categoria == categoria,
        models.Budget.mes_referencia == mes_atual,
        models.Budget.ano_referencia == ano_atual
    ).first()

    if existente:
        existente.valor_limite = valor_limite
        db.commit()
        return {"status": "atualizado", "id": existente.id}

    budget = models.Budget(
        categoria=categoria,
        valor_limite=valor_limite,
        mes_referencia=mes_atual,
        ano_referencia=ano_atual
    )
    db.add(budget)
    db.commit()
    return {"status": "criado", "id": budget.id}


@app.delete("/budgets/{budget_id}", status_code=status.HTTP_200_OK)
async def deletar_budget(budget_id: int, db: Session = Depends(database.get_db)):
    """Remove um budget."""
    budget = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget não encontrado")

    db.delete(budget)
    db.commit()
    return {"status": "deletado"}


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
    """
    Gera lista de compras detalhada agrupada por estabelecimento mais barato.

    Para cada produto com estoque baixo:
    1. Analisa histórico de preços por estabelecimento
    2. Calcula preço médio por estabelecimento
    3. Determina o estabelecimento mais barato
    4. Agrupa por estabelecimento (se diferença < 5%, considera irrelevante)
    """
    # 1. Busca produtos com estoque baixo
    itens = db.query(models.Produto).filter(models.Produto.estoque_atual < 1.0).all()

    if not itens:
        return {"por_estabelecimento": {}, "total_estimado": 0.0}

    produtos_analise = []

    for p in itens:
        # Busca histórico completo de preços deste produto
        historico = (
            db.query(models.ItemCompra, models.Compra)
            .join(models.Compra)
            .filter(
                models.ItemCompra.produto_id == p.id,
                models.Compra.excluida == 0,
            )
            .all()
        )

        if not historico:
            # Sem histórico - usa preço zero e sem estabelecimento definido
            produtos_analise.append({
                "nome": p.nome,
                "categoria": p.categoria,
                "preco_referencia": 0.0,
                "estoque": p.estoque_atual,
                "unidade": p.unidade_medida,
                "melhor_estabelecimento": "Sem histórico",
                "preco_medio": 0.0,
            })
            continue

        # Calcula preço médio por estabelecimento (ignora preços zero)
        precos_por_local = {}
        for item_compra, compra in historico:
            if item_compra.preco_unitario <= 0:
                continue
            local = compra.local_compra
            if local not in precos_por_local:
                precos_por_local[local] = []
            precos_por_local[local].append(item_compra.preco_unitario)

        # Calcula médias
        medias = {
            local: sum(precos) / len(precos)
            for local, precos in precos_por_local.items()
        }

        # Se todos os preços eram zero, marca como sem histórico válido
        if not medias:
            produtos_analise.append({
                "nome": p.nome,
                "categoria": p.categoria,
                "preco_referencia": 0.0,
                "estoque": p.estoque_atual,
                "unidade": p.unidade_medida,
                "melhor_estabelecimento": "Sem preço válido",
                "preco_medio": 0.0,
            })
            continue

        # Encontra o mais barato
        if medias:
            melhor_local = min(medias, key=medias.get)
            preco_medio = medias[melhor_local]
            menor_preco = min(medias.values())
            maior_preco = max(medias.values())

            # Verifica se diferença é relevante (> 5%)
            if maior_preco > 0:
                diff_percentual = ((maior_preco - menor_preco) / menor_preco) * 100
            else:
                diff_percentual = 0

            # Se diferença irrelevante, agrupa no local com mais produtos
            if diff_percentual < 5:
                # Conta compras por local
                contagem = {local: len(precos) for local, precos in precos_por_local.items()}
                melhor_local = max(contagem, key=contagem.get)
                preco_medio = sum(medias.values()) / len(medias)

            produtos_analise.append({
                "nome": p.nome,
                "categoria": p.categoria,
                "preco_referencia": round(preco_medio, 2),
                "estoque": p.estoque_atual,
                "unidade": p.unidade_medida,
                "melhor_estabelecimento": melhor_local,
                "preco_medio": round(preco_medio, 2),
                "diferenca_percentual": round(diff_percentual, 1) if diff_percentual >= 5 else 0,
            })

    # Agrupa por estabelecimento
    por_estabelecimento = {}
    for produto in produtos_analise:
        local = produto["melhor_estabelecimento"]
        if local not in por_estabelecimento:
            por_estabelecimento[local] = {
                "produtos": [],
                "total_estimado": 0.0,
            }
        por_estabelecimento[local]["produtos"].append(produto)
        por_estabelecimento[local]["total_estimado"] += produto["preco_referencia"]

    # Arredonda totais
    for local_data in por_estabelecimento.values():
        local_data["total_estimado"] = round(local_data["total_estimado"], 2)

    total_geral = sum(d["total_estimado"] for d in por_estabelecimento.values())

    return {
        "por_estabelecimento": por_estabelecimento,
        "total_estimado": round(total_geral, 2),
        "quantidade_produtos": len(produtos_analise),
    }


@app.get("/relatorios/historico-precos/{produto_id}")
async def historico_precos(produto_id: int, db: Session = Depends(database.get_db)):
    # Buscamos todos os itens de compra vinculados ao produto, ordenados por data
    historico = (
        db.query(models.ItemCompra)
        .join(models.Compra)
        .filter(
            models.ItemCompra.produto_id == produto_id,
            models.Compra.excluida == 0,  # Apenas compras ativas
        )
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


@app.get("/ia/analisar-precos/{produto_id}")
async def analisar_precos(produto_id: int, db: Session = Depends(database.get_db)):
    """
    Analisa o histórico de preços de um produto usando IA.
    Retorna insights sobre tendências, melhores preços e sugestões.
    """
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    historico = (
        db.query(models.ItemCompra)
        .join(models.Compra)
        .filter(
            models.ItemCompra.produto_id == produto_id,
            models.Compra.excluida == 0,
        )
        .order_by(models.Compra.data_compra)
        .all()
    )

    if not historico:
        return {"insight": f"Não há histórico de preços para {produto.nome}."}

    dados_precos = [
        {"data": item.compra.data_compra.strftime("%d/%m/%Y"), "preco": item.preco_unitario, "local": item.compra.local_compra}
        for item in historico
    ]

    precos = [d["preco"] for d in dados_precos]
    menor_preco = min(precos)
    maior_preco = max(precos)
    preco_medio = sum(precos) / len(precos)

    prompt = f"""Analise o histórico de preços do produto *{produto.nome}* e forneça insights úteis:

Histórico de compras:
{chr(10).join([f"- {d['data']}: R$ {d['preco']:.2f} em {d['local']}" for d in dados_precos])}

Estatísticas:
- Menor preço: R$ {menor_preco:.2f}
- Maior preço: R$ {maior_preco:.2f}
- Preço médio: R$ {preco_medio:.2f}

Responda em português de forma direta e útil. Inclua:
1. Tendência de preço (subindo, descendo, estável)
2. Melhor local para comprar
3. Se vale a pena comprar agora ou esperar

Máximo 3 frases."""
    
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{config.OLLAMA_BASE_URL()}/api/generate",
                json={
                    "model": config.MODEL(),
                    "prompt": prompt,
                    "stream": False,
                },
            )
            
            if response.status_code == 200:
                resultado = response.json()
                insight = resultado.get("response", "").strip()
                return {
                    "produto": produto.nome,
                    "dados": dados_precos,
                    "estatisticas": {
                        "menor_preco": menor_preco,
                        "maior_preco": maior_preco,
                        "preco_medio": round(preco_medio, 2),
                    },
                    "insight": insight,
                }
            else:
                return {"insight": f"Erro ao consultar IA: {response.status_code}"}
    except Exception as e:
        return {"insight": f"Erro na comunicação com Ollama: {str(e)}"}


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
    """
    Sugere receitas baseadas no estoque atual.
    1. Primeiro verifica receitas pré-definidas que podem ser feitas
    2. Se houver itens vencendo, complementa com sugestão de IA
    """
    # Buscar receitas viáveis com estoque
    sugestoes = crud.sugerir_receitas(db)

    completas = [s for s in sugestoes if s["pode_fazer"]]
    quase = [s for s in sugestoes if not s["pode_fazer"] and s["status"] == "quase"][:2]

    resposta = {
        "status": "sucesso",
        "receitas_completas": completas,
        "quase_prontas": quase,
    }

    # Se tem itens vencendo, usa IA para sugestão extra
    vencendo = (
        db.query(models.Produto)
        .filter(
            models.Produto.ultima_validade <= datetime.date.today() + datetime.timedelta(days=7),
            models.Produto.ultima_validade >= datetime.date.today(),
            models.Produto.estoque_atual > 0,
        )
        .all()
    )

    if vencendo:
        ingredientes = ", ".join([p.nome for p in vencendo])
        prompt = f"""
Ingredientes que vencem em breve: {ingredientes}.
Sugira UMA receita rápida que use esses itens. Máximo 3 passos."""

        try:
            response = await processador_receitas.client.chat(
                model=config.MODEL(),
                messages=[{"role": "user", "content": prompt}]
            )
            resposta["sugestao_ia"] = response["message"]["content"]
            resposta["itens_vencendo"] = [p.nome for p in vencendo]
        except Exception:
            pass

    return resposta


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


@app.get("/produtos/alertas")
async def listar_alertas(db: Session = Depends(database.get_db)):
    """Retorna alertas de estoque baixo e produtos vencendo."""
    hoje = datetime.date.today()
    proxima_semana = hoje + datetime.timedelta(days=7)

    estoque_baixo = (
        db.query(models.Produto)
        .filter(
            models.Produto.estoque_atual < 1.0,
            models.Produto.estoque_atual > 0,
        )
        .all()
    )

    vencendo = (
        db.query(models.Produto)
        .filter(
            models.Produto.ultima_validade <= proxima_semana,
            models.Produto.ultima_validade >= hoje,
            models.Produto.estoque_atual > 0,
        )
        .all()
    )

    return {
        "estoque_baixo": [
            {
                "id": p.id,
                "nome": p.nome,
                "categoria": p.categoria,
                "estoque_atual": p.estoque_atual,
                "unidade_medida": p.unidade_medida,
                "ultima_validade": p.ultima_validade,
            }
            for p in estoque_baixo
        ],
        "vencendo_em_breve": [
            {
                "id": p.id,
                "nome": p.nome,
                "categoria": p.categoria,
                "estoque_atual": p.estoque_atual,
                "unidade_medida": p.unidade_medida,
                "ultima_validade": p.ultima_validade,
            }
            for p in vencendo
        ],
    }


@app.get("/produtos/buscar")
async def buscar_produtos(
    termo: str = Query(..., min_length=1, description="Termo de busca por nome"),
    com_estoque: bool = Query(default=True, description="Filtrar apenas produtos com estoque"),
    db: Session = Depends(database.get_db)
):
    """
    Busca produtos por nome usando busca híbrida (ilike + fuzzy matching).
    
    Útil para encontrar produtos mesmo com erros de digitação ou variações
    (ex: 'pão' encontra 'Pães', 'arros' encontra 'Arroz').
    """
    from hejmai import crud
    
    produtos = crud.buscar_produtos_similares(db, termo, com_estoque=com_estoque)
    
    return [
        {
            "id": p.id,
            "nome": p.nome,
            "categoria": p.categoria,
            "estoque_atual": p.estoque_atual,
            "unidade_medida": p.unidade_medida,
            "ultima_validade": p.ultima_validade,
        }
        for p in produtos
    ]


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


@app.patch("/produtos/perda/{produto_id}")
async def registrar_perda(
    produto_id: int, quantidade: float, db: Session = Depends(database.get_db)
):
    """
    Registra perda/desperdício de um produto.
    
    Diferente do consumo, cria movimentação do tipo 'PERDA' para auditoria.
    """
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
        tipo="PERDA"
    )

    db.add(nova_mov)

    db.commit()
    db.refresh(produto)

    return {
        "mensagem": f"{quantidade} {produto.unidade_medida} de {produto.nome} registrado como perda.",
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
    print("Dados:", dados)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    return produto


@app.get("/produtos/{produto_id}")
async def detalhes_produto(
    produto_id: int,
    db: Session = Depends(database.get_db),
):
    """Retorna detalhes de um produto específico com histórico."""
    produto = crud.get_produto_por_id(db, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    historico_precos = crud.get_historico_precos(db, produto.nome)

    return {
        "id": produto.id,
        "nome": produto.nome,
        "categoria": produto.categoria,
        "unidade_medida": produto.unidade_medida,
        "estoque_atual": produto.estoque_atual,
        "ultima_validade": produto.ultima_validade,
        "tags": produto.tags.split(",") if produto.tags else [],
        "historico_precos": historico_precos,
    }


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
            excluida=0,  # Compra ativa por padrão
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
    Faz exclusão lógica de uma compra registrada e reverte o estoque dos produtos afetados.

    - Marca a compra como excluída (excluida=1)
    - Registra data da exclusão
    - Reverte o estoque dos produtos (subtrai quantidades)
    - Cria movimentação de ajuste para auditoria

    A compra não aparece mais nas consultas, mas permanece no banco para auditoria.
    """
    # Busca a compra (apenas se não estiver já excluída)
    compra = db.query(models.Compra).filter(
        models.Compra.id == compra_id,
        models.Compra.excluida == 0
    ).first()

    if not compra:
        raise HTTPException(
            status_code=404,
            detail=f"Compra (ID {compra_id}) não encontrada ou já está excluída"
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

        # Faz exclusão lógica da compra
        compra.excluida = 1
        compra.data_exclusao = datetime.datetime.now(datetime.timezone.utc)

        # Cria movimentação de ajuste para auditoria
        # Uma movimentação por produto afetado para rastreio correto
        for item in itens_compra:
            mov_ajuste = models.Movimentacao(
                produto_id=item.produto_id,
                quantidade=-item.quantidade,
                tipo="AJUSTE",
            )
            db.add(mov_ajuste)

        db.commit()

        return {
            "status": "sucesso",
            "mensagem": f"Compra {compra_id} marcada como excluída",
            "compra_excluida": {
                "id": compra_id,
                "local": compra.local_compra,
                "data": compra.data_compra,
                "valor_total": compra.valor_total_nota,
                "data_exclusao": compra.data_exclusao.isoformat(),
            },
            "produtos_afetados": produtos_afetados,
            "itens_afetados": len(itens_compra),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao excluir compra: {str(e)}"
        )


@app.patch("/compras/{compra_id}/restaurar", status_code=status.HTTP_200_OK)
async def restaurar_compra(
    compra_id: int,
    db: Session = Depends(database.get_db)
):
    """
    Restaura uma compra que foi excluída logicamente.

    - Marca a compra como ativa (excluida=0)
    - Limpa a data de exclusão
    - Reaplica o estoque dos produtos

    Útil para desfazer exclusões acidentais.
    """
    # Busca a compra excluída
    compra = db.query(models.Compra).filter(
        models.Compra.id == compra_id,
        models.Compra.excluida == 1
    ).first()

    if not compra:
        raise HTTPException(
            status_code=404,
            detail=f"Compra (ID {compra_id}) não encontrada ou não está excluída"
        )

    try:
        # Busca os itens da compra para reaplicar o estoque
        itens_compra = (
            db.query(models.ItemCompra)
            .filter(models.ItemCompra.compra_id == compra_id)
            .all()
        )

        produtos_afetados = []

        for item in itens_compra:
            produto = db.query(models.Produto).filter(
                models.Produto.id == item.produto_id
            ).first()

            if produto:
                estoque_anterior = produto.estoque_atual
                produto.estoque_atual += item.quantidade
                produtos_afetados.append({
                    "nome": produto.nome,
                    "quantidade_adicionada": item.quantidade,
                    "estoque_anterior": estoque_anterior,
                    "estoque_atual": produto.estoque_atual,
                })

        # Restaura a compra
        compra.excluida = 0
        compra.data_exclusao = None

        # Cria movimentação de ajuste para auditoria
        # Uma movimentação por produto afetado para rastreio correto
        for item in itens_compra:
            mov_ajuste = models.Movimentacao(
                produto_id=item.produto_id,
                quantidade=item.quantidade,
                tipo="AJUSTE",
            )
            db.add(mov_ajuste)

        db.commit()

        return {
            "status": "sucesso",
            "mensagem": f"Compra {compra_id} restaurada com sucesso",
            "compra_restaurada": {
                "id": compra_id,
                "local": compra.local_compra,
                "data": compra.data_compra,
                "valor_total": compra.valor_total_nota,
            },
            "produtos_afetados": produtos_afetados,
            "itens_afetados": len(itens_compra),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao restaurar compra: {str(e)}"
        )


@app.get("/compras/excluidas")
async def listar_compras_excluidas(db: Session = Depends(database.get_db)):
    """
    Lista todas as compras que foram excluídas logicamente.

    Útil para auditoria e para permitir restauração de exclusões acidentais.
    """
    compras = (
        db.query(models.Compra)
        .filter(models.Compra.excluida == 1)
        .order_by(models.Compra.data_exclusao.desc())
        .all()
    )

    return [
        {
            "id": c.id,
            "local_compra": c.local_compra,
            "data_compra": c.data_compra,
            "valor_total_nota": c.valor_total_nota,
            "data_exclusao": c.data_exclusao.isoformat() if c.data_exclusao else None,
        }
        for c in compras
    ]


@app.get("/compras/recentes")
async def listar_compras_recentes(
    limite: int = Query(default=5, ge=1, le=20, description="Número de compras a retornar (1-20)"),
    db: Session = Depends(database.get_db)
):
    """
    Lista as últimas compras realizadas (não excluídas).
    
    Retorna local, data e valor total de cada compra.
    """
    compras = (
        db.query(models.Compra)
        .filter(models.Compra.excluida == 0)
        .order_by(models.Compra.data_compra.desc(), models.Compra.id.desc())
        .limit(limite)
        .all()
    )

    return [
        {
            "id": c.id,
            "local_compra": c.local_compra,
            "data_compra": c.data_compra,
            "valor_total_nota": c.valor_total_nota,
            "quantidade_itens": len(c.itens) if c.itens else 0,
        }
        for c in compras
    ]


@app.put("/compras/{compra_id}", status_code=status.HTTP_200_OK)
async def editar_compra(
    compra_id: int,
    update: schemas.CompraUpdate,
    db: Session = Depends(database.get_db)
):
    """
    Edita uma compra existente.
    
    Permite alterar o local de compra e/ou a data da compra.
    Não altera os itens da compra - para isso, exclua e registre novamente.
    """
    compra = db.query(models.Compra).filter(models.Compra.id == compra_id).first()
    
    if not compra:
        raise HTTPException(
            status_code=404,
            detail=f"Compra (ID {compra_id}) não encontrada"
        )
    
    try:
        # Obtém os campos enviados (apenas os não-None)
        dados = update.model_dump(exclude_unset=True)
        
        if not dados:
            raise HTTPException(
                status_code=400,
                detail="Nenhum dado fornecido para atualização"
            )
        
        # Aplica as atualizações
        for campo, valor in dados.items():
            setattr(compra, campo, valor)
        
        db.commit()
        db.refresh(compra)
        
        return {
            "status": "sucesso",
            "mensagem": f"Compra {compra_id} atualizada com sucesso",
            "compra": {
                "id": compra.id,
                "local_compra": compra.local_compra,
                "data_compra": compra.data_compra,
                "valor_total_nota": compra.valor_total_nota,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar compra: {str(e)}"
        )


# =============================================================================
# Endpoints de Receitas
# =============================================================================


@app.get("/receitas", response_model=List[dict])
def listar_receitas(
    ativas: bool = True,
    db: Session = Depends(database.get_db)
):
    """Lista todas as receitas."""
    receitas = crud.get_todas_receitas(db, ativas=ativas)
    return [
        {
            "id": r.id,
            "nome": r.nome,
            "descricao": r.descricao,
            "modo_preparo": r.modo_preparo,
            "porcoes": r.porcoes,
            "tags": r.tags.split(",") if r.tags else [],
            "ativa": r.ativa,
            "itens": [
                {
                    "id": i.id,
                    "produto_id": i.produto_id,
                    "produto_nome": i.produto.nome if i.produto else None,
                    "quantidade": i.quantidade_porcao,
                    "observacao": i.observacao,
                }
                for i in r.itens
            ],
        }
        for r in receitas
    ]


@app.get("/receitas/sugerir")
def sugerir_receitas_endpoint(
    db: Session = Depends(database.get_db)
):
    """Sugere receitas baseadas no estoque atual."""
    return crud.sugerir_receitas(db)


@app.get("/receitas/{receita_id}", response_model=dict)
def buscar_receita(
    receita_id: int,
    db: Session = Depends(database.get_db)
):
    """Busca uma receita pelo ID com verificação de estoque."""
    receita = crud.get_receita_por_id(db, receita_id)
    if not receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    pode_fazer, faltantes = crud.receita_pode_ser_feita(db, receita)

    return {
        "id": receita.id,
        "nome": receita.nome,
        "descricao": receita.descricao,
        "modo_preparo": receita.modo_preparo,
        "porcoes": receita.porcoes,
        "tags": receita.tags.split(",") if receita.tags else [],
        "ativa": receita.ativa,
        "pode_fazer": pode_fazer,
        "itens": [
            {
                "id": i.id,
                "produto_id": i.produto_id,
                "produto_nome": i.produto.nome if i.produto else None,
                "quantidade": i.quantidade_porcao,
                "estoque_atual": i.produto.estoque_atual if i.produto else 0,
                "observacao": i.observacao,
            }
            for i in receita.itens
        ],
        "itens_faltantes": faltantes,
    }


@app.post("/receitas", status_code=status.HTTP_201_CREATED)
def criar_receita_endpoint(
    receita: schemas.ReceitaCreate,
    db: Session = Depends(database.get_db)
):
    """Cria uma nova receita com seus itens.
    
    Ingredientes sem produto_id são marcados como pendentes.
    """
    existente = db.query(models.Receita).filter(
        models.Receita.nome == receita.nome
    ).first()
    if existente:
        raise HTTPException(
            status_code=400,
            detail=f"Já existe uma receita com o nome '{receita.nome}'"
        )

    receita_data = {
        "nome": receita.nome,
        "descricao": receita.descricao,
        "modo_preparo": receita.modo_preparo,
        "porcoes": receita.porcoes,
        "tags": ",".join(receita.tags) if receita.tags else None,
    }

    itens_data = [
        {
            "produto_id": item.produto_id,
            "quantidade_porcao": item.quantidade_porcao,
            "observacao": item.observacao,
        }
        for item in receita.itens
    ]

    try:
        nova, pendentes = crud.criar_receita(db, receita_data, itens_data)
        
        response = {
            "status": "sucesso",
            "mensagem": f"Receita '{nova.nome}' criada",
            "id": nova.id,
            "total_itens": len(itens_data),
        }
        
        if pendentes:
            response["pendentes"] = pendentes
            response["mensagem"] += f" ({len(pendentes)} ingredientes pendentes)"
        
        return response
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/receitas/{receita_id}", status_code=status.HTTP_200_OK)
def atualizar_receita_endpoint(
    receita_id: int,
    receita: schemas.ReceitaUpdate,
    db: Session = Depends(database.get_db)
):
    """Atualiza dados de uma receita."""
    existente = crud.get_receita_por_id(db, receita_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    dados = receita.model_dump(exclude_unset=True)
    if "tags" in dados and dados["tags"]:
        dados["tags"] = ",".join(dados["tags"])

    try:
        atualizada = crud.atualizar_receita(db, receita_id, dados)
        return {
            "status": "sucesso",
            "mensagem": f"Receita '{atualizada.nome}' atualizada",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/receitas/{receita_id}", status_code=status.HTTP_200_OK)
def deletar_receita_endpoint(
    receita_id: int,
    db: Session = Depends(database.get_db)
):
    """Soft delete - desativa a receita."""
    if not crud.deletar_receita(db, receita_id):
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    return {"status": "sucesso", "mensagem": "Receita desativada"}


@app.patch("/receitas/{receita_id}/itens/{item_id}")
def atualizar_item_receita_endpoint(
    receita_id: int,
    item_id: int,
    produto_id: int = None,
    quantidade_porcao: float = None,
    observacao: str = None,
    db: Session = Depends(database.get_db)
):
    """Atualiza um ingrediente de receita (produto, quantidade ou observação)."""
    receita = crud.get_receita_por_id(db, receita_id)
    if not receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    
    item = next((i for i in receita.itens if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    try:
        atualizado = crud.atualizar_item_receita(
            db, item_id, produto_id, quantidade_porcao, observacao
        )
        return {
            "status": "sucesso",
            "item": {
                "id": atualizado.id,
                "produto_id": atualizado.produto_id,
                "produto_nome": atualizado.produto.nome if atualizado.produto else None,
                "quantidade_porcao": atualizado.quantidade_porcao,
                "observacao": atualizado.observacao,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/receitas/{receita_id}/itens/{item_id}")
def remover_item_receita_endpoint(
    receita_id: int,
    item_id: int,
    db: Session = Depends(database.get_db)
):
    """Remove um ingrediente de receita."""
    receita = crud.get_receita_por_id(db, receita_id)
    if not receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    
    item = next((i for i in receita.itens if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    if not crud.remover_item_receita(db, item_id):
        raise HTTPException(status_code=500, detail="Erro ao remover item")
    
    return {"status": "sucesso", "mensagem": "Item removido"}


@app.get("/receitas/{receita_id}/pendentes")
def receita_pendentes_endpoint(
    receita_id: int,
    db: Session = Depends(database.get_db)
):
    """Lista ingredientes pendentes de uma receita."""
    receita = crud.get_receita_por_id(db, receita_id)
    if not receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    pendentes = crud.receita_ingredientes_pendentes(db, receita_id)
    return {
        "receita_id": receita_id,
        "receita_nome": receita.nome,
        "total_pendentes": len(pendentes),
        "pendentes": pendentes,
    }


# =============================================================================
# Start
# =============================================================================


def start():
    import uvicorn

    uvicorn.run(
        "hejmai.main:app", host="0.0.0.0", port=8081, reload=True, app_dir="src"
    )
