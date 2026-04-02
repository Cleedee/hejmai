"""
Validadores de dados para entrada manual de estoque.

Este módulo fornece funções para validar dados antes de enviar para a API,
garantindo que apenas dados corretos sejam persistidos.
"""

from typing import List
import pandas as pd


def validate_carga_manual(df: pd.DataFrame) -> List[str]:
    """
    Valida dados de carga manual de estoque.
    
    Verifica:
    - Nome do produto preenchido
    - Quantidade maior que zero
    - Preço não negativo
    - Categoria válida
    - Data de validade futura (opcional)
    
    Args:
        df: DataFrame com colunas ['nome', 'categoria', 'quantidade', 
                                   'unidade', 'preco_pago', 'data_validade']
    
    Returns:
        Lista de mensagens de erro. Lista vazia significa que todos os dados são válidos.
    
    Example:
        >>> df = pd.DataFrame([{"nome": "", "quantidade": -1}])
        >>> validate_carga_manual(df)
        ['Nome do produto é obrigatório.', 'Quantidade deve ser maior que zero.']
    """
    erros = []
    
    if df.empty:
        erros.append("Adicione pelo menos um item à lista.")
        return erros
    
    # Verificar nome do produto
    if df["nome"].isnull().any() or (df["nome"].str.strip() == "").any():
        erros.append("Nome do produto é obrigatório.")
    
    # Verificar quantidade
    if "quantidade" in df.columns:
        if (df["quantidade"] <= 0).any():
            erros.append("Quantidade deve ser maior que zero.")
        
        # Alerta para quantidades muito altas (possível erro de digitação)
        if (df["quantidade"] > 100).any():
            erros.append(
                f"Quantidades muito altas (>100) podem indicar erro de digitação. "
                f"Verifique os itens: {', '.join(df[df['quantidade'] > 100]['nome'].tolist())}"
            )
    
    # Verificar preço
    if "preco_pago" in df.columns:
        if (df["preco_pago"] < 0).any():
            erros.append("Preço não pode ser negativo.")
        
        # Alerta para preços muito altos
        if (df["preco_pago"] > 1000).any():
            itens_caros = df[df["preco_pago"] > 1000]["nome"].tolist()
            erros.append(
                f"Preços muito altos (>R$ 1000) podem indicar erro. "
                f"Verifique: {', '.join(itens_caros)}"
            )
    
    # Verificar categoria
    if "categoria" in df.columns:
        categorias_validas = {
            "Açougue", "Laticínios", "Hortifruti", "Mercearia",
            "Higiene", "Limpeza", "Padaria", "Bebidas", "Outros"
        }
        categorias_invalidas = set(df["categoria"].unique()) - categorias_validas
        if categorias_invalidas:
            erros.append(
                f"Categorias inválidas: {', '.join(categorias_invalidas)}. "
                f"Use uma das categorias permitidas."
            )
    
    # Verificar unidade de medida
    if "unidade" in df.columns:
        unidades_validas = {"un", "kg", "l", "g", "ml", "pct", "cx"}
        unidades_invalidas = set(df["unidade"].str.lower().unique()) - unidades_validas
        if unidades_invalidas:
            erros.append(
                f"Unidades inválidas: {', '.join(unidades_invalidas)}. "
                f"Use: un, kg, l, g, ml, pct, cx"
            )
    
    return erros


def validate_produto_individual(nome: str, quantidade: float, preco: float) -> List[str]:
    """
    Valida dados de um único produto.
    
    Args:
        nome: Nome do produto
        quantidade: Quantidade do produto
        preco: Preço pago
    
    Returns:
        Lista de mensagens de erro
    """
    erros = []
    
    if not nome or not nome.strip():
        erros.append("Nome do produto é obrigatório.")
    
    if quantidade <= 0:
        erros.append("Quantidade deve ser maior que zero.")
    
    if preco < 0:
        erros.append("Preço não pode ser negativo.")
    
    return erros
