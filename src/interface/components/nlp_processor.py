"""
Componente de processamento NLP para entrada de texto livre.

Este componente fornece uma interface para:
- Entrada de texto descritivo de compras
- Processamento via Ollama (IA)
- Visualização dos itens extraídos
- Feedback visual com status e tratamento de erros
"""

import streamlit as st
import pandas as pd

from ..api_client import APIClient, ConnectionError, ServerError
from ..config import config


def render_nlp_processor(api: APIClient) -> None:
    """
    Renderiza o componente de processamento NLP.
    
    Este componente cria:
    - Uma área de texto para entrada
    - Botão de processamento
    - Visualização do resultado com status
    - Tabela de itens extraídos
    
    Args:
        api: Instância do APIClient para comunicação com a API
    """
    st.markdown("## 🤷 NLP Playground")
    st.markdown("Processamento de texto livre com IA")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📥 Entrada de Texto")
        
        texto_livre = st.text_area(
            "Cole aqui a nota do Keep ou descreva a compra:",
            placeholder="Ex: Comprei 2kg de carne por 80 reais no Carvalho Super...",
            height=300,
            key="texto_nlp",
            help="Descreva sua compra em linguagem natural. A IA irá extrair os itens automaticamente.",
        )
        
        btn_processar = st.button(
            "Processar com Ollama 🚀",
            type="primary",
            disabled=not texto_livre.strip(),
        )
    
    with col2:
        st.markdown("### 🤖 Resultado do Processamento")
        
        if btn_processar and texto_livre:
            with st.status("Processando com Ollama...", expanded=True) as status:
                st.write("📝 Extraindo itens do texto...")
                
                try:
                    dados = api.post_processar_entrada_livre(texto_livre)
                    
                    # Verifica status do processamento
                    if dados.get("status") == "alerta":
                        status.update(label="⚠️ Processado com alertas", state="warning")
                        st.warning(dados.get("mensagem_bot", ""))
                    else:
                        status.update(label="✅ Processado com sucesso!", state="complete")
                        st.success(dados.get("mensagem_bot", ""))
                    
                    # Mostra JSON para debug
                    dados_processados = dados.get("dados_processados", {})
                    if dados_processados:
                        with st.expander("📋 Dados brutos (JSON)"):
                            st.json(dados_processados)
                    
                    # Mostra tabela de itens
                    itens = dados_processados.get("itens", [])
                    if itens:
                        df_itens = pd.DataFrame(itens)
                        st.markdown("### 📊 Itens Identificados")
                        st.dataframe(
                            df_itens,
                            use_container_width=True,
                            hide_index=True,
                        )
                    
                except ConnectionError as e:
                    status.update(label="❌ Erro de conexão", state="error")
                    st.error(
                        f"Não foi possível conectar à API. Verifique se o servidor está rodando.\n\n"
                        f"Detalhes: {str(e)}"
                    )
                
                except ServerError as e:
                    status.update(label="❌ Erro no servidor", state="error")
                    st.error(f"Erro no processamento: {str(e)}")
                
                except Exception as e:
                    status.update(label="❌ Erro inesperado", state="error")
                    st.error(f"Erro inesperado: {type(e).__name__}: {str(e)}")
        
        elif btn_processar:
            st.info("👆 Digite algum texto para processar.")
        
        else:
            st.info(
                "💡 **Dica:** Descreva sua compra de forma natural.\n\n"
                "Exemplo: *'Comprei 3kg de arroz por R$ 15 e 2 litros de leite por R$ 8 no Mercado Extra'*"
            )
