"""
Componente de visualização de histórico de preços.

Este componente fornece:
- Seletor de produtos
- Gráfico interativo de variação de preços
- Tabela de histórico recente
- Tratamento de erros específico
"""

import streamlit as st
import pandas as pd
import altair as alt

from interface.api_client import APIClient, NotFoundError


def render_price_chart(api: APIClient, produtos: list) -> None:
    """
    Renderiza o componente de gráfico de histórico de preços.
    
    Este componente cria:
    - Seletor de produtos com busca
    - Gráfico Altair interativo de variação de preços
    - Tabela de histórico recente
    
    Args:
        api: Instância do APIClient para comunicação com a API
        produtos: Lista de produtos disponíveis para seleção
    """
    if not produtos:
        st.info("ℹ️ Nenhum produto disponível para análise de preços.")
        return
    
    st.markdown("## 📈 Inteligência de Mercado")
    st.markdown("Acompanhe a variação de preços ao longo do tempo")
    
    # Criar mapping de produtos
    opcoes_produtos = {p["nome"]: p["id"] for p in produtos}
    
    # Seletor de produto com busca
    produto_nome = st.selectbox(
        "Selecione um produto para ver a evolução do preço:",
        options=list(opcoes_produtos.keys()),
        key="seletor_produto_preco",
        placeholder="Digite para buscar...",
    )
    
    if produto_nome:
        produto_id = opcoes_produtos[produto_nome]
        
        try:
            historico = api.get_historico_precos(produto_id)
            
            if not historico:
                st.info(f"Sem histórico de preços para '{produto_nome}'.")
                return
            
            # Processar dados
            df = pd.DataFrame(historico)
            df["data"] = pd.to_datetime(df["data"])
            
            # Criar gráfico Altair
            chart = (
                alt.Chart(df)
                .mark_line(point=True, strokeWidth=2, clip=True)
                .encode(
                    x=alt.X(
                        "data:T",
                        title="Data da Compra",
                        axis=alt.Axis(format="%d/%m/%Y", labelAngle=-45),
                    ),
                    y=alt.Y(
                        "preco:Q",
                        title="Preço Unitário (R$)",
                        scale=alt.Scale(zero=False, padding=10),
                        axis=alt.Axis(format="R$ %.2f"),
                    ),
                    color=alt.Color("local:N", title="Local de Compra"),
                    tooltip=[
                        alt.Tooltip("data:T", title="Data", format="%d/%m/%Y"),
                        alt.Tooltip("preco:Q", title="Preço", format="R$ %.2f"),
                        alt.Tooltip("local:N", title="Local"),
                    ],
                )
                .properties(
                    height=400,
                    title=f"Variação de Preço: {produto_nome}",
                )
                .configure_title(
                    fontSize=16,
                    anchor="start",
                )
                .interactive()
            )
            
            # Exibir gráfico
            st.altair_chart(chart, use_container_width=True)
            
            # Tabela de histórico recente
            st.markdown("### 📋 Histórico Recente")
            
            df_recente = df.sort_values("data", ascending=False).head(10)
            
            st.dataframe(
                df_recente,
                column_config={
                    "data": st.column_config.DateColumn(
                        "Data",
                        format="DD/MM/YYYY",
                    ),
                    "preco": st.column_config.NumberColumn(
                        "Preço Unitário",
                        format="R$ %.2f",
                    ),
                    "local": st.column_config.TextColumn(
                        "Local de Compra",
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )
            
            # Estatísticas resumidas
            st.markdown("### 📊 Estatísticas")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="Menor Preço",
                    value=f"R$ {df['preco'].min():.2f}",
                )
            
            with col2:
                st.metric(
                    label="Maior Preço",
                    value=f"R$ {df['preco'].max():.2f}",
                )
            
            with col3:
                st.metric(
                    label="Preço Médio",
                    value=f"R$ {df['preco'].mean():.2f}",
                )
            
            with col4:
                variacao = ((df['preco'].max() - df['preco'].min()) / df['preco'].min() * 100) if df['preco'].min() > 0 else 0
                st.metric(
                    label="Variação Total",
                    value=f"{variacao:.1f}%",
                )
            
        except NotFoundError:
            st.error(f"❌ Histórico não encontrado para '{produto_nome}'.")
        
        except ConnectionError:
            st.error(
                "❌ Não foi possível conectar à API. "
                "Verifique se o servidor está rodando."
            )
        
        except Exception as e:
            st.error(f"❌ Erro ao carregar histórico: {type(e).__name__}: {str(e)}")
