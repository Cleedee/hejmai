"""
Coordinator Agent para o Hejmai.

Este é o "cérebro" do sistema. Ele recebe perguntas em linguagem natural,
decide qual ferramenta usar e sintetiza a resposta final.
"""

from agno.agent import Agent
from agno.models.ollama import Ollama

from hejmai.agents.tools.finance import FinanceTool
from hejmai.agents.tools.inventory import InventoryTool
from hejmai.agents.tools.projection import ProjectionTool
from hejmai.config import config


def get_coordinator_agent() -> Agent:
    """
    Retorna a instância do Agente Coordenador.

    O coordenador tem acesso às ferramentas de Inventário, Finanças e Projeção.
    """
    return Agent(
        name="Hejmai Coordinator",
        model=Ollama(id=config.MODEL(), host=config.OLLAMA_BASE_URL()),
        tools=[InventoryTool, FinanceTool, ProjectionTool],
        instructions=[
            "REGRAS CRÍTICAS:",
            "1. Use SEMPRE as ferramentas para obter dados.",
            "2.Após chamar uma ferramenta, leia CUIDADOSAMENTE o resultado exato que ela retorna.",
            "3. Use APENAS os dados retornados pela ferramenta. NÃO invente, NÃO arredonde, NÃO acrescente.",
            "4. Se a ferramenta retorna '1 kg', diga '1 kg'. Se retorna '31 kg', diga '31 kg'.",
            "5. Se não houver dados ou a ferramenta não retornar nada, diga que não encontrou.",
            "",
            "Ferramentas:",
            "consultar_estoque(termo_busca): busca produtos no estoque.",
            "verificar_alertas_estoque(): lista produtos acabando/vencendo.",
            "analisar_frequencia_consumo(produto_nome): histórico de consumo.",
            "registrar_consumo(produto_nome, quantidade): REGISTRA BAIXA (só se pedido!).",
            "verificar_gastos(categoria): gastos recentes.",
            "consultar_historico_precos(produto_nome, dias): histórico de preços de um produto.",
            "previsao_reposicao(): itens para repor.",
            "",
            "Responda em Português. Seja direto.",
        ],
        markdown=True,
    )
