"""
Coordinator Agent para o Hejmai.

Este é o "cérebro" do sistema. Ele recebe perguntas em linguagem natural,
decide qual ferramenta usar e sintetiza a resposta final.
"""

from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.team import Team, TeamMode

from hejmai.agents.tools.finance import FinanceTool
from hejmai.agents.tools.inventory import InventoryTool
from hejmai.agents.tools.projection import ProjectionTool
from hejmai.agents.tools.recipe import ReceitaTool
from hejmai.config import config


def get_coordinator_agent() -> Team:
    """
    Retorna a instância do Agente Coordenador.

    O coordenador tem acesso às ferramentas de Inventário, Finanças e Projeção.
    """

    model_config = Ollama(
        id=config.MODEL(),
        host=config.OLLAMA_BASE_URL(),
        options={
            "num_thread": 3,  # Ajuste para o número de núcleos físicos da sua CPU
            "num_ctx": 1024,  # Contexto reduzido economiza RAM e processamento
            "temperature": 0.2,  # Menor temperatura ajuda em modelos pequenos a serem mais precisos
            "top_p": 0.9,
        },
    )

    # 1. Agente especialista em receitas
    receitas_agent = Agent(
        name="Cozinheiro",
        role="Sugere receitas baseadas em lista de receitas disponíveis e ingredientes em estoque",
        model=model_config,
        instructions=[
            "Sugere receitas baseadas em lista de receitas disponíveis e ingredientes em estoque",
            "Responda SEMPRE no formato JSON quando chamar uma ferramenta.",
        ],
        tools=ReceitaTool,
    )

    # 2. Agente especialista em finanças
    financas_agent = Agent(
        name="Especialista em Finanças",
        role="Fornece capacidades de consulta de finanças.",
        model=model_config,
        instructions=[
            "Responda SEMPRE no formato JSON quando chamar uma ferramenta.",
        ],
        tools=FinanceTool,
    )

    # 3. Agente especialista em projeção
    projecao_agent = Agent(
        name="Especialista em Projeção",
        role="Fornece capacidades de previsão e análise de tendências.",
        model=model_config,
        instructions=[
            "",
            "Responda SEMPRE no formato JSON quando chamar uma ferramenta.",
        ],
        tools=ProjectionTool,
    )
    # 4. Agente especialista em inventário
    inventario_agent = Agent(
        name="Especialista em Inventário",
        role="Fornece capacidades de consulta do estoque.",
        model=model_config,
        instructions=[
            "",
            "Responda SEMPRE no formato JSON quando chamar uma ferramenta.",
        ],
        tools=InventoryTool,
    )

    # 5. O Coordenador
    team = Team(
        members=[financas_agent, projecao_agent, inventario_agent, receitas_agent],
        model=model_config,
        instructions=[
            "Delegue a tarefa para o agente correto.",
            "Se for sobre receitas, use Cozinheiro.",
            "Se for sobre o estoque, use Especialista em Inventário.",
            "Se for sobre financeiro, use Especialista em Finanças.",
            "Se for sobre projeção de gasto e consumo futuro, use Especialista em Projeção.",
            "Não tente adivinhar valores, peça se não souber o parâmetro.",
        ],
        markdown=True,
        debug_mode=True,
        mode=TeamMode.coordinate,
        show_members_responses=True,
    )
    return team
