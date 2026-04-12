# Guia de Uso do Agente Hejmai

Este documento descreve as ferramentas disponíveis no Agente Hejmai e as melhores práticas para solicitar cada uma delas.

---

## Inventário (Inventory Tools)

### 1. `consultar_estoque`

**Propósito:** Consulta o estoque atual de produtos.

**Parâmetros:**
- `termo_busca` (opcional): Nome ou parte do nome do produto para filtrar.

**Melhores formas de solicitar:**

| Intenção | Exemplos de Pedido |
|----------|-------------------|
| Ver estoque geral | "mostre meu estoque", "o que tenho em casa?" |
| Buscar produto específico | "tenho arroz?", "quanto iogurte tenho?" |
| Listar categoria | "meus laticínios", "o que tenho de limpeza" |

**Exemplos de prompts:**
- "Quanto arroz temos?"
- "Mostre meu estoque de laticínios"
- "O que está acabando em casa?"
- "Tenho feijão no estoque?"

---

### 2. `verificar_alertas_estoque`

**Propósito:** Verifica produtos acabando (estoque < 1) ou vencendo em breve.

**Parâmetros:** Nenhum.

**Melhores formas de solicitar:**

| Intenção | Exemplos de Pedido |
|----------|-------------------|
| Verificar alertas | "quais produtos estão acabando?", "o que preciso comprar?" |
| Produtos vencendo | "algum produto está vencendo?", "o que vai vencer?" |
| Alerta geral | "me avise sobre o estoque", "quais itens precisam de reposição?" |

**Exemplos de prompts:**
- "Quais produtos estão acabando?"
- "Me avise sobre itens vencendo"
- "O que preciso comprar com urgência?"
- "Tem algo que vai vencer essa semana?"

---

### 3. `analisar_frequencia_consumo`

**Propósito:** Analisa o histórico de consumo de um produto específico.

**Parâmetros:**
- `produto_nome`: Nome do produto a ser analisado.

**Melhores formas de solicitar:**

| Intenção | Exemplos de Pedido |
|----------|-------------------|
| Frequência | "com que frequência como iogurte?", "quanto tempo leva para acabar o arroz?" |
| Histórico | "quando foi o último consumo de leite?", "histórico de consumo de frango" |
| Padrão | "como é meu consumo de pães?", "qual a frequência de compra de café?" |

**Exemplos de prompts:**
- "Com que frequência consumo iogurte?"
- "Quando foi a última vez que usei farinha?"
- "Me conte sobre meu histórico de consumo de arroz"
- "Como é meu padrão de consumo de laticínios?"
- "Há quanto tempo não consumo refrigerante?"

**Importante:** Para melhor resultado, use o nome completo ou parcial do produto que existe no seu estoque.

---

### 4. `registrar_consumo`

**Propósito:** Registra a baixa/consumo de um produto no estoque.

**Parâmetros:**
- `produto_nome`: Nome do produto consumido.
- `quantidade`: Quantidade consumida.

**ATENÇÃO:** Esta ferramenta **só deve ser chamada** quando você **explicitamente** pedir para registrar/dar baixa.

**Melhores formas de solicitar:**

| Intenção | Exemplos de Pedido |
|----------|-------------------|
| Registrar consumo | "registre que consumi 2 pães", "dei baixa em 500g de arroz" |
| Atualizar estoque | "atualize o estoque, usei 1kg de carne", "baixa de 1 unidade de iogurte" |
| Descontar | "desconte do estoque 3 ovos", "remova 1L de leite" |

**Exemplos de prompts:**
- "Registre que consumi 2 pães"
- "Dei baixa em 500g de arroz do estoque"
- "Atualize: usei 1kg de frango"
- "Remova 1 unidade de iogurte do estoque"

**⚠️ CUIDADO:** Sempre especifique a quantidade para evitar erros.

---

## Finanças (Finance Tools)

### 5. `resumo_financeiro`

**Propósito:** Retorna um resumo geral das finanças e orçamentos.

**Parâmetros:** Nenhum.

**Melhores formas de solicitar:**

