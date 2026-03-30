import json
from datetime import date, timedelta

import streamlit as st
import httpx
import pandas as pd
import altair as alt


st.set_page_config(page_title="Hejmai - Lab de Compras", layout="wide")

st.title("🧪 Hejmai NLP Playground")
st.subheader("Teste de Extração com Ollama")

# URL do seu backend FastAPI
API_URL = "http://localhost:8081"


def interface_carga_manual():
    st.header("📋 Inventário Manual de Estoque")
    st.markdown("Preencha a tabela abaixo com os itens que você já possui.")

    if 'df_carga' not in st.session_state:
        
        st.session_state.df_carga = pd.DataFrame(
            [
                {
                    "nome": "",
                    "categoria": "Mercearia",
                    "quantidade": 1.0,
                    "unidade": "un",
                    "preco_pago": 0.0,
                    "data_validade": date.today() + timedelta(days=90),
                }
            ]
        )

    # 2. Editor de Dados (Interface estilo Excel)
    # num_rows="dynamic" permite que você clique no '+' para adicionar itens

    categorias_permitidas = []
    res = httpx.get(f"{API_URL}/categorias")
    if res.status_code != 200:
        st.error("Não foi possível trazer as categorias.")
    else:
        categorias_permitidas = [cat["nome"] for cat in res.json()]

    df_editado = st.data_editor(
        st.session_state.df_carga,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "categoria": st.column_config.SelectboxColumn(
                options=categorias_permitidas
            ),
            "data_validade": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "preco_pago": st.column_config.NumberColumn(format="R$ %.2f"),
        },
        key="editor_manual",
    )

    col1, col2 = st.columns([1, 5])

    with col1:
        if st.button("Limpar Tabela 🗑️"):
            # Resetamos o DataFrame no estado da sessão
            del st.session_state.df_carga
            if "carga_manual_editor" in st.session_state:
                del st.session_state.carga_manual_editor
            st.rerun() # Força o refresh para limpar a UI
    with col2:

        # 3. Botão de Submissão
        if st.button("Finalizar Carga deste Bloco 📥", type="primary"):
            # Limpar linhas vazias (onde o nome não foi preenchido)
            df_final = df_editado[df_editado["nome"] != ""].copy()

            if df_final.empty:
                st.warning("A tabela está vazia ou os itens não têm nome.")
            else:
                with st.spinner("Salvando no banco de dados..."):
                    df_final["data_validade"] = pd.to_datetime(
                        df_final["data_validade"]
                    ).dt.strftime("%Y-%m-%d")
                    payload = {
                        "local_compra": "Inventário Inicial",
                        "itens": df_final.to_dict("records"),
                    }
                    # Ajuste a porta se o seu FastAPI estiver em outra
                    try:
                        res = httpx.post(
                            f"{API_URL}/compras/registrar-lote", json=payload, timeout=20.0
                        )
                        if res.status_code == 201:
                            st.success(
                                f"✅ {len(df_final)} itens adicionados ao seu estoque!"
                            )
                            st.balloons()
                            del st.session_state.df_carga
                            st.rerun()
                        else:
                            st.error(f"Erro ao salvar: {res.text}")
                    except Exception as e:
                        st.error(f"Erro de conexão com o backend: {e}")


col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📥 Entrada de Texto")
    texto_livre = st.text_area(
        "Cole aqui a nota do Keep ou descreva a compra:",
        placeholder="Ex: Comprei 2kg de carne por 80 reais no Carvalho Super...",
        height=300,
    )

    btn_processar = st.button("Processar com Ollama 🚀")

with col2:
    st.markdown("### 🤖 Saída da IA (JSON)")
    if btn_processar and texto_livre:
        with st.spinner("Ollama está pensando..."):
            try:
                # Chamada para o seu novo endpoint orquestrador
                response = httpx.post(
                    f"{API_URL}/processar-entrada-livre",
                    json={"texto": texto_livre},
                    timeout=260.0,
                )

                if response.status_code == 200:
                    dados = response.json()

                    # Exibe a mensagem do bot (incluindo Sanity Checks)
                    if dados["status"] == "alerta":
                        st.warning(dados["mensagem_bot"])
                    else:
                        st.success(dados["mensagem_bot"])

                    # Mostra o JSON bruto para depuração
                    st.json(dados["dados_processados"])

                    # Converte os itens para uma tabela para facilitar a leitura
                    df_itens = pd.DataFrame(dados["dados_processados"]["itens"])
                    st.markdown("### 📊 Itens Identificados")
                    st.table(df_itens)
                else:
                    st.error(f"Erro no Backend: {response.text}")
            except Exception as e:
                st.error(f"Falha na conexão: {e}")

st.divider()

