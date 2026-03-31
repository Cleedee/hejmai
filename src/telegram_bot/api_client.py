import httpx


class EstoqueAPI:
    def __init__(self, base_url: str = "http://127.0.0.1:8081"):
        self.base_url = base_url

    async def lista_compras_detalhada(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/produtos/lista-compras-detalhada"
            )
            return response.json()

    async def buscar_historico_consumo(self, dias: int = 30):
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/itens/historico-consumo/?dias={dias}"
            )
            return r.json()

    async def buscar_alertas(self, dias: int = 5):
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/itens/alertas-validade/"
            response = await client.get(url, params={"dias": dias})

            if response.status_code != 200:
                print(f"Erro na API: Status {response.status_code} - {response.text}")
                return []

            return response.json()

    async def listar_produtos(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/produtos/todos")
            response.raise_for_status()
            return response.json()

    async def adicionar_item(self, item_dict: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/itens/", json=item_dict)
            response.raise_for_status()
            return response.json()

    async def consumir_item(self, item_id, quantidade: float | None = None):
        async with httpx.AsyncClient() as client:
            if quantidade:
                url = f"{self.base_url}/itens/{item_id}/{quantidade}/consumir"
            else:
                url = f"{self.base_url}/itens/{item_id}/consumir"
            response = await client.patch(url)

    async def processar_entrada_livre(self, texto):
        async with httpx.AsyncClient() as client:
            print("1")
            response = await client.post(
                f"{self.base_url}/processar-entrada-livre",
                json={"texto": texto},
                timeout=160.0,  # O Ollama pode demorar um pouco
            )

            print("2")
            if response.status_code == 200:
                print("3")
                msg = response.json()["mensagem_bot"]
                print("4")
                return f"✅ {msg}"
            else:
                print("5")
                return "❌ Erro ao processar no servidor."

    async def sugerir_receita(self):
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/sugerir-receita"
            response = await client.get(url)
            if response.status_code != 200:
                print(f"Erro na API: Status {response.status_code} - {response.text}")
                return []
            return response.json()
