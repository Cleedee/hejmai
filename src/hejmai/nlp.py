import json
import datetime
import os
from difflib import get_close_matches

import ollama
from sqlalchemy.orm import Session

from hejmai import models
from hejmai.config import config


async def refinamento_categoria(categoria_ia: str, db: Session):
    # 1. Busca todas as categorias reais do seu banco
    categorias_reais = [c.nome for c in db.query(models.Categoria).all()]

    # 2. Tenta encontrar a mais próxima (Fuzzy Matching)
    matches = get_close_matches(categoria_ia, categorias_reais, n=1, cutoff=0.3)

    if matches:
        return matches[0]
    return "Outros"  # Fallback caso a IA invente algo bizarro


class Receitas:
    def __init__(self, model: str = None):
        self.model = model or config.MODEL()
        self.client = ollama.AsyncClient(host=config.OLLAMA_BASE_URL())

    async def sugerir_receita(self, itens_vencendo: list):
        if not itens_vencendo:
            return "Não há itens vencendo em breve. Use o que preferir do estoque!"

        ingredientes = ", ".join([p["nome"] for p in itens_vencendo])

        prompt = f"""
        Você é um Chef especializado em economia doméstica. 
        Tenho os seguintes ingredientes que VENCEM EM BREVE: {ingredientes}.
        
        TAREFA:
        1. Sugira UMA receita principal que use o máximo desses itens.
        2. A receita deve ser nutritiva e atraente para duas crianças (7 e 10 anos).
        3. Seja breve nos passos (máximo 5 passos).
        4. Liste ingredientes extras simples que provavelmente tenho na despensa (sal, óleo, cebola).
        
        Responda em Português.
        """

        response = await self.client.chat(
            model=self.model, messages=[{"role": "user", "content": prompt}]
        )
        return response["message"]["content"]


class ProcessadorCompras:
    def __init__(self, model: str = None):
        self.model = model or config.MODEL()
        self.client = ollama.AsyncClient(host=config.OLLAMA_BASE_URL())

    async def extrair_dados(self, texto: str):
        hoje = datetime.date.today().isoformat()

        prompt = f"""
        Você é um parser de alta precisão para um sistema de inventário doméstico.
        Sua tarefa é transformar o texto do usuário em um JSON estruturado para um banco de dados relacional.

        CATEGORIAS PERMITIDAS: [Açougue, Laticínios, Hortifruti, Mercearia, Higiene, Limpeza, Padaria, Bebidas].
        Escolha a que melhor se adapta ao item.

        REGRAS DE EXTRAÇÃO:
        1. LOCAL: Identifique o estabelecimento (ex: 'Mercado Extra', 'Armazém Dom Severino').
        2. PRODUTOS: Normalize os nomes (ex: 'leite condensado moça' -> 'Leite Condensado').
        3. QUANTIDADE: Extraia apenas o número. Se não houver, assuma 1.0.
        4. PREÇO: Extraia o valor total pago por aquele item (float).
        5. VALIDADE (Apenas para cálculo interno): Estime a validade a partir de hoje ({hoje}):
           - Laticínios: +7 dias.
           - Carnes: +15 dias.
           - Frutas/Legumes/Hortaliças: + 7 dias.
           - Grãos/Latas: +180 dias.
           - Limpeza: +365 dias.
           - Outros: +100 dias.

        TEXTO DO USUÁRIO:
        "{texto}"

        EXEMPLO DE SAÍDA DESEJADA:
        {{
            "local_compra": "Nome do Mercado",
            "itens": [
                {{
                    "nome": "Arroz Integral",
                    "categoria": "Grãos",
                    "quantidade": 2.0,
                    "unidade": "kg",
                    "preco_pago": 15.50,
                    "data_validade": "2026-09-22"
                }}
            ]
        }}

        RETORNE APENAS O JSON:
        """

        response = await self.client.chat(
            model=self.model, messages=[{"role": "user", "content": prompt}]
        )

        # Limpeza simples para garantir que pegamos apenas o bloco JSON
        conteudo = response["message"]["content"]
        print(conteudo)
        inicio = conteudo.find("{")
        fim = conteudo.rfind("}") + 1
        return json.loads(conteudo[inicio:fim])
