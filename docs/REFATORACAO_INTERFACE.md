# 📋 Especificação Técnica: Refatoração da Interface Streamlit

## Visão Geral

**Objetivo:** Transformar a interface Streamlit de um "playground" para uma aplicação **production-ready** com tratamento de erros robusto, configuração externalizada e melhor UX.

**Escopo:** Refatorar o arquivo `src/interface/app.py` e adicionar arquivos de configuração.

**Tempo Estimado:** 8-12 horas

---

## 🎯 Objetivos da Refatoração

| Objetivo | Descrição | Critério de Sucesso |
|----------|-----------|---------------------|
| **Configuração Externalizada** | Remover todos os valores hardcoded | Variáveis via `.env` ou `secrets.toml` |
| **Tratamento de Erros** | Cobrir 100% das chamadas de API | Nenhum erro silencioso |
| **UX Melhorada** | Feedback claro em todas as ações | Mensagens específicas por tipo de erro |
| **Performance** | Reduzir chamadas redundantes | Cache implementado com TTL |
| **Manutenibilidade** | Código limpo e testável | Funções isoladas, sem código morto |

---

## 📁 Estrutura de Arquivos Proposta

```
hejmai/
├── src/
│   └── interface/
│       ├── app.py                 # Aplicação principal (refatorada)
│       ├── config.py              # NOVO: Configurações e constantes
│       ├── api_client.py          # NOVO: Cliente HTTP com retry e erro
│       ├── components/            # NOVO: Componentes reutilizáveis
│       │   ├── __init__.py
│       │   ├── budget.py          # Componente de orçamento
│       │   ├── nlp_processor.py   # Componente de processamento NLP
│       │   └── product_charts.py  # Componente de gráficos
│       └── utils/                 # NOVO: Utilitários
│           ├── __init__.py
│           └── validators.py      # Validações de dados
├── .streamlit/
│   └── secrets.toml.example       # NOVO: Template de secrets
└── .env.example                   # Atualizado: Variáveis da interface
```

---

## 🔧 Tarefas de Refatoração

### **Fase 1: Fundação (Prioridade Alta)**

#### Tarefa 1.1: Criar Sistema de Configuração
- **Arquivo:** `src/interface/config.py`
- **Descrição:** Centralizar todas as configurações e constantes
- **Critérios de Aceitação:**
  - [ ] URL da API via `os.getenv("API_URL")`
  - [ ] Timeouts configuráveis via env
  - [ ] Constantes magic numbers em variáveis nomeadas
  - [ ] Valores padrão sensatos para desenvolvimento

```python
# config.py
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    API_URL: str = os.getenv("API_URL", "http://localhost:8081")
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "30"))
    NLP_TIMEOUT: int = int(os.getenv("NLP_TIMEOUT", "60"))
    ORCAMENTO_LIMITE_PADRAO: float = float(os.getenv("ORCAMENTO_LIMITE", "500.00"))
    CACHE_TTL_SEGUNDOS: int = int(os.getenv("CACHE_TTL", "300"))
    MAX_RETRY_TENTATIVAS: int = int(os.getenv("MAX_RETRY", "3"))

config = Config()
```

---

#### Tarefa 1.2: Criar Cliente HTTP com Tratamento de Erros
- **Arquivo:** `src/interface/api_client.py`
- **Descrição:** Encapsular chamadas HTTP com retry e tratamento de erros
- **Critérios de Aceitação:**
  - [ ] Funções para cada endpoint da API
  - [ ] Retry exponencial para falhas temporárias
  - [ ] Exceções específicas por tipo de erro
  - [ ] Logs de erro para debugging

