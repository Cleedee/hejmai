# 📝 Especificação: Comando de Lista de Compras no Bot

## 📋 Visão Geral

Adicionar um comando no bot Telegram que permita ao usuário montar uma lista de compras manual, incluindo itens que **não precisam existir previamente no banco de dados**. A lista pode ser enviada por mensagem formatada ou salva para consulta posterior.

---

## 🎯 Funcionalidades

### 1. Adicionar Item à Lista
- **Comando**: `/lista_add <quantidade> <unidade> <nome>`
- **Exemplo**: `/lista_add 2 kg Arroz Integral`
- **Exemplo**: `/lista_add 5 un Detergente`
- **Não exige** que o produto exista no banco

### 2. Ver Lista Atual
- **Comando**: `/lista_ver`
- Mostra todos os itens adicionados na sessão atual

### 3. Remover Item da Lista
- **Comando**: `/lista_rem <número>` (remove pelo índice)
- **Exemplo**: `/lista_rem 2`

### 4. Limpar Lista
- **Comando**: `/lista_limpar`
- Remove todos os itens da sessão

### 5. Enviar Lista Formatada
- **Comando**: `/lista_enviar`
- Gera mensagem formatada pronta para copiar/colar no Keep

---

## 🗃️ Armazenamento

### Opção A: Session State (Recomendada para uso simples)

Os itens são armazenados no `context.user_data` do Telegram Bot, persistindo apenas durante a sessão do usuário.

**Vantagens:**
- Simples de implementar
- Não requer mudanças no banco
- Cada usuário tem sua própria lista

**Desvantagens:**
- Lista é perdida se o bot reiniciar
- Não persiste entre sessões longas

### Opção B: Nova Tabela no Banco (Para uso avançado)

Criar tabela `listas_compras` com:
```sql
CREATE TABLE listas_compras (
    id INTEGER PRIMARY KEY,
    telegram_user_id INTEGER NOT NULL,
    nome_produto TEXT NOT NULL,
    quantidade REAL NOT NULL,
    unidade TEXT NOT NULL,
    categoria TEXT,
    adicionado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    comprado INTEGER DEFAULT 0
);
```

**Vantagens:**
- Persiste entre sessões
- Permite histórico de listas
- Múltiplas listas por usuário

**Desvantagens:**
- Mais complexo
- Requer migração de banco

---

## 📐 Design do Comando

### `/lista_add`

**Formato:**
```
/lista_add <quantidade> <unidade> <nome do produto> [categoria]
```

**Parâmetros:**
| Parâmetro | Obrigatório | Descrição | Exemplo |
|-----------|-------------|-----------|---------|
| quantidade | ✅ | Quantidade numérica | `2`, `0.5`, `10` |
| unidade | ✅ | Unidade de medida | `kg`, `un`, `l`, `pct` |
| nome | ✅ | Nome do produto | `Arroz Integral` |
| categoria | ❌ | Categoria (auto-detectada se omitida) | `Mercearia` |

**Exemplos Válidos:**
```
/lista_add 2 kg Arroz Integral
/lista_add 5 un Sabão em Pó
/lista_add 1.5 l Leite
/lista_add 10 un Ovo
```

**Resposta do Bot:**
```
✅ Adicionado à lista:
📦 2 kg de Arroz Integral

📝 Itens na lista: 3
```

---

### `/lista_ver`

**Resposta do Bot:**
```
📝 *Sua Lista de Compras*

1. 🌾 2 kg de Arroz Integral
2. 🧼 5 un de Sabão em Pó
3. 🥛 1.5 l de Leite

💰 *Total estimado:* R$ 45.50
📦 *Itens:* 3
```

---

### `/lista_rem <número>`

**Exemplo:**
```
/lista_rem 2
```

**Resposta:**
```
❌ Removido: 5 un de Sabão em Pó

📝 Itens restantes: 2
```

---

### `/lista_enviar`

**Resposta do Bot:**
```
📋 *Lista de Compras para o Mercado*
━━━━━━━━━━━━━━━━━━━━━━

☐ 2 kg de Arroz Integral
☐ 5 un de Sabão em Pó
☐ 1.5 l de Leite

━━━━━━━━━━━━━━━━━━━━━━
💰 Estimativa: R$ 45.50

💡 _Cole esta lista no Google Keep e ative as checkboxes!_
```

---

## 🔧 Implementação Técnica

### Handler do Bot

