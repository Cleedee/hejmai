# 🤖 Arquitetura de Agentes e Tools - Hejmai AI

> **Framework:** Agno (Agent Framework)
> **Objetivo:** Dividir capacidades do Hejmai em ferramentas especializadas para roteamento inteligente via LLM.

---

## 1. Visão Geral da Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                        COORDINATOR AGENT                      │
│           (Agno Agent - Roteador Principal)                    │
│  "Entenda a intenção do usuário e escolha a melhor ferramenta"  │
└──────────────────┬───────────────────────────────────────────┘
                   │
      ┌────────────┼────────────┬──────────────┬──────────────┐
      │            │            │              │              │
      ▼            ▼            ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│INVENTÁRIO│  │ FINANCEIRO│  │ NUTRIÇÃO │  │  PREVISÃO │  │ AÇÕES    │
│  TOOL    │  │  TOOL    │  │  TOOL    │  │  TOOL     │  │ TOOL     │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

---

## 2. Definição das Tools

### 🔹 `InventoryTool` - Gestão de Estoque
**Função:** Consultar e modificar o inventário atual.

```python
from agno.tools import tool
from hejmai.database import SessionLocal
from hejmai import crud

@tool
def consultar_estoque(produto: str = None) -> str:
    """Consulta o estoque atual. Se produto for informado, busca específico."""
    db = SessionLocal()
    try:
        if produto:
            itens = crud.buscar_produtos_similares(db, produto)
        else:
            itens = crud.get_produtos_com_estoque(db)
        
        if not itens:
            return "Estoque vazio."
        
        return "\n".join([f"{p.nome}: {p.estoque_atual} {p.unidade_medida}" for p in itens[:10]])
    finally:
        db.close()

@tool
def registrar_consumo(produto: str, quantidade: float) -> str:
    """Registra o consumo de um produto no estoque."""
    # Implementação usando crud e models
    pass

@tool
def registrar_compra_texto(descricao: str) -> str:
    """Registra uma compra baseada em descrição de texto livre."""
    # Integração com endpoint /processar-entrada-livre
    pass
```

### 🔹 `FinanceTool` - Finanças e Orçamento
**Função:** Analisar gastos, orçamentos e listas de compras.

```python
@tool
def verificar_gastos(periodo: str = "mes_atual") -> str:
    """Retorna o resumo de gastos do período."""
    pass

@tool
def verificar_orcamento(categoria: str = None) -> str:
    """Verifica o orçamento disponível por categoria."""
    pass

@tool
def gerar_lista_compras() -> str:
    """Gera lista de produtos com estoque baixo e preços estimados."""
    pass
```

### 🔹 `NutritionTool` - Nutrição e Refeições
**Função:** Informações nutricionais e sugestões de refeições.

```python
@tool
def info_nutricional(produto: str) -> str:
    """Retorna calorias e macros de um produto."""
    pass

@tool
def sugerir_receita(itens_disponiveis: list = None) -> str:
    """Sugere receita baseada nos itens disponíveis no estoque."""
    pass
```

### 🔹 `ProjectionTool` - Previsão e Vigia
**Função:** Projeção de gastos e alertas de estoque.

```python
@tool
def previsao_gastos() -> str:
    """Estima custos para reposição de estoque."""
    pass

@tool
def vigia_estoque() -> str:
    """Relatório de produtos acabando ou vencendo."""
    pass

@tool
def burn_rate(produto: str) -> str:
    """Calcula o ritmo de consumo de um produto."""
    pass
```

### 🔹 `ActionTool` - Ações no Bot Telegram
**Função:** Executar ações no ambiente (ex: enviar mensagem).

```python
@tool
def enviar_mensagem_telegram(chat_id: str, texto: str) -> str:
    """Envia uma mensagem para um usuário ou grupo no Telegram."""
    pass
```

---

## 3. Definição dos Agentes

### 🧠 `CoordinatorAgent` (Roteador)

Este é o agente principal que recebe a pergunta em linguagem natural e decide qual tool usar.

```python
from agno.agent import Agent
from agno.models.ollama import Ollama

coordinator = Agent(
    name="Hejmai Coordinator",
    model=Ollama(id="llama3"),
    tools=[
        InventoryTool, 
        FinanceTool, 
        NutritionTool, 
        ProjectionTool
    ],
    instructions=[
        "Você é o assistente de gestão doméstica Hejmai.",
        "Use as ferramentas disponíveis para responder o usuário.",
        "Se a pergunta for sobre estoque, use InventoryTool.",
        "Se for sobre dinheiro/gastos, use FinanceTool.",
        "Se for sobre comida/receitas, use NutritionTool.",
        "Se for sobre alertas/previsões, use ProjectionTool.",
        "Sempre responda em português de forma amigável e concisa."
    ],
    markdown=True,
    show_tool_calls=True
)
```

---

## 4. Integração com API e Bot

### Novo Endpoint `/ia/agente`

Substitui ou complementa o `/ia/perguntar` atual.

```python
@app.post("/ia/agente")
async def agente_hejmai(payload: PerguntaIA):
    resposta = coordinator.run(payload.pergunta)
    return {"resposta": resposta.content}
```

### Handler no Bot Telegram

```python
async def agente_telegram(update, context):
    resposta = coordinator.run(update.message.text)
    await update.message.reply_text(resposta.content)
```

---

## 5. Estrutura de Pastas Proposta

```
src/hejmai/
└── agents/
    ├── __init__.py
    ├── coordinator.py       # Definição do Agente Principal
    ├── tools/
    │   ├── __init__.py
    │   ├── inventory.py     # Tools de Estoque
    │   ├── finance.py       # Tools Financeiras
    │   ├── nutrition.py     # Tools Nutricionais
    │   └── projection.py    # Tools de Previsão
    └── actions/
        └── telegram.py      # Actions de Envio
```

---

## 6. Fluxo de Execução Exemplo

**Usuário:** *"Quanto eu gastei com carne esse mês e o que eu preciso comprar?"*

1. **Coordinator:** Entende que é uma pergunta financeira + inventário.
2. **Step 1:** Chama `FinanceTool.verificar_gastos(categoria="Açougue")`.
3. **Step 2:** Chama `FinanceTool.gerar_lista_compras()`.
4. **Resposta Final:** "Você gastou R$ 150,00 com carne. Você precisa comprar: Picanha, Frango..."

---

## 7. Dependências Necessárias

Adicionar ao `pyproject.toml`:

```toml
dependencies = [
    # ... existentes
    "agno",
    "fastapi",
    # ...
]
```