```python
# api_client.py
import httpx
import time
from typing import Optional, List, Dict, Any
from .config import config

class APIError(Exception):
    """Erro base da API"""
    pass

class ConnectionError(APIError):
    """Erro de conexão com a API"""
    pass

class NotFoundError(APIError):
    """Recurso não encontrado (404)"""
    pass

class ServerError(APIError):
    """Erro interno do servidor (5xx)"""
    pass

class APIClient:
    def __init__(self, base_url: str = config.API_URL, timeout: int = config.API_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
    
    def _request_with_retry(self, method: str, endpoint: str, **kwargs):
        """Faz requisição com retry exponencial."""
        last_error = None
        
        for tentativa in range(config.MAX_RETRY_TENTATIVAS):
            try:
                response = httpx.request(
                    method=method,
                    url=f"{self.base_url}{endpoint}",
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code < 500:  # Não retry para erro do cliente
                    return response
                    
            except httpx.ConnectError as e:
                last_error = e
                if tentativa < config.MAX_RETRY_TENTATIVAS - 1:
                    wait_time = (tentativa + 1) * 2  # 2s, 4s, 6s...
                    time.sleep(wait_time)
                    
        raise ConnectionError(f"Falha ao conectar após {config.MAX_RETRY_TENTATIVAS} tentativas") from last_error
    
    def get_categorias(self) -> List[str]:
        """Lista categorias disponíveis."""
        try:
            response = self._request_with_retry("GET", "/categorias")
            response.raise_for_status()
            return [cat["nome"] for cat in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise ServerError(f"Erro ao buscar categorias: {e.response.status_code}")
    
    def get_produtos_alertas(self) -> Dict[str, Any]:
        """Busca produtos com alertas de estoque."""
        response = self._request_with_retry("GET", "/produtos/alertas")
        response.raise_for_status()
        return response.json()
    
    def post_compra_lote(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """Registra compra em lote."""
        response = self._request_with_retry(
            "POST", 
            "/compras/registrar-lote",
            json=dados,
            timeout=config.NLP_TIMEOUT * 2  # Compra em lote pode demorar
        )
        response.raise_for_status()
        return response.json()
    
    def post_processar_entrada_livre(self, texto: str) -> Dict[str, Any]:
        """Processa texto livre com NLP."""
        response = self._request_with_retry(
            "POST",
            "/processar-entrada-livre",
            json={"texto": texto},
            timeout=config.NLP_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    
    def get_historico_precos(self, produto_id: int) -> List[Dict[str, Any]]:
        """Busca histórico de preços de um produto."""
        response = self._request_with_retry("GET", f"/relatorios/historico-precos/{produto_id}")
        response.raise_for_status()
        return response.json()
    
    def get_previsao_gastos(self) -> Dict[str, Any]:
        """Busca previsão de gastos para reposição."""
        response = self._request_with_retry("GET", "/relatorios/previsao-gastos")
        response.raise_for_status()
        return response.json()
    
    def get_performance_budget(self) -> List[Dict[str, Any]]:
        """Busca performance de orçamento por categoria."""
        response = self._request_with_retry("GET", "/relatorios/performance-budget")
        response.raise_for_status()
        return response.json()
    
    def delete_compra(self, compra_id: int) -> Dict[str, Any]:
        """Exclui compra (logicamente)."""
        response = self._request_with_retry("DELETE", f"/compras/{compra_id}")
        response.raise_for_status()
        return response.json()
    
    def patch_compra_restaurar(self, compra_id: int) -> Dict[str, Any]:
        """Restaura compra excluída."""
        response = self._request_with_retry("PATCH", f"/compras/{compra_id}/restaurar")
        response.raise_for_status()
        return response.json()
```

---

#### Tarefa 1.3: Atualizar `.env.example` e `secrets.toml.example`
- **Arquivos:** `.env.example`, `.streamlit/secrets.toml.example`
- **Descrição:** Documentar variáveis de ambiente necessárias

```bash
# .env.example
# ===========================================
# Hejmai Interface - Variáveis de Ambiente
# ===========================================

# URL da API FastAPI
API_URL=http://localhost:8081

# Timeouts (em segundos)
API_TIMEOUT=30
NLP_TIMEOUT=60
CACHE_TTL=300

# Retry
MAX_RETRY=3

# Orçamento padrão (R$)
ORCAMENTO_LIMITE=500.00
```

```toml
# .streamlit/secrets.toml.example
# ===========================================
# Hejmai Interface - Secrets (copie para secrets.toml)
# ===========================================

# Chaves de API externas (se necessário)
# TELEGRAM_BOT_TOKEN = "seu_token_aqui"

# Configurações sensíveis
# ORCAMENTO_LIMITE = 500.00
```

---

### **Fase 2: Componentes Reutilizáveis (Prioridade Média)**

#### Tarefa 2.1: Criar Componente de Processamento NLP
- **Arquivo:** `src/interface/components/nlp_processor.py`
- **Descrição:** Componente isolado para entrada de texto e processamento NLP
- **Critérios de Aceitação:**
  - [ ] Função única que retorna o resultado processado
  - [ ] Status visual com `st.status()`
  - [ ] Tratamento de erro com mensagens específicas
  - [ ] Exibição de itens em tabela formatada

