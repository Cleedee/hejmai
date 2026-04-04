"""
Módulo de análise de consumo e validade do estoque.

Calcula:
- Burn rate (ritmo de consumo) por produto
- Dias restantes até acabar
- Produtos próximos do vencimento

Este módulo usa funções de crud.py para acesso ao banco de dados.
"""

import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from hejmai import crud


# =============================================================================
# Configurações
# =============================================================================

DIAS_PARA_ACABAR_ALERTA = 7  # Alerta se for acabar em menos de X dias
DIAS_PARA_VENCER_ALERTA = 5  # Alerta se for vencer em menos de X dias
DIAS_ANALISE_CONSUMO = 30    # Período de análise do burn rate (dias)


# =============================================================================
# Tipos de Dados
# =============================================================================

class ProdutoAlerta:
    """Representa um produto com alerta."""

    def __init__(
        self,
        nome: str,
        estoque_atual: float,
        unidade: str,
        burn_rate: float,
        dias_restantes: int,
        motivo: str,  # 'acabando' ou 'vencendo'
        data_validade: datetime.date = None,
    ):
        self.nome = nome
        self.estoque_atual = estoque_atual
        self.unidade = unidade
        self.burn_rate = burn_rate
        self.dias_restantes = dias_restantes
        self.motivo = motivo
        self.data_validade = data_validade

    def __repr__(self):
        return f"ProdutoAlerta({self.nome}, {self.dias_restantes} dias, {self.motivo})"


# =============================================================================
# Funções de Análise
# =============================================================================

def calcular_burn_rate(db: Session, produto_id: int, dias: int = DIAS_ANALISE_CONSUMO) -> float:
    """
    Calcula o burn rate (ritmo de consumo) de um produto.

    Args:
        db: Sessão do banco de dados
        produto_id: ID do produto
        dias: Período de análise em dias

    Returns:
        Burn rate em unidades/dia. 0 se não houver consumo.
    """
    # Usa crud para buscar consumo
    total_consumido = crud.get_consumo_periodo(db, produto_id, dias)
    
    if total_consumido == 0:
        return 0.0
    
    # Burn rate = total consumido / dias
    return total_consumido / dias


def calcular_dias_restantes(estoque_atual: float, burn_rate: float) -> int:
    """
    Calcula quantos dias o produto vai durar com base no burn rate.

    Args:
        estoque_atual: Quantidade atual em estoque
        burn_rate: Ritmo de consumo (unidades/dia)

    Returns:
        Dias restantes. 999 se burn_rate for 0 (produto não está sendo consumido).
    """
    if burn_rate <= 0:
        return 999  # Produto não está sendo consumido

    return int(estoque_atual / burn_rate)


def analisar_estoque(db: Session) -> Dict[str, Any]:
    """
    Analisa todo o estoque e identifica produtos com alerta.

    Args:
        db: Sessão do banco de dados

    Returns:
        Dict com:
        - 'produtos_acabando': Lista de ProdutoAlerta com estoque baixo
        - 'produtos_vencendo': Lista de ProdutoAlerta próximos do vencimento
        - 'total_monitorados': Total de produtos monitorados
        - 'data_analise': Data/hora da análise
    """
    hoje = datetime.date.today()

    produtos_acabando = []
    produtos_vencendo = []

    # Busca todos os produtos com estoque positivo via crud
    produtos = crud.get_produtos_com_estoque(db)

    for produto in produtos:
        # Calcula burn rate
        burn_rate = calcular_burn_rate(db, produto.id)
        dias_restantes = calcular_dias_restantes(produto.estoque_atual, burn_rate)

        # Verifica se está acabando
        if dias_restantes <= DIAS_PARA_ACABAR_ALERTA and burn_rate > 0:
            produtos_acabando.append(ProdutoAlerta(
                nome=produto.nome,
                estoque_atual=produto.estoque_atual,
                unidade=produto.unidade_medida,
                burn_rate=burn_rate,
                dias_restantes=dias_restantes,
                motivo="acabando",
            ))

        # Verifica se está vencendo
        if produto.ultima_validade:
            dias_para_vencer = (produto.ultima_validade - hoje).days

            if 0 <= dias_para_vencer <= DIAS_PARA_VENCER_ALERTA:
                produtos_vencendo.append(ProdutoAlerta(
                    nome=produto.nome,
                    estoque_atual=produto.estoque_atual,
                    unidade=produto.unidade_medida,
                    burn_rate=burn_rate,
                    dias_restantes=dias_para_vencer,
                    motivo="vencendo",
                    data_validade=produto.ultima_validade,
                ))

    # Ordena por urgência (menos dias primeiro)
    produtos_acabando.sort(key=lambda p: p.dias_restantes)
    produtos_vencendo.sort(key=lambda p: p.dias_restantes)

    return {
        "produtos_acabando": produtos_acabando,
        "produtos_vencendo": produtos_vencendo,
        "total_monitorados": len(produtos),
        "data_analise": datetime.datetime.now(),
        "config": {
            "dias_para_acabar_alerta": DIAS_PARA_ACABAR_ALERTA,
            "dias_para_vencer_alerta": DIAS_PARA_VENCER_ALERTA,
            "dias_analise_consumo": DIAS_ANALISE_CONSUMO,
        }
    }


