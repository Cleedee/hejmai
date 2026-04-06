# 🥗 Análise: Implementação de Funcionalidades de Nutrição

> **Data da Análise:** 06 de Abril de 2026
> **Contexto:** Avaliação da base atual do sistema Hejmai para expansão em nutrição.

---

## 1. O Que Já Temos (Base Aproveitável)

| Componente Atual | Como Ajuda na Nutrição |
|------------------|------------------------|
| **Catálogo de Produtos** | Base para tabela nutricional (um produto = um registro). |
| **Categorias** | Agrupamento por tipo alimentar (Frutas, Carnes, Laticínios). |
| **Histórico de Consumo** | Rastreamento do que foi ingerido ao longo do tempo. |
| **Movimentações** | Diferencia consumo (comi) de perda (estragou). |
| **Validade** | Controle de frescor e segurança dos alimentos. |
| **API REST + Bot** | Infraestrutura pronta para registrar refeições por voz/texto. |

---

## 2. O Que Falta (Precisa Criar)

| Requisito | Complexidade | Descrição |
|-----------|:------------:|-----------|
| **Tabela Nutricional** | 🟡 Média | Calorias, macros (prot/carb/gord) e micros por produto. |
| **Registro de Refeições** | 🟢 Baixa | Café, almoço, jantar, lanches (agrupar consumo em eventos). |
| **Metas Nutricionais** | 🟢 Baixa | Definir limites diários de calorias/macros por usuário. |
| **Relatório Nutricional** | 🟡 Média | Comparar Consumo vs Metas por período (dia/semana). |
| **Sugestão Alimentar** | 🔴 Alta | Sugerir refeições baseado no que tem em estoque + metas. |

---

## 3. Estrutura de Banco Proposta

```sql
-- 1. Informações Nutricionais (Vinculado ao Produto)
CREATE TABLE info_nutricional (
    produto_id INTEGER PRIMARY KEY,
    kcal_por_100g REAL,
    proteinas REAL,      -- g
    carboidratos REAL,   -- g
    gorduras REAL,       -- g
    fibras REAL,         -- g
    sodio REAL,          -- mg
    FOREIGN KEY (produto_id) REFERENCES produtos(id)
);

-- 2. Registro de Refeições (O evento de comer)
CREATE TABLE refeicoes (
    id INTEGER PRIMARY KEY,
    data DATE,
    tipo TEXT,           -- 'cafe', 'almoco', 'jantar', 'lanche'
    observacao TEXT
);

-- 3. Itens da Refeição (O que foi comido)
CREATE TABLE itens_refeicao (
    id INTEGER PRIMARY KEY,
    refeicao_id INTEGER,
    produto_id INTEGER,
    quantidade REAL,     -- em gramas ou unidades
    FOREIGN KEY (refeicao_id) REFERENCES refeicoes(id),
    FOREIGN KEY (produto_id) REFERENCES produtos(id)
);
```

---

## 4. Estimativa de Esforço

| Funcionalidade | Esforço | Depende de |
|----------------|:-------:|------------|
| Cadastrar info nutricional | 🟢 2-3h | Tabela nutricional |
| Registrar refeição via bot | 🟢 3-4h | Tabela nutricional |
| Relatório diário/semanal | 🟡 4-6h | Registro de refeições |
| Alerta de excesso/déficit | 🟡 4-6h | Metas + relatórios |
| Sugestão inteligente (IA) | 🔴 8-12h | IA + base nutricional |

---

## 5. Recomendação de Implementação

1. **Fase 1 (Fundação):** Criar tabela `info_nutricional` e permitir cadastro (manual ou via scraping de bancos de dados públicos como TACO/IBGE).
2. **Fase 2 (Entrada de Dados):** Permitir registrar refeições no Bot (`/almoco arroz frango`).
3. **Fase 3 (Feedback):** Dashboard no Streamlit mostrando "Calorias consumidas hoje vs Meta".

### Pontos Fortes para Começar Agora
- O sistema já sabe **o que você tem** (estoque).
- O sistema já sabe **o que você gastou** (consumo/perda).
- Falta apenas saber **o valor nutricional** do que foi gasto.