```python
# components/nlp_processor.py
import streamlit as st
import pandas as pd
from ..api_client import APIClient, ConnectionError, ServerError
from ..config import config

def render_nlp_processor(api: APIClient):
    """Renderiza componente de processamento NLP."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📥 Entrada de Texto")
        texto_livre = st.text_area(
            "Cole aqui a nota do Keep ou descreva a compra:",
            placeholder="Ex: Comprei 2kg de carne por 80 reais no Carvalho Super...",
            height=300,
            key="texto_nlp",
        )
        
        btn_processar = st.button("Processar com Ollama 🚀", type="primary")
    
    with col2:
        st.markdown("### 🤖 Resultado do Processamento")
        
        if btn_processar and texto_livre:
            with st.status("Processando com Ollama...", expanded=True) as status:
                st.write("📝 Extraindo itens do texto...")
                
                try:
                    dados = api.post_processar_entrada_livre(texto_livre)
                    
                    if dados.get("status") == "alerta":
                        status.update(label="⚠️ Processado com alertas", state="warning")
                        st.warning(dados.get("mensagem_bot", ""))
                    else:
                        status.update(label="✅ Processado com sucesso!", state="complete")
                        st.success(dados.get("mensagem_bot", ""))
                    
                    # Mostrar JSON para debug
                    with st.expander("📋 Dados brutos (JSON)"):
                        st.json(dados.get("dados_processados", {}))
                    
                    # Mostrar tabela de itens
                    itens = dados.get("dados_processados", {}).get("itens", [])
                    if itens:
                        df_itens = pd.DataFrame(itens)
                        st.markdown("### 📊 Itens Identificados")
                        st.dataframe(df_itens, use_container_width=True)
                        
                except ConnectionError as e:
                    status.update(label="❌ Erro de conexão", state="error")
                    st.error(f"Não foi possível conectar à API: {str(e)}")
                except ServerError as e:
                    status.update(label="❌ Erro no servidor", state="error")
                    st.error(f"Erro no processamento: {str(e)}")
                except Exception as e:
                    status.update(label="❌ Erro inesperado", state="error")
                    st.error(f"Erro inesperado: {str(e)}")
```

---

#### Tarefa 2.2: Criar Componente de Gráficos de Preços
- **Arquivo:** `src/interface/components/product_charts.py`
- **Descrição:** Componente para visualização de histórico de preços

```python
# components/product_charts.py
import streamlit as st
import pandas as pd
import altair as alt
from ..api_client import APIClient, NotFoundError

def render_price_chart(api: APIClient, produtos: list):
    """Renderiza gráfico de histórico de preços."""
    if not produtos:
        st.info("Nenhum produto disponível para análise.")
        return
    
    st.markdown("### 📈 Inteligência de Mercado")
    
    # Seleção de produto com busca
    opcoes_produtos = {p["nome"]: p["id"] for p in produtos}
    produto_nome = st.selectbox(
        "Selecione um produto para ver a evolução do preço:",
        options=list(opcoes_produtos.keys()),
        key="seletor_produto_preco",
    )
    
    if produto_nome:
        produto_id = opcoes_produtos[produto_nome]
        
        try:
            historico = api.get_historico_precos(produto_id)
            
            if not historico:
                st.info(f"Sem histórico de preços para '{produto_nome}'.")
                return
            
            df = pd.DataFrame(historico)
            df["data"] = pd.to_datetime(df["data"])
            
            # Gráfico Altair
            chart = (
                alt.Chart(df)
                .mark_line(point=True, strokeWidth=2)
                .encode(
                    x=alt.X("data:T", title="Data da Compra"),
                    y=alt.Y(
                        "preco:Q",
                        title="Preço Unitário (R$)",
                        scale=alt.Scale(zero=False, padding=10),
                    ),
                    color=alt.Color("local:N", title="Local de Compra"),
                    tooltip=[
                        alt.Tooltip("data:T", format="%d/%m/%Y"),
                        alt.Tooltip("preco:Q", format="R$ %.2f"),
                        "local",
                    ],
                )
                .properties(
                    height=400,
                    title=f"Variação de Preço: {produto_nome}",
                )
                .interactive()
            )
            
            st.altair_chart(chart, use_container_width=True)
            
            # Tabela resumo
            st.markdown("### 📋 Histórico Recente")
            st.dataframe(
                df.sort_values("data", ascending=False).head(10),
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                },
                use_container_width=True,
            )
            
        except NotFoundError:
            st.error(f"Histórico não encontrado para '{produto_nome}'.")
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {str(e)}")
```