| Intenção | Exemplos de Pedido |
|----------|-------------------|
| Resumo geral | "resumo financeiro", "como estão minhas finanças?" |
| Orçamento | "mostre meu orçamento", "tenho orçamento definido?" |
| Visão geral | "panorama financeiro", "visão geral das contas" |

**Exemplos de prompts:**
- "Me dê um resumo financeiro"
- "Como estão minhas finanças?"
- "Qual meu orçamento mensal?"

---

### 6. `verificar_gastos`

**Propósito:** Verifica os gastos recentes com compras.

**Parâmetros:**
- `categoria` (opcional): Filtrar por categoria (Açougue, Laticínios, Hortifruti, etc.)

**Melhores formas de solicitar:**

| Intenção | Exemplos de Pedido |
|----------|-------------------|
| Gastos gerais | "quais foram meus últimos gastos?", "gastos recentes" |
| Por categoria | "gastos com açougue", "quanto gastei em laticínios?" |
| Total | "total gasto recentemente", "quanto gastei essa semana?" |
| Estabelecimento | "gastos no mercado extra", "compras no atacadão" |

**Exemplos de prompts:**
- "Quais foram minhas últimas compras?"
- "Quanto gastei com laticínios?"
- "Meus gastos recentes no supermercado"
- "Total gasto essa semana"

---

## Projeção (Projection Tools)

### 7. `previsao_reposicao`

**Propósito:** Estima quais itens precisam de reposição com base no estoque baixo.

**Parâmetros:** Nenhum.

**Melhores formas de solicitar:**

| Intenção | Exemplos de Pedido |
|----------|-------------------|
| Previsão | "previsão de reposição", "o que preciso comprar?" |
| Itens acabando | "quais itens vão acabar?", "lista de compras sugerida" |
| Reposição | "o que está acabando?", "preciso repor algum item?" |

**Exemplos de prompts:**
- "O que preciso repor no estoque?"
- "Liste itens que vão acabar"
- "Me dê uma previsão de compras"
- "Quais produtos estão com estoque baixo?"

---

## Dicas Gerais

### Como o Agente Escolhe a Ferramenta

O agente usa o modelo LLM para interpretar sua pergunta e escolher a ferramenta mais adequada. Para melhores resultados:

1. **Seja específico:** "quanto arroz tenho?" é melhor que "arroz"
2. **Use português claro:** O modelo entende perguntas naturais
3. **Mencione a intenção:** "registre", "consulte", "analise", "verifique"
4. **Para histórico:** Use palavras como "frequência", "histórico", "quando", "último"
5. **Para gastos:** Mencione categoria ou período se relevante

### Combinação de Ferramentas

O agente pode usar múltiplas ferramentas em sequência. Exemplos:

- "Quanto gastei em laticínios e quais estão acabando?"
- "Me mostre o estoque de arroz e quando foi o último consumo"
- "Liste compras recentes e produtos que vão vencer"

### Quando NÃO usar o Agente

Para ações diretas e simples, considere usar os endpoints da API diretamente:
- Cadastrar compra: `POST /compras/registrar-lote`
- Registrar consumo: `PATCH /produtos/consumir/{id}`
- Cadastrar produto: `POST /produtos`

O agente é melhor para:
- Perguntas em linguagem natural
- Análises que exigem interpretação
- Combinação de múltiplas fontes de dados

---

## Tabela Resumo

| Ferramenta | Uso Principal | Chave para Solicitar |
|------------|---------------|---------------------|
| `consultar_estoque` | Quantidade de produtos | "quanto", "tenho", "mostre" |
| `verificar_alertas_estoque` | Produtos acabando/vencendo | "acabando", "vencendo", "preciso comprar" |
| `analisar_frequencia_consumo` | Histórico de consumo | "frequência", "histórico", "quando" |
| `registrar_consumo` | Dar baixa no estoque | "registre", "baixa", "consumi" |
| `resumo_financeiro` | Visão geral finanças | "resumo", "orçamento", "finanças" |
| `verificar_gastos` | Gastos recentes | "gastei", "compras", "despesas" |
| `previsao_reposicao` | Itens para repor | "repor", "acabar", "previsão" |
