import streamlit as st
import httpx
import pandas as pd
import json

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
