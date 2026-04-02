"""
Componente de gerenciamento de orçamentos por categoria.

Este componente fornece:
- Definição de limites de orçamento por categoria
- Visualização de performance em tempo real
- Barras de progresso com cores dinâmicas
- Alertas de orçamento estourado
"""

import streamlit as st

from ..api_client import APIClient


def render_budget_manager(api: APIClient) -> None:
    """
    Renderiza o componente de gerenciamento de orçamentos.
    
    Este componente cria:
    - Seção de definição de orçamentos (expander)
    - Visualização de performance com barras de progresso
    - Alertas visuais para orçamentos estourados
    
    Args:
        api: Instância do APIClient para comunicação com a API
    """
    st.markdown("## 🎯 Metas Financeiras")
    st.markdown("Acompanhe seu consumo de orçamento por categoria")
    
    # =========================================================================
    # Seção de Definição de Orçamentos
    # =========================================================================
    with st.expander("⚙️ Definir Orçamentos por Categoria"):
        st.markdown(
            "Defina limites mensais de gastos para cada categoria de produto.\n\n"
            "💡 **Dica:** Estes limites ajudam a controlar seus gastos e evitar compras impulsivas."
        )
        
        try:
            categorias = api.get_categorias()
            
            if not categorias:
                st.warning("⚠️ Nenhuma categoria cadastrada no sistema.")
                st.info(
                    "Cadastre categorias primeiro usando o endpoint `POST /categoria` da API."
                )
                return
            
            st.markdown("### Limites por Categoria")
            
            # Criar colunas para input
            for i, categoria in enumerate(categorias):
                col_input, col_btn = st.columns([4, 1], gap="small")
                
                with col_input:
                    valor = st.number_input(
                        f"Limite para **{categoria}** (R$):",
                        min_value=0.0,
                        max_value=10000.0,
                        step=50.0,
                        key=f"budget_{categoria}",
                        label_visibility="collapsed",
                        placeholder="R$ 0,00",
                    )
                
                with col_btn:
                    if st.button(
                        "💾 Salvar",
                        key=f"btn_{categoria}",
                        use_container_width=True,
                    ):
                        # TODO: Implementar endpoint de budget na API
                        st.toast(
                            f"⚠️ Endpoint de budget para '{categoria}' será implementado em breve.",
                            icon="ℹ️",
                        )
                        # Quando implementado:
                        # try:
                        #     api.post_budget(categoria, valor)
                        #     st.success(f"Limite de R$ {valor:.2f} salvo para {categoria}!")
                        # except Exception as e:
                        #     st.error(f"Erro ao salvar: {e}")
            
        except ConnectionError:
            st.error(
                "❌ Não foi possível conectar à API. "
                "Verifique se o servidor está rodando."
            )
        
        except Exception as e:
            st.error(f"❌ Erro ao carregar categorias: {type(e).__name__}: {str(e)}")
    
    st.divider()
    
    # =========================================================================
    # Visualização da Performance
    # =========================================================================
    st.markdown("### 📊 Consumo do Orçamento - Tempo Real")
    st.markdown("Acompanhe quanto já foi gasto em cada categoria este mês")
    
    try:
        performance = api.get_performance_budget()
        
        if not performance:
            st.info(
                "ℹ️ Nenhum orçamento definido para este mês.\n\n"
                "Use o expander acima para definir limites de orçamento."
            )
            return
        
        # Exibir performance por categoria
        for p in performance:
            categoria = p.get("categoria", "Desconhecida")
            limite = p.get("limite", 0)
            real = p.get("real", 0)
            porcentagem = p.get("porcentagem", 0)
            
            # Criar colunas
            col_cat, col_vals, col_bar, col_status = st.columns([2, 2, 4, 1], gap="small")
            
            with col_cat:
                st.markdown(f"**{categoria}**")
            
            with col_vals:
                st.markdown(f"**R$ {real:.2f}** / R$ {limite:.2f}")
            
            with col_bar:
                # Determinar cor e ícone baseado na porcentagem
                if porcentagem > 100:
                    # Estourado
                    st.progress(1.0)
                    excesso = porcentagem - 100
                    st.caption(f"❌ Estourou em {excesso:.0f}%")
                
                elif porcentagem > 90:
                    # Quase no limite
                    st.progress(1.0)
                    st.caption(f"⚠️ {porcentagem:.0f}% do limite")
                
                elif porcentagem > 70:
                    # Atenção
                    st.progress(porcentagem / 100)
                    st.caption(f"📈 {porcentagem:.0f}% utilizado")
                
                else:
                    # Dentro do orçamento
                    st.progress(porcentagem / 100)
                    st.caption(f"✅ {porcentagem:.0f}% utilizado")
            
            with col_status:
                # Ícone de status
                if porcentagem > 100:
                    st.markdown("❌")
                elif porcentagem > 90:
                    st.markdown("⚠️")
                elif porcentagem > 70:
                    st.markdown("📈")
                else:
                    st.markdown("✅")
        
        # Resumo geral
        st.divider()
        st.markdown("### 📈 Resumo Geral")
        
        total_limite = sum(p.get("limite", 0) for p in performance)
        total_real = sum(p.get("real", 0) for p in performance)
        porcentagem_geral = (total_real / total_limite * 100) if total_limite > 0 else 0
        
        col_total1, col_total2, col_total3 = st.columns(3)
        
        with col_total1:
            st.metric(
                label="Total Limite",
                value=f"R$ {total_limite:.2f}",
            )
        
        with col_total2:
            st.metric(
                label="Total Gasto",
                value=f"R$ {total_real:.2f}",
                delta=f"{porcentagem_geral:.0f}% do limite",
            )
        
        with col_total3:
            restante = total_limite - total_real
            if restante >= 0:
                st.metric(
                    label="Restante",
                    value=f"R$ {restante:.2f}",
                )
            else:
                st.metric(
                    label="Estouro Total",
                    value=f"R$ {abs(restante):.2f}",
                    delta="⚠️ Acima do limite",
                )
        
    except ConnectionError:
        st.error(
            "❌ Não foi possível conectar à API. "
            "Verifique se o servidor está rodando."
        )
    
    except Exception as e:
        st.error(f"❌ Erro ao carregar performance: {type(e).__name__}: {str(e)}")
