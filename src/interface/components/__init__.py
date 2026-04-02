"""
Componentes reutilizáveis da interface Streamlit.

Módulos:
- nlp_processor: Componente de processamento de texto NLP
- product_charts: Componente de gráficos de preços
- budget: Componente de gerenciamento de orçamento
"""

from hejmai.interface.components.nlp_processor import render_nlp_processor
from hejmai.interface.components.product_charts import render_price_chart
from hejmai.interface.components.budget import render_budget_manager

__all__ = [
    "render_nlp_processor",
    "render_price_chart",
    "render_budget_manager",
]
