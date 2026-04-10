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


def get_coordinator_agent() -> Agent:
    """
    Retorna a instância do Agente Coordenador.

    O coordenador tem acesso às ferramentas de Inventário, Finanças e Projeção.
    """
    return Agent(
        name="Hejmai Coordinator",
        model=Ollama(id="qwen3.5:2b"),
        tools=[InventoryTool, FinanceTool, ProjectionTool],
        instructions=[
            "Você é o Hejmai, um assistente inteligente de gestão doméstica.",
            "Sua missão é ajudar o usuário a controlar seu estoque e finanças.",
            "Use as ferramentas disponíveis para obter dados reais antes de responder.",
            "Sempre responda em Português do Brasil.",
            "Seja amigável, direto e útil.",
            "Se não souber a resposta, diga que pode buscar a informação.",
        ],
        markdown=True,
        show_tool_calls=True,
    )