---

#### Tarefa 2.3: Criar Componente de Orçamento
- **Arquivo:** `src/interface/components/budget.py`
- **Descrição:** Componente para definição e visualização de orçamentos

```python
# components/budget.py
import streamlit as st
import pandas as pd
from ..api_client import APIClient

def render_budget_manager(api: APIClient):
    """Renderiza gerenciador de orçamentos por categoria."""
    st.header("🎯 Metas Financeiras")
    
    # Seção de definição de orçamentos
    with st.expander("⚙️ Definir Orçamentos por Categoria"):
        try:
            categorias = api.get_categorias()
            
            if not categorias:
                st.warning("Nenhuma categoria cadastrada.")
                return
            
            st.markdown("Defina limites mensais para cada categoria:")
            
            for categoria in categorias:
                col_input, col_btn = st.columns([3, 1])
                
                with col_input:
                    valor = st.number_input(
                        f"Limite para **{categoria}** (R$):",
                        min_value=0.0,
                        step=50.0,
                        key=f"budget_{categoria}",
                        label_visibility="collapsed",
                    )
                
                with col_btn:
                    if st.button("💾 Salvar", key=f"btn_{categoria}"):
                        # TODO: Implementar endpoint de budget na API
                        st.info("Endpoint de budget será implementado em breve.")
                        # api.post_budget(categoria, valor)
            
        except Exception as e:
            st.error(f"Erro ao carregar categorias: {str(e)}")
    
    st.divider()
    
    # Visualização da performance
    st.subheader("📊 Consumo do Orçamento - Tempo Real")
    
    try:
        performance = api.get_performance_budget()
        
        if not performance:
            st.info("Nenhum orçamento definido para este mês.")
            return
        
        for p in performance:
            col_cat, col_vals, col_bar = st.columns([2, 2, 4])
            
            with col_cat:
                st.markdown(f"**{p['categoria']}**")
            
            with col_vals:
                porcentagem = p.get("porcentagem", 0)
                if porcentagem > 100:
                    st.error(f"❌ Estourou em {porcentagem - 100:.0f}%")
                elif porcentagem > 90:
                    st.warning(f"⚠️ {porcentagem:.0f}%")
                else:
                    st.success(f"✅ {porcentagem:.0f}%")
            
            with col_bar:
                # Barra de progresso com cor dinâmica
                progress_value = min(p.get("porcentagem", 0) / 100, 1.0)
                
                if porcentagem > 100:
                    st.progress(progress_value)
                elif porcentagem > 90:
                    st.progress(progress_value)
                else:
                    st.progress(progress_value)
                
                st.caption(f"R$ {p.get('real', 0):.2f} / R$ {p.get('limite', 0):.2f}")
        
    except Exception as e:
        st.error(f"Erro ao carregar performance: {str(e)}")
```

---

### **Fase 3: Refatoração do App Principal (Prioridade Média)**

#### Tarefa 3.1: Refatorar `app.py` para Usar Componentes
- **Arquivo:** `src/interface/app.py`
- **Descrição:** Reescrever app principal usando componentes criados
- **Critérios de Aceitação:**
  - [ ] Importar componentes ao invés de código inline
  - [ ] Usar `APIClient` para todas as chamadas
  - [ ] Usar `config` para constantes
  - [ ] Remover código duplicado
  - [ ] Adicionar cache com `@st.cache_data`

