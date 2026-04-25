# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não Lançado]

### Corrigido
- Erro no endpoint /produtos/unificar
- Horário do job não usa o GMT-3

## [0.1.1] - 2026-04-22

### Corrigido
- Dashboard: KeyError nas colunas `categoria`, `estoque_atual`, `unidade_medida` (endpoint `/produtos/alertas` não retornava esses campos)
- Analytics: Gráfico de variação de preços não exibia (usava apenas produtos com alertas, alterado para usar `/produtos/todos`)

## [0.1.0] - 2026-04-22

### Adicionado
- Projeto inicial Hejmai (gestão de despensa e planejamento de refeições)
