import ollama
from sqlalchemy import text
from sqlalchemy.orm import Session


class AnalistaEstoque:
    def __init__(self, model="llama3"):
        self.model = model

    def gerar_query(self, pergunta_usuario: str):
        prompt_sistema = """
        Você é um analista de dados especializado em SQLite. 
        TABELAS:
        - produtos (id, nome, categoria, estoque_atual)
        - movimentacoes (id, produto_id, quantidade, tipo, data_movimento)
        
        REGRAS:
        1. Retorne APENAS o código SQL.
        2. Para saídas de estoque, a quantidade na tabela 'movimentacoes' é negativa.
        3. Use JOIN entre produtos e movimentacoes quando necessário.
        
        PERGUNTA: {pergunta}
        SQL:
        """

        print("chat com OLLAMA")

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": prompt_sistema.format(pergunta=pergunta_usuario),
                }
            ],
        )
        return response["message"]["content"]

    async def responder_pergunta(self, pergunta: str, db: Session):
        print("responder_pergunta()")
        # 1. IA gera o SQL
        sql_query = self.gerar_query(pergunta)

        # 2. Executa no banco (Cuidado: sanitize ou use readonly user)
        resultado = db.execute(text(sql_query)).mappings().all()

        # 3. IA interpreta o resultado
        prompt_final = f"O usuário perguntou: {pergunta}. O resultado do banco foi: {resultado}. Responda de forma amigável."
        final_resp = ollama.chat(
            model=self.model, messages=[{"role": "user", "content": prompt_final}]
        )

        return final_resp["message"]["content"]