```python
# app.py (refatorado)
import streamlit as st
import os
from datetime import date, timedelta

import pandas as pd
import altair as alt

from .config import config
from .api_client import APIClient, ConnectionError, ServerError
from .components.nlp_processor import render_nlp_processor
from .components.product_charts import render_price_chart
from .components.budget import render_budget_manager
from .utils.validators import validate_carga_manual

# Configuração da página
st.set_page_config(
    page_title="Hejmai - Gestão de Estoque",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inicializar cliente API
@st.cache_resource
def get_api_client():
    return APIClient(
        base_url=config.API_URL,
        timeout=config.API_TIMEOUT,
    )

api = get_api_client()

# Título e descrição
st.title("🛒 Hejmai")
st.subheader("Gestão de Estoque e Compras Domésticas")

# Sidebar com navegação
with st.sidebar:
    st.markdown("### Navegação")
    page = st.radio(
        "Ir para:",
        ["🏠 Dashboard", "📝 Carga Manual", "🤷 NLP Playground", "📊 Analytics"],
        label_visibility="collapsed",
    )

# Cache para dados que mudam pouco
@st.cache_data(ttl=config.CACHE_TTL_SEGUNDOS)
def get_produtos_alertas():
    """Busca produtos com alertas (cache por 5 minutos)."""
    try:
        return api.get_produtos_alertas()
    except Exception:
        return {"estoque_baixo": [], "vencendo_em_breve": []}

# ==================== DASHBOARD ====================
st.markdown("## 🏠 Dashboard")

# Resumo de alertas
alertas = get_produtos_alertas()
col1, col2, col3 = st.columns(3)

with col1:
    estoque_baixo = len(alertas.get("estoque_baixo", []))
    st.metric(
        label="📦 Produtos com Estoque Baixo",
        value=estoque_baixo,
        delta=None,
    )

with col2:
    vencendo = len(alertas.get("vencendo_em_breve", []))
    st.metric(
        label="⏰ Produtos Vencendo em Breve",
        value=vencendo,
        delta=None,
    )

with col3:
    st.metric(
        label="🏷️ Total de Categorias",
        value=len(api.get_categorias()),
        delta=None,
    )

st.divider()

# ==================== CARGA MANUAL ====================
st.markdown("## 📝 Carga Manual de Estoque")

if 'df_carga' not in st.session_state:
    st.session_state.df_carga = pd.DataFrame([{
        "nome": "",
        "categoria": "Mercearia",
        "quantidade": 1.0,
        "unidade": "un",
        "preco_pago": 0.0,
        "data_validade": date.today() + timedelta(days=90),
    }])

categorias = api.get_categorias() or ["Mercearia", "Açougue", "Laticínios", "Hortifruti"]

df_editado = st.data_editor(
    st.session_state.df_carga,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "categoria": st.column_config.SelectboxColumn(options=categorias),
        "data_validade": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "preco_pago": st.column_config.NumberColumn(format="R$ %.2f"),
    },
    key="editor_carga_manual",
)

col_btn1, col_btn2 = st.columns([1, 4])

with col_btn1:
    if st.button("🗑️ Limpar"):
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
        df_final = df_editado[df_editado["nome"] != ""].copy()
        
        # Validações
        erros = validate_carga_manual(df_final)
        if erros:
            for erro in erros:
                st.error(erro)
        elif df_final.empty:
            st.warning("Adicione pelo menos um item.")
        else:
            with st.spinner("Salvando..."):
                try:
                    df_final["data_validade"] = pd.to_datetime(
                        df_final["data_validade"]
                    ).dt.strftime("%Y-%m-%d")
                    
                    resultado = api.post_compra_lote({
                        "local_compra": "Inventário Inicial",
                        "itens": df_final.to_dict("records"),
                    })
                    
                    st.success(f"✅ {len(df_final)} itens adicionados!")
                    st.balloons()
                    
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
                    st.error("❌ Não foi possível conectar à API.")
                except ServerError as e:
                    st.error(f"Erro no servidor: {str(e)}")

st.divider()

# ==================== NLP PLAYGROUND ====================
render_nlp_processor(api)

st.divider()

# ==================== GRÁFICO DE PREÇOS ====================
render_price_chart(api, alertas.get("estoque_baixo", []) + alertas.get("vencendo_em_breve", []))

st.divider()

# ==================== SIMULADOR DE GASTOS ====================
st.markdown("## 🛒 Simulador de Próxima Compra")

if st.button("💰 Calcular Estimativa", type="primary"):
    try:
        previsao = api.get_previsao_gastos()
        
        st.metric(
            label="Estimativa Total para Reposição",
            value=f"R$ {previsao.get('valor_total_estimado', 0):.2f}",
            delta="Baseado em preços históricos",
        )
        
        itens = previsao.get("itens", [])
        if itens:
            st.dataframe(pd.DataFrame(itens), use_container_width=True)
            
            if previsao.get("valor_total_estimado", 0) > config.ORCAMENTO_LIMITE_PADRAO:
                st.error(
                    f"⚠️ Atenção: Estimativa excede o limite de R$ {config.ORCAMENTO_LIMITE_PADRAO:.2f}!"
                )
            else:
                st.success("✅ Dentro do orçamento planejado.")
        else:
            st.info("Nenhum item precisa de reposição.")
            
    except Exception as e:
        st.error(f"Erro ao calcular estimativa: {str(e)}")

st.divider()

# ==================== ORÇAMENTOS ====================
render_budget_manager(api)
```

