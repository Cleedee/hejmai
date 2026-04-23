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
from hejmai.agents.tools.recipe import RecipeTool
from hejmai.config import config


def get_coordinator_agent() -> Agent:
    """
    Retorna a instância do Agente Coordenador.

    O coordenador tem acesso às ferramentas de Inventário, Finanças, Projeção e Receitas.
    """

    ferramentas = InventoryTool + FinanceTool + ProjectionTool + RecipeTool

    return Agent(
        name="Hejmai Coordinator",
        model=Ollama(
            id=config.MODEL(),
            host=config.OLLAMA_BASE_URL(),
            options={
                "num_thread": 3,  # Ajuste para o número de núcleos físicos da sua CPU
                "num_ctx": 1024,  # Contexto reduzido economiza RAM e processamento
                "temperature": 0.2,  # Menor temperatura ajuda em modelos pequenos a serem mais precisos
                "top_p": 0.9,
            },
        ),
        tools=ferramentas,
        instructions=[
            "Se você precisar de informações externas, use as ferramentas disponíveis.",
            "Responda SEMPRE no formato JSON quando chamar uma ferramenta.",
            "Não tente adivinhar valores, peça se não souber o parâmetro.",
        ],
        markdown=True,
        debug_mode=True,
    )
