# 🕵️ Vigia do Estoque

Sistema de monitoramento de consumo e validade com notificações via Telegram.

## 📋 Visão Geral

O **Vigia do Estoque** analisa diariamente:

1. **Burn Rate** (ritmo de consumo) de cada produto
2. **Dias restantes** até o produto acabar
3. **Produtos próximos do vencimento**

E envia um relatório formatado via Telegram.

---

## 🔧 Configuração

### Variáveis de Ambiente

Adicione ao seu `.env`:

```bash
# Token do Bot do Telegram (obtenha em @BotFather)
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Seu Chat ID (use @userinfobot no Telegram)
TELEGRAM_CHAT_ID=123456789

# Opcional: Enviar relatório mesmo sem alertas urgentes
VIGIA_ENVIAR_SEMPRE=false
```

### Como Obter o Chat ID

1. No Telegram, inicie uma conversa com `@userinfobot`
2. Ele mostrará seu Chat ID (ex: `123456789`)
3. Copie e cole no `.env`

---

## 📖 Comandos do Telegram

### `/vigia` - Executar Análise Manual

Executa o vigia do estoque imediatamente.

```
/vigia
```

**Resposta:**
```
🛒 VIGIA DO ESTOQUE
Relatório Diário
📅 02/04/2026 08:00

📦 PRODUTOS ACABANDO EM BREVE
━━━━━━━━━━━━━━━━━━━━━━
🔴 Arroz (2 dias restantes)
   Estoque: 0.5kg | Consumo: 0.3kg/dia

⏰ PRODUTOS VENCENDO
━━━━━━━━━━━━━━━━━━━━━━
⚠️ Iogurte vence em 2 dias (04/04)

📊 RESUMO
━━━━━━━━━━━━━━━━━━━━━━
• 1 produtos com estoque crítico
• 1 produtos vencendo em breve
• 32 produtos monitorados
```

### `/vigia_config` - Ver Configurações

Mostra as configurações atuais do vigia.

```
/vigia_config
```

### `/start` - Ajuda

Mostra mensagem de boas-vindas com comandos disponíveis.

---

## ⏰ Relatório Automático

O relatório é enviado **automaticamente todos os dias às 08:00** se houver:

- Produtos acabando em menos de 3 dias, OU
- Produtos vencendo hoje ou amanhã, OU
- 5 ou mais produtos com alertas

Se não houver alertas urgentes, o relatório **não é enviado** para não incomodar.

---

## 🧮 Como Funciona o Cálculo

### Burn Rate (Ritmo de Consumo)

```
Burn Rate = Total Consumido nos Últimos 30 Dias / 30
```

Exemplo:
- Se você consumiu 6kg de arroz em 30 dias
- Burn Rate = 6 / 30 = **0.2kg/dia**

### Dias Restantes

```
Dias Restantes = Estoque Atual / Burn Rate
```

Exemplo:
- Estoque: 1kg de arroz
- Burn Rate: 0.2kg/dia
- Dias Restantes = 1 / 0.2 = **5 dias**

### Quando Não Há Consumo

Se o burn rate for 0 (produto não foi consumido nos últimos 30 dias):
- Dias Restantes = 999 (não será alertado)

---

## 🎯 Configurações Padrão

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `DIAS_PARA_ACABAR_ALERTA` | 7 | Alerta se for acabar em menos de X dias |
| `DIAS_PARA_VENCER_ALERTA` | 5 | Alerta se for vencer em menos de X dias |
| `DIAS_ANALISE_CONSUMO` | 30 | Período de análise do burn rate (dias) |

Para alterar, edite `src/hejmai/vigia_estoque/analise_consumo.py`.

---

## 🖥️ Execução Manual (CLI)

Além do Telegram, você pode executar via linha de comando:

```bash
# No container Docker
docker exec hejmai_api uv run python -m hejmai.vigia_estoque.vigia

# Localmente (com DATABASE_PATH configurado)
DATABASE_PATH=./data/estoque.db uv run python -m hejmai.vigia_estoque.vigia
```

---

## 📊 Exemplo de Relatório

```
🛒 *VIGIA DO ESTOQUE*
_Relatório Diário_
📅 02/04/2026 08:00

📦 *PRODUTOS ACABANDO EM BREVE*
━━━━━━━━━━━━━━━━━━━━━━
🔴 Arroz (2 dias restantes)
   Estoque: 0.5kg | Consumo: 0.3kg/dia
   
🟡 Leite (5 dias restantes)
   Estoque: 1.5L | Consumo: 0.3L/dia

⏰ *PRODUTOS VENCENDO*
━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Iogurte*
   Vence amanhã (03/04)
   
⚠️ *Queijo Mussarela*
   Vence em 4 dias (06/04)

📊 *RESUMO*
━━━━━━━━━━━━━━━━━━━━━━
• 1 produtos com estoque crítico
• 2 produtos vencendo em breve
• 32 produtos monitorados
```

---

## 🔍 Interpretação dos Ícones

| Ícone | Significado |
|-------|-------------|
| 🔴 | Acabando em 3 dias ou menos (URGENTE) |
| 🟡 | Acabando em 4-7 dias (ATENÇÃO) |
| ⚠️ | Vencendo em breve |
| ✅ | Tudo certo |

---

## 🛠️ Troubleshooting

### "Bot não responde"

Verifique se o `TELEGRAM_TOKEN` está correto no `.env`.

### "Nenhum alerta enviado"

O vigia só envia se houver alertas urgentes. Execute `/vigia` para ver o relatório completo.

### "Erro de banco de dados"

Verifique se `DATABASE_PATH` está configurado corretamente.

---

## 📁 Estrutura de Arquivos

```
src/hejmai/
├── vigia_estoque/
│   ├── __init__.py
│   ├── analise_consumo.py    # Lógica de análise
│   └── vigia.py              # Script principal
└── telegram_bot/
    ├── __init__.py
    ├── __main__.py           # Entry point do bot
    └── handlers.py           # Handlers de comandos
```