# Seção para visualizar o Estado Atual do Banco
if st.button("Ver Estoque Atual 📦"):
    res = httpx.get(f"{API_URL}/produtos/alertas")
    if res.status_code == 200:
        estoque = res.json()
        st.write("Produtos em Estoque:")
        st.dataframe(
            pd.DataFrame(estoque["estoque_baixo"] + estoque["vencendo_em_breve"])
        )

st.divider()
st.header("📈 Inteligência de Mercado (Teresina)")

# 1. Seleção do Produto
res_produtos = httpx.get(
    f"{API_URL}/produtos/alertas"
)  # Ou um endpoint de listagem total
if res_produtos.status_code == 200:
    lista_produtos = (
        res_produtos.json()["estoque_baixo"] + res_produtos.json()["vencendo_em_breve"]
    )

    if lista_produtos:
        prod_selecionado = st.selectbox(
            "Selecione um produto para ver a evolução do preço:",
            options=lista_produtos,
            format_func=lambda x: x["nome"],
        )

        # 2. Busca o Histórico
        res_hist = httpx.get(
            f"{API_URL}/relatorios/historico-precos/{prod_selecionado['id']}"
        )

        if res_hist.status_code == 200 and res_hist.json():
            df = pd.DataFrame(res_hist.json())
            df["data"] = pd.to_datetime(df["data"])

            # 3. Criação do Gráfico Interativo com Altair
            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("data:T", title="Data da Compra"),
                    y=alt.Y(
                        "preco:Q",
                        title="Preço Unitário (R$)",
                        scale=alt.Scale(zero=False),
                    ),
                    tooltip=["data", "preco", "local"],
                )
                .properties(
                    width=700,
                    height=400,
                    title=f"Variação de Preço: {prod_selecionado['nome']}",
                )
                .interactive()
            )

            st.altair_chart(chart, use_container_width=True)

            # Tabela comparativa rápida
            st.dataframe(df.sort_values(by="data", ascending=False))
        else:
            st.info("Ainda não há histórico suficiente para este produto.")

st.divider()
st.header("🛒 Simulador de Próxima Compra")

if st.button("Calcular Estimativa de Gastos 💰"):
    res = httpx.get(f"{API_URL}/relatorios/previsao-gastos")

    if res.status_code == 200:
        previsao = res.json()

        # Métrica em destaque
        st.metric(
            label="Estimativa Total para Reposição",
            value=f"R$ {previsao['valor_total_estimado']:.2f}",
            delta="Baseado em preços históricos",
        )

        if previsao["itens"]:
            df_previsao = pd.DataFrame(previsao["itens"])
            st.table(df_previsao)

            # Alerta de Orçamento
            # Supondo que você queira gastar no máximo R$ 500 por ida
            LIMITE_ORCAMENTO = 500.00
            if previsao["valor_total_estimado"] > LIMITE_ORCAMENTO:
                st.error(
                    f"⚠️ Atenção: A estimativa excede o seu limite planejado de R$ {LIMITE_ORCAMENTO}!"
                )
            else:
                st.success("✅ A estimativa está dentro do plano financeiro.")
        else:
            st.info("Nenhum item com estoque baixo para repor.")

st.divider()
st.header("🎯 Metas Financeiras - Abril 2026")

with st.expander("⚙️ Definir Orçamentos por Categoria"):
    # Exemplo de categorias que limpamos no passo anterior
    cats = []
    res = httpx.get(f"{API_URL}/categorias")
    if res.status_code != 200:
        st.error("Não foi possível trazer as categorias.")
    else:
        cats = [cat["nome"] for cat in res.json()]
    # cats = ["Açougue", "Laticínios", "Hortifrúti", "Mercearia", "Limpeza"]
    for cat in cats:
        novo_valor = st.number_input(
            f"Limite para {cat} (R$):", min_value=0.0, step=50.0, key=cat
        )
        if st.button(f"Salvar {cat}"):
            # Envia POST para gravar no banco
            httpx.post(
                f"{API_URL}/budgets/", json={"categoria": cat, "valor": novo_valor}
            )

st.divider()

# Visualização da Performance
st.subheader("📊 Consumo do Orçamento Real-Time")
res = httpx.get(f"{API_URL}/relatorios/performance-budget")
if res.status_code == 200:
    for p in res.json():
        col_cat, col_bar = st.columns([1, 3])
        with col_cat:
            st.write(f"**{p['categoria']}**")
            st.caption(f"R$ {p['real']:.2f} / R$ {p['limite']:.2f}")

        with col_bar:
            cor = "normal"
            if p["porcentagem"] > 90:
                cor = "inverse"  # Vermelho se passar de 90%
            st.progress(min(p["porcentagem"] / 100, 1.0))

# No final do arquivo, adicione a chamada se quiser usar abas
tab1, tab2, tab3 = st.tabs(["Dashboard", "Carga Inicial", "Analytics"])
with tab2:
    interface_carga_manual()
