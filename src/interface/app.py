"""
Hejmai - Interface Streamlit para Gestão de Estoque e Compras Domésticas.

Esta aplicação fornece:
- Dashboard de alertas de estoque
- Carga manual de produtos
- Processamento NLP de compras via IA
- Histórico de preços com gráficos
- Simulador de gastos para reposição
- Gerenciamento de orçamentos por categoria
"""

import streamlit as st
from datetime import date, timedelta

import pandas as pd

from .config import config
from .api_client import APIClient, ConnectionError, ServerError
from .components import (
    render_nlp_processor,
    render_price_chart,
    render_budget_manager,
)
from .utils import validate_carga_manual


# =============================================================================
# Configuração da Página
# =============================================================================

st.set_page_config(
    page_title="Hejmai - Gestão de Estoque",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# Inicialização de Recursos
# =============================================================================

@st.cache_resource
def get_api_client() -> APIClient:
    """
    Cria e retorna uma instância singleton do APIClient.
    
    Usa @st.cache_resource para garantir que apenas uma instância
    seja criada por sessão, otimizando conexões.
    
    Returns:
        APIClient: Instância do cliente API
    """
    return APIClient(
        base_url=config.API_URL,
        timeout=config.API_TIMEOUT,
    )


api = get_api_client()


# =============================================================================
# Cache para Dados
# =============================================================================

@st.cache_data(ttl=config.CACHE_TTL_SEGUNDOS)
def get_produtos_alertas_cached() -> dict:
    """
    Busca produtos com alertas de estoque (cache por 5 minutos).
    
    Returns:
        Dict com 'estoque_baixo' e 'vencendo_em_breve'
    """
    try:
        return api.get_produtos_alertas()
    except Exception:
        return {"estoque_baixo": [], "vencendo_em_breve": []}


@st.cache_data(ttl=config.CACHE_TTL_SEGUNDOS)
def get_categorias_cached() -> list:
    """
    Busca categorias cadastradas (cache por 5 minutos).
    
    Returns:
        Lista de nomes de categorias
    """
    try:
        return api.get_categorias()
    except Exception:
        return []


# =============================================================================
# Header e Navegação
# =============================================================================

st.title("🛒 Hejmai")
st.subheader("Gestão de Estoque e Compras Domésticas")

# Sidebar com navegação
with st.sidebar:
    st.markdown("### 🧭 Navegação")
    
    page = st.radio(
        "Ir para:",
        ["🏠 Dashboard", "📝 Carga Manual", "🤷 NLP Playground", "📊 Analytics"],
        label_visibility="collapsed",
        index=0,
    )
    
    st.divider()
    
    # Status da API
    try:
        status = api.health_check()
        st.success("✅ API Online")
        st.caption(f"Conectado em: {config.API_URL}")
    except ConnectionError:
        st.error("❌ API Offline")
        st.caption("Verifique se o servidor está rodando")


# =============================================================================
# 🏠 DASHBOARD
# =============================================================================

if page == "🏠 Dashboard":
    st.markdown("## 🏠 Visão Geral")
    
    # Carregar dados de alertas
    alertas = get_produtos_alertas_cached()
    categorias = get_categorias_cached()
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        estoque_baixo = len(alertas.get("estoque_baixo", []))
        st.metric(
            label="📦 Estoque Baixo",
            value=estoque_baixo,
            delta="Precisa repor" if estoque_baixo > 0 else "Tudo OK",
        )
    
    with col2:
        vencendo = len(alertas.get("vencendo_em_breve", []))
        st.metric(
            label="⏰ Vencendo em Breve",
            value=vencendo,
            delta="Atenção necessária" if vencendo > 0 else "Nada vencendo",
        )
    
    with col3:
        st.metric(
            label="🏷️ Categorias",
            value=len(categorias),
            delta=None,
        )
    
    with col4:
        # Total de produtos (estimativa baseada nos alertas)
        total_produtos = estoque_baixo + vencendo
        st.metric(
            label="📦 Total em Alerta",
            value=total_produtos,
            delta="Produtos com atenção",
        )
    
    st.divider()
    
    # Detalhes dos alertas
    col_alertas1, col_alertas2 = st.columns(2)
    
    with col_alertas1:
        st.markdown("### 📦 Produtos com Estoque Baixo")
        
        itens_baixo = alertas.get("estoque_baixo", [])
        if itens_baixo:
            df_baixo = pd.DataFrame(itens_baixo)
            st.dataframe(
                df_baixo[["nome", "categoria", "estoque_atual", "unidade_medida"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("✅ Nenhum produto com estoque baixo!")
    
    with col_alertas2:
        st.markdown("### ⏰ Produtos Vencendo em Breve")
        
        itens_vencendo = alertas.get("vencendo_em_breve", [])
        if itens_vencendo:
            df_vencendo = pd.DataFrame(itens_vencendo)
            st.dataframe(
                df_vencendo[["nome", "categoria", "ultima_validade", "estoque_atual"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("✅ Nenhum produto vencendo em breve!")


# =============================================================================
# 📝 CARGA MANUAL
# =============================================================================

elif page == "📝 Carga Manual":
    st.markdown("## 📝 Carga Manual de Estoque")
    st.markdown("Preencha a tabela abaixo com os itens do seu inventário")
    
    # Inicializar estado da sessão
    if "df_carga" not in st.session_state:
        st.session_state.df_carga = pd.DataFrame([{
            "nome": "",
            "categoria": "Mercearia",
            "quantidade": 1.0,
            "unidade": "un",
            "preco_pago": 0.0,
            "data_validade": date.today() + timedelta(days=90),
        }])
    
    # Buscar categorias
    categorias = get_categorias_cached() or [
        "Mercearia", "Açougue", "Laticínios", "Hortifruti",
        "Higiene", "Limpeza", "Padaria", "Bebidas"
    ]
    
    # Editor de dados
    df_editado = st.data_editor(
        st.session_state.df_carga,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "categoria": st.column_config.SelectboxColumn(
                options=categorias,
                required=True,
            ),
            "data_validade": st.column_config.DateColumn(
                format="DD/MM/YYYY",
            ),
            "preco_pago": st.column_config.NumberColumn(
                format="R$ %.2f",
            ),
            "unidade": st.column_config.SelectboxColumn(
                options=["un", "kg", "l", "g", "ml", "pct", "cx"],
            ),
        },
        key="editor_carga_manual",
    )
    
    # Botões de ação
    col_btn1, col_btn2 = st.columns([1, 4])
    
    with col_btn1:
        if st.button("🗑️ Limpar Tabela"):
            st.session_state.df_carga = pd.DataFrame([{
                "nome": "",
                "categoria": "Mercearia",
                "quantidade": 1.0,
                "unidade": "un",
                "preco_pago": 0.0,
                "data_validade": date.today() + timedelta(days=90),
            }])
            st.rerun()
    
    with col_btn2:
        if st.button("📥 Salvar Carga", type="primary"):
            # Filtrar linhas vazias
            df_final = df_editado[df_editado["nome"].str.strip() != ""].copy()
            
            # Validações
            erros = validate_carga_manual(df_final)
            
            if erros:
                for erro in erros:
                    st.error(erro)
            
            elif df_final.empty:
                st.warning("⚠️ Adicione pelo menos um item à lista.")
            
            else:
                with st.spinner("💾 Salvando no banco de dados..."):
                    try:
                        # Preparar dados para envio
                        df_final["data_validade"] = pd.to_datetime(
                            df_final["data_validade"]
                        ).dt.strftime("%Y-%m-%d")
                        
                        payload = {
                            "local_compra": "Inventário Inicial",
                            "itens": df_final.to_dict("records"),
                        }
                        
                        resultado = api.post_compra_lote(payload)
                        
                        st.success(
                            f"✅ {len(df_final)} itens adicionados ao estoque!"
                        )
                        st.balloons()
                        
                        # Resetar tabela
                        st.session_state.df_carga = pd.DataFrame([{
                            "nome": "",
                            "categoria": "Mercearia",
                            "quantidade": 1.0,
                            "unidade": "un",
                            "preco_pago": 0.0,
                            "data_validade": date.today() + timedelta(days=90),
                        }])
                        st.rerun()
                        
                    except ConnectionError:
                        st.error(
                            "❌ Não foi possível conectar à API. "
                            "Verifique se o servidor está rodando."
                        )
                    
                    except ServerError as e:
                        st.error(f"❌ Erro no servidor: {str(e)}")
                    
                    except Exception as e:
                        st.error(f"❌ Erro inesperado: {type(e).__name__}: {str(e)}")


# =============================================================================
# 🤷 NLP PLAYGROUND
# =============================================================================

elif page == "🤷 NLP Playground":
    render_nlp_processor(api)


# =============================================================================
# 📊 ANALYTICS
# =============================================================================

elif page == "📊 Analytics":
    # Carregar dados de alertas para obter lista de produtos
    alertas = get_produtos_alertas_cached()
    produtos = alertas.get("estoque_baixo", []) + alertas.get("vencendo_em_breve", [])
    
    # Seção 1: Gráfico de Preços
    render_price_chart(api, produtos)
    
    st.divider()
    
    # Seção 2: Simulador de Gastos
    st.markdown("## 🛒 Simulador de Próxima Compra")
    st.markdown("Estime os gastos para repor itens com estoque baixo")
    
    if st.button("💰 Calcular Estimativa de Gastos", type="primary"):
        try:
            previsao = api.get_previsao_gastos()
            
            # Métrica principal
            st.metric(
                label="📊 Estimativa Total para Reposição",
                value=f"R$ {previsao.get('valor_total_estimado', 0):.2f}",
                delta="Baseado em preços históricos",
            )
            
            # Lista de itens
            itens = previsao.get("itens", [])
            
            if itens:
                df_previsao = pd.DataFrame(itens)
                st.dataframe(
                    df_previsao,
                    use_container_width=True,
                    hide_index=True,
                )
                
                # Alerta de orçamento
                if previsao.get("valor_total_estimado", 0) > config.ORCAMENTO_LIMITE_PADRAO:
                    st.error(
                        f"⚠️ **Atenção:** A estimativa excede o limite padrão de "
                        f"R$ {config.ORCAMENTO_LIMITE_PADRAO:.2f}!"
                    )
                else:
                    st.success("✅ Estimativa dentro do orçamento planejado.")
            
            else:
                st.info("ℹ️ Nenhum item precisa de reposição no momento.")
        
        except ConnectionError:
            st.error(
                "❌ Não foi possível conectar à API. "
                "Verifique se o servidor está rodando."
            )
        
        except ServerError as e:
            st.error(f"❌ Erro no servidor: {str(e)}")
        
        except Exception as e:
            st.error(f"❌ Erro inesperado: {type(e).__name__}: {str(e)}")
    
    st.divider()
    
    # Seção 3: Gerenciamento de Orçamentos
    render_budget_manager(api)


# =============================================================================
# Rodapé
# =============================================================================

st.divider()
st.caption(
    f"Hejmai v0.1.0 | API: {config.API_URL} | "
    f"Cache TTL: {config.CACHE_TTL_SEGUNDOS}s"
)