def gerar_relatorio_texto(analise: Dict[str, Any]) -> str:
    """
    Gera relatório em texto formatado para envio via Telegram.
    
    Args:
        analise: Resultado da função analisar_estoque()
    
    Returns:
        String formatada para Telegram
    """
    linhas = []
    
    # Header
    linhas.append("🛒 *VIGIA DO ESTOQUE*")
    linhas.append(f"_Relatório Diário_")
    linhas.append(f"📅 {analise['data_analise'].strftime('%d/%m/%Y %H:%M')}")
    linhas.append("")
    
    # Produtos acabando
    if analise["produtos_acabando"]:
        linhas.append("📦 *PRODUTOS ACABANDO EM BREVE*")
        linhas.append("━" * 30)
        
        for produto in analise["produtos_acabando"]:
            emoji = "🔴" if produto.dias_restantes <= 3 else "🟡"
            linhas.append(
                f"{emoji} *{produto.nome}* ({produto.dias_restantes} dias)"
            )
            linhas.append(
                f"   Estoque: {produto.estoque_atual}{produto.unidade} | "
                f"Consumo: {produto.burn_rate:.2f}{produto.unidade}/dia"
            )
        
        linhas.append("")
    
    # Produtos vencendo
    if analise["produtos_vencendo"]:
        linhas.append("⏰ *PRODUTOS VENCENDO*")
        linhas.append("━" * 30)
        
        for produto in analise["produtos_vencendo"]:
            dias = produto.dias_restantes
            if dias == 0:
                texto_dias = "*VENCE HOJE!*"
            elif dias == 1:
                texto_dias = "Vence amanhã"
            else:
                texto_dias = f"Vence em {dias} dias ({produto.data_validade.strftime('%d/%m')})"
            
            linhas.append(f"⚠️ *{produto.nome}*")
            linhas.append(f"   {texto_dias}")
        
        linhas.append("")
    
    # Resumo
    linhas.append("📊 *RESUMO*")
    linhas.append("━" * 30)
    
    total_alertas = len(analise["produtos_acabando"]) + len(analise["produtos_vencendo"])
    
    if total_alertas == 0:
        linhas.append("✅ Tudo certo! Nenhum produto precisa de atenção.")
    else:
        linhas.append(f"• {len(analise['produtos_acabando'])} produtos com estoque crítico")
        linhas.append(f"• {len(analise['produtos_vencendo'])} produtos vencendo em breve")
    
    linhas.append(f"• {analise['total_monitorados']} produtos monitorados")
    
    return "\n".join(linhas)


def tem_alertas_urgentes(analise: Dict[str, Any]) -> bool:
    """
    Verifica se há alertas que justificam envio de mensagem.
    
    Args:
        analise: Resultado da análise
    
    Returns:
        True se houver alertas urgentes
    """
    # Alerta se tiver produto acabando em menos de 3 dias
    acaba_muito_em_breve = any(
        p.dias_restantes <= 3 for p in analise["produtos_acabando"]
    )
    
    # Alerta se tiver produto vencendo hoje ou amanhã
    vence_muito_em_breve = any(
        p.dias_restantes <= 1 for p in analise["produtos_vencendo"]
    )
    
    # Alerta se tiver mais de 5 produtos com problema
    muitos_alertas = (
        len(analise["produtos_acabando"]) + len(analise["produtos_vencendo"])
    ) >= 5
    
    return acaba_muito_em_breve or vence_muito_em_breve or muitos_alertas