---

### **Fase 4: Validações e Utilitários (Prioridade Baixa)**

#### Tarefa 4.1: Criar Módulo de Validações
- **Arquivo:** `src/interface/utils/validators.py`

```python
# utils/validators.py
from typing import List
import pandas as pd

def validate_carga_manual(df: pd.DataFrame) -> List[str]:
    """Valida dados de carga manual de estoque."""
    erros = []
    
    if (df["quantidade"] <= 0).any():
        erros.append("Quantidade deve ser maior que zero.")
    
    if (df["preco_pago"] < 0).any():
        erros.append("Preço não pode ser negativo.")
    
    if df["nome"].isnull().any():
        erros.append("Nome do produto é obrigatório.")
    
    return erros
```

---

### **Fase 5: Testes e Documentação (Prioridade Baixa)**

#### Tarefa 5.1: Adicionar Testes Unitários
- **Arquivo:** `tests/interface/test_components.py`

```python
# tests/interface/test_components.py
import pytest
from src.interface.api_client import APIClient, ConnectionError

def test_api_client_get_categorias():
    """Testa busca de categorias."""
    api = APIClient()
    categorias = api.get_categorias()
    assert isinstance(categorias, list)

def test_api_client_connection_error():
    """Testa erro de conexão."""
    api = APIClient(base_url="http://localhost:9999")  # Porta inexistente
    with pytest.raises(ConnectionError):
        api.get_categorias()
```

---

## 📊 Cronograma Estimado

| Fase | Tarefas | Horas | Dependências |
|------|---------|-------|--------------|
| **Fase 1** | 1.1, 1.2, 1.3 | 3-4h | Nenhuma |
| **Fase 2** | 2.1, 2.2, 2.3 | 3-4h | Fase 1 |
| **Fase 3** | 3.1 | 2-3h | Fase 2 |
| **Fase 4** | 4.1 | 1h | Fase 1 |
| **Fase 5** | 5.1 | 1-2h | Todas |
| **Total** | **8 tarefas** | **10-14h** | |

---

## ✅ Critérios de Aceitação Gerais

1. **Zero erros silenciosos** - Todas as chamadas de API têm tratamento
2. **Zero hardcoded values** - Tudo configurável via env/secrets
3. **Componentização** - Código dividido em módulos reutilizáveis
4. **Cache implementado** - Requisições repetidas usam cache
5. **UX consistente** - Mensagens de erro claras e específicas
6. **Documentação** - `.env.example` e `secrets.toml.example` atualizados

---

## 🔗 Dependências da API

Os seguintes endpoints são necessários na API:

| Endpoint | Status | Notas |
|----------|--------|-------|
| `GET /categorias` | ✅ Existe | Funcional |
| `GET /produtos/alertas` | ✅ Existe | Funcional |
| `POST /compras/registrar-lote` | ✅ Existe | Funcional |
| `POST /processar-entrada-livre` | ✅ Existe | Funcional |
| `GET /relatorios/historico-precos/{id}` | ✅ Existe | Funcional |
| `GET /relatorios/previsao-gastos` | ✅ Existe | Funcional |
| `GET /relatorios/performance-budget` | ✅ Existe | Funcional |
| `DELETE /compras/{id}` | ✅ Existe | Funcional |
| `PATCH /compras/{id}/restaurar` | ✅ Existe | Funcional |
| `POST /budgets/` | ❌ **Não existe** | **Precisa ser implementado** |

---

## 📝 Notas Adicionais

1. **Endpoint de Budget:** A interface atual chama `POST /budgets/` que não existe. Isso precisa ser implementado na API ou removido da interface.

2. **Compatibilidade com Docker:** A configuração via variáveis de ambiente garante que a interface funcione tanto localmente quanto em containers Docker.

3. **Progressive Enhancement:** A refatoração pode ser feita incrementalmente. Cada fase é independente e pode ser testada isoladamente.
