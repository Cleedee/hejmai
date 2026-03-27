import json

import streamlit as st
import httpx
import pandas as pd
import altair as alt

st.set_page_config(page_title="Hejmai - Lab de Compras", layout="wide")

st.title("🧪 Hejmai NLP Playground")
st.subheader("Teste de Extração com Ollama")

# URL do seu backend FastAPI
API_URL = "http://localhost:8081"

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📥 Entrada de Texto")
    texto_livre = st.text_area(
        "Cole aqui a nota do Keep ou descreva a compra:",
        placeholder="Ex: Comprei 2kg de carne por 80 reais no Carvalho Super...",
        height=300
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
                    timeout=260.0
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
        st.dataframe(pd.DataFrame(estoque['estoque_baixo'] + estoque['vencendo_em_breve']))

st.divider()
st.header("📈 Inteligência de Mercado (Teresina)")

# 1. Seleção do Produto
res_produtos = httpx.get(f"{API_URL}/produtos/alertas") # Ou um endpoint de listagem total
if res_produtos.status_code == 200:
    lista_produtos = res_produtos.json()['estoque_baixo'] + res_produtos.json()['vencendo_em_breve']
    
    if lista_produtos:
        prod_selecionado = st.selectbox(
            "Selecione um produto para ver a evolução do preço:",
            options=lista_produtos,
            format_func=lambda x: x['nome']
        )

        # 2. Busca o Histórico
        res_hist = httpx.get(f"{API_URL}/relatorios/historico-precos/{prod_selecionado['id']}")
        
        if res_hist.status_code == 200 and res_hist.json():
            df = pd.DataFrame(res_hist.json())
            df['data'] = pd.to_datetime(df['data'])

            # 3. Criação do Gráfico Interativo com Altair
            chart = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X('data:T', title='Data da Compra'),
                y=alt.Y('preco:Q', title='Preço Unitário (R$)', scale=alt.Scale(zero=False)),
                tooltip=['data', 'preco', 'local']
            ).properties(
                width=700,
                height=400,
                title=f"Variação de Preço: {prod_selecionado['nome']}"
            ).interactive()

            st.altair_chart(chart, use_container_width=True)
            
            # Tabela comparativa rápida
            st.dataframe(df.sort_values(by='data', ascending=False))
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
            delta="Baseado em preços históricos"
        )

        if previsao['itens']:
            df_previsao = pd.DataFrame(previsao['itens'])
            st.table(df_previsao)
            
            # Alerta de Orçamento
            # Supondo que você queira gastar no máximo R$ 500 por ida
            LIMITE_ORCAMENTO = 500.00
            if previsao['valor_total_estimado'] > LIMITE_ORCAMENTO:
                st.error(f"⚠️ Atenção: A estimativa excede o seu limite planejado de R$ {LIMITE_ORCAMENTO}!")
            else:
                st.success("✅ A estimativa está dentro do plano financeiro.")
        else:
            st.info("Nenhum item com estoque baixo para repor.")