```python
async def comando_lista_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona item à lista de compras."""
    # Inicializa lista se não existir
    if "lista_compras" not in context.user_data:
        context.user_data["lista_compras"] = []
    
    # Parse dos argumentos
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "💡 Use: /lista_add <qtd> <unidade> <nome>\n"
            "Ex: /lista_add 2 kg Arroz"
        )
        return
    
    try:
        quantidade = float(args[0])
        unidade = args[1].lower()
        nome = " ".join(args[2:])
        
        # Valida unidade
        unidades_validas = {"un", "kg", "l", "g", "ml", "pct", "cx"}
        if unidade not in unidades_validas:
            await update.message.reply_text(
                f"❌ Unidade inválida: '{unidade}'\n"
                f"Use: {', '.join(sorted(unidades_validas))}"
            )
            return
        
        # Adiciona à lista
        item = {
            "nome": nome,
            "quantidade": quantidade,
            "unidade": unidade,
        }
        context.user_data["lista_compras"].append(item)
        
        total_itens = len(context.user_data["lista_compras"])
        
        await update.message.reply_text(
            f"✅ Adicionado à lista:\n"
            f"📦 {quantidade} {unidade} de {nome}\n\n"
            f"📝 Itens na lista: {total_itens}"
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Quantidade deve ser um número.\n"
            "Ex: /lista_add 2 kg Arroz"
        )
```

### Comandos Registrados

```python
app.add_handler(CommandHandler("lista_add", comando_lista_add))
app.add_handler(CommandHandler("lista_ver", comando_lista_ver))
app.add_handler(CommandHandler("lista_rem", comando_lista_remover))
app.add_handler(CommandHandler("lista_limpar", comando_lista_limpar))
app.add_handler(CommandHandler("lista_enviar", comando_lista_enviar))
```

---

## 📊 Endpoints da API (Opcional)

Se quiser persistir no banco:

### `POST /lista-compras/itens`
```json
{
  "nome": "Arroz Integral",
  "quantidade": 2.0,
  "unidade": "kg"
}
```

### `GET /lista-compras`
```json
[
  {"nome": "Arroz Integral", "quantidade": 2.0, "unidade": "kg"},
  {"nome": "Sabão em Pó", "quantidade": 5.0, "unidade": "un"}
]
```

### `DELETE /lista-compras/{index}`

### `DELETE /lista-compras`

---

## 🧪 Casos de Teste

| Cenário | Entrada | Resultado Esperado |
|---------|---------|-------------------|
| Item válido | `/lista_add 2 kg Arroz` | ✅ Adicionado |
| Unidade inválida | `/lista_add 2 metros Arroz` | ❌ Erro de unidade |
| Quantidade inválida | `/lista_add abc kg Arroz` | ❌ Erro de número |
| Faltando argumentos | `/lista_add 2` | ❌ Erro de formato |
| Lista vazia | `/lista_ver` | ℹ️ "Lista vazia" |
| Remover item | `/lista_rem 1` | ✅ Removido |
| Remover inexistente | `/lista_rem 99` | ❌ Item não existe |
| Limpar lista | `/lista_limpar` | ✅ Lista vazia |
| Enviar lista | `/lista_enviar` | 📋 Mensagem formatada |

---

## 🎨 Mensagens de Erro

| Erro | Mensagem |
|------|----------|
| Formato inválido | `💡 Use: /lista_add <qtd> <unidade> <nome>` |
| Unidade inválida | `❌ Unidade inválida. Use: un, kg, l, g, ml, pct, cx` |
| Quantidade inválida | `❌ Quantidade deve ser um número (ex: 2 ou 0.5)` |
| Lista vazia | `📝 Sua lista está vazia. Adicione itens com /lista_add` |
| Item não existe | `❌ Item 99 não encontrado na lista` |

---

## 📝 Checklist de Implementação

- [ ] Criar handler `comando_lista_add`
- [ ] Criar handler `comando_lista_ver`
- [ ] Criar handler `comando_lista_remover`
- [ ] Criar handler `comando_lista_limpar`
- [ ] Criar handler `comando_lista_enviar`
- [ ] Registrar handlers no bot
- [ ] Adicionar ao `/start` e documentação
- [ ] Testar todos os casos de uso
- [ ] Atualizar documentação do bot

---

## 🔮 Futuras Melhorias

1. **Categorias automáticas**: Usar IA para detectar categoria do produto
2. **Preço estimado**: Buscar último preço pago se produto existir no banco
3. **Lista compartilhada**: Múltiplos usuários acessam mesma lista
4. **Integração com Keep**: Enviar lista diretamente para Google Keep
5. **Histórico de listas**: Salvar listas anteriores para reutilizar
6. **Checklist interativo**: Usar botões inline para marcar itens como comprados
