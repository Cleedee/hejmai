"""
Cliente HTTP para comunicação com a API FastAPI.

Este módulo encapsula todas as chamadas HTTP com:
- Retry exponencial para falhas temporárias
- Tratamento de erros específico por tipo
- Timeout configurável
- Interface type-safe para todos os endpoints
"""

import httpx
import time
from typing import List, Dict, Any

from .config import config


# =============================================================================
# Exceções Personalizadas
# =============================================================================

class APIError(Exception):
    """Erro base da API. Use para capturar qualquer erro da API."""
    pass


class ConnectionError(APIError):
    """
    Erro de conexão com a API.
    
    Causas comuns:
    - API fora do ar
    - URL incorreta
    - Problemas de rede
    """
    pass


class NotFoundError(APIError):
    """
    Recurso não encontrado (HTTP 404).
    
    Use para tratar casos onde o recurso solicitado não existe.
    """
    pass


class ServerError(APIError):
    """
    Erro interno do servidor (HTTP 5xx).
    
    Indica problema no servidor da API, não no cliente.
    """
    pass


class BadRequestError(APIError):
    """
    Requisição inválida (HTTP 400).
    
    Indica que os dados enviados estão incorretos.
    """
    pass


class UnauthorizedError(APIError):
    """
    Não autorizado (HTTP 401).
    
    Indica problema de autenticação.
    """
    pass


# =============================================================================
# Cliente API
# =============================================================================

class APIClient:
    """
    Cliente HTTP para comunicação com a API FastAPI do Hejmai.
    
    Exemplo de uso:
        >>> api = APIClient()
        >>> categorias = api.get_categorias()
        >>> print(categorias)
        ['Açougue', 'Laticínios', 'Mercearia']
    """
    
    def __init__(
        self, 
        base_url: str | None = None, 
        timeout: int | None = None
    ):
        """
        Inicializa o cliente API.
        
        Args:
            base_url: URL base da API (default: config.API_URL)
            timeout: Timeout em segundos (default: config.API_TIMEOUT)
        """
        self.base_url = (base_url or config.API_URL).rstrip('/')
        self.timeout = timeout or config.API_TIMEOUT
    
    def _request_with_retry(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> httpx.Response:
        """
        Faz requisição HTTP com retry exponencial para falhas temporárias.
        
        Args:
            method: Método HTTP (GET, POST, PUT, DELETE, PATCH)
            endpoint: Endpoint da API (ex: '/categorias')
            **kwargs: Argumentos adicionais para httpx.request()
        
        Returns:
            httpx.Response: Resposta da requisição
        
        Raises:
            ConnectionError: Falha ao conectar após todas as tentativas
        """
        last_error: Exception | None = None
        url = f"{self.base_url}{endpoint}"
        
        for tentativa in range(config.MAX_RETRY_TENTATIVAS):
            try:
                response = httpx.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )
                
                # Não faz retry para erros do cliente (4xx)
                if response.status_code < 500:
                    return response
                    
            except httpx.ConnectError as e:
                last_error = e
                # Retry exponencial: 2s, 4s, 6s...
                if tentativa < config.MAX_RETRY_TENTATIVAS - 1:
                    wait_time = (tentativa + 1) * 2
                    time.sleep(wait_time)
                    
        raise ConnectionError(
            f"Falha ao conectar com a API após {config.MAX_RETRY_TENTATIVAS} tentativas. "
            f"Verifique se o servidor está rodando em {self.base_url}"
        ) from last_error
    
    def _handle_response(self, response: httpx.Response) -> httpx.Response:
        """
        Trata a resposta HTTP e levanta exceções apropriadas.
        
        Args:
            response: Resposta HTTP para tratar
        
        Returns:
            httpx.Response: A própria resposta se bem-sucedida
        
        Raises:
            NotFoundError: HTTP 404
            BadRequestError: HTTP 400
            UnauthorizedError: HTTP 401
            ServerError: HTTP 5xx
        """
        status = response.status_code
        
        if status == 404:
            raise NotFoundError(f"Recurso não encontrado: {response.url}")
        elif status == 400:
            raise BadRequestError(f"Requisição inválida: {response.text}")
        elif status == 401:
            raise UnauthorizedError("Não autorizado. Verifique as credenciais.")
        elif status >= 500:
            raise ServerError(f"Erro interno do servidor ({status}): {response.text}")
        
        return response
    
    # ==========================================================================
    # Endpoints - Categorias
    # ==========================================================================
    
    def get_categorias(self) -> List[str]:
        """
        Lista todas as categorias disponíveis.
        
        Returns:
            Lista de nomes de categorias.
            
        Example:
            >>> api.get_categorias()
            ['Açougue', 'Laticínios', 'Hortifruti', 'Mercearia']
        """
        try:
            response = self._request_with_retry("GET", "/categorias")
            response = self._handle_response(response)
            return [cat["nome"] for cat in response.json()]
        except NotFoundError:
            return []
        except ServerError as e:
            raise ServerError(f"Erro ao buscar categorias: {e}")
    
    # ==========================================================================
    # Endpoints - Produtos
    # ==========================================================================
    
    def get_produtos_alertas(self) -> Dict[str, Any]:
        """
        Busca produtos com alertas de estoque (baixo ou vencendo).
        
        Returns:
            Dict com chaves 'estoque_baixo' e 'vencendo_em_breve'.
            
        Example:
            >>> api.get_produtos_alertas()
            {
                'estoque_baixo': [{'id': 1, 'nome': 'Arroz', ...}],
                'vencendo_em_breve': [{'id': 2, 'nome': 'Leite', ...}]
            }
        """
        response = self._request_with_retry("GET", "/produtos/alertas")
        self._handle_response(response)
        return response.json()
    
    def get_produtos_todos(self) -> List[Dict[str, Any]]:
        """
        Lista todos os produtos cadastrados.
        
        Returns:
            Lista de produtos.
        """
        response = self._request_with_retry("GET", "/produtos/todos")
        self._handle_response(response)
        return response.json()
    
    # ==========================================================================
    # Endpoints - Compras
    # ==========================================================================
    
    def post_compra_lote(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registra uma compra com múltiplos itens em lote.
        
        Args:
            dados: Dict com 'local_compra' e 'itens' (lista de itens).
        
        Returns:
            Dict com resultado do registro.
            
        Example:
            >>> api.post_compra_lote({
            ...     'local_compra': 'Mercado Extra',
            ...     'itens': [{'nome': 'Arroz', 'quantidade': 2, ...}]
            ... })
            {'message': 'Compra registrada!', 'itens': 5}
        """
        response = self._request_with_retry(
            "POST", 
            "/compras/registrar-lote",
            json=dados,
            timeout=config.NLP_TIMEOUT * 2  # Compra em lote pode demorar mais
        )
        self._handle_response(response)
        return response.json()
    
    def post_processar_entrada_livre(self, texto: str) -> Dict[str, Any]:
        """
        Processa texto livre com NLP para extrair itens de compra.
        
        Args:
            texto: Texto descritivo da compra.
        
        Returns:
            Dict com itens extraídos e status do processamento.
            
        Example:
            >>> api.post_processar_entrada_livre(
            ...     "Comprei 2kg de carne por R$ 50 no Mercado A"
            ... )
            {
                'status': 'sucesso',
                'dados_processados': {'itens': [...], 'local_compra': 'Mercado A'}
            }
        """
        response = self._request_with_retry(
            "POST",
            "/processar-entrada-livre",
            json={"texto": texto},
            timeout=config.NLP_TIMEOUT
        )
        self._handle_response(response)
        return response.json()
    
    def delete_compra(self, compra_id: int) -> Dict[str, Any]:
        """
        Exclui uma compra (exclusão lógica).
        
        Args:
            compra_id: ID da compra para excluir.
        
        Returns:
            Dict com confirmação da exclusão.
        """
        response = self._request_with_retry("DELETE", f"/compras/{compra_id}")
        self._handle_response(response)
        return response.json()
    
    def patch_compra_restaurar(self, compra_id: int) -> Dict[str, Any]:
        """
        Restaura uma compra que foi excluída logicamente.
        
        Args:
            compra_id: ID da compra para restaurar.
        
        Returns:
            Dict com confirmação da restauração.
        """
        response = self._request_with_retry("PATCH", f"/compras/{compra_id}/restaurar")
        self._handle_response(response)
        return response.json()
    
    def get_compras_excluidas(self) -> List[Dict[str, Any]]:
        """
        Lista todas as compras excluídas logicamente.
        
        Returns:
            Lista de compras excluídas.
        """
        response = self._request_with_retry("GET", "/compras/excluidas")
        self._handle_response(response)
        return response.json()
    
    # ==========================================================================
    # Endpoints - Relatórios
    # ==========================================================================
    
    def get_historico_precos(self, produto_id: int) -> List[Dict[str, Any]]:
        """
        Busca histórico de preços de um produto.
        
        Args:
            produto_id: ID do produto.
        
        Returns:
            Lista de registros de preço com data, preço e local.
        """
        response = self._request_with_retry(
            "GET", 
            f"/relatorios/historico-precos/{produto_id}"
        )
        self._handle_response(response)
        return response.json()
    
    def get_previsao_gastos(self) -> Dict[str, Any]:
        """
        Busca previsão de gastos para reposição de estoque.
        
        Returns:
            Dict com 'valor_total_estimado' e 'itens' para reposição.
        """
        response = self._request_with_retry("GET", "/relatorios/previsao-gastos")
        self._handle_response(response)
        return response.json()
    
    def get_performance_budget(self) -> List[Dict[str, Any]]:
        """
        Busca performance de orçamento por categoria.
        
        Returns:
            Lista de categorias com limite, gasto real e porcentagem.
        """
        response = self._request_with_retry("GET", "/relatorios/performance-budget")
        self._handle_response(response)
        return response.json()
    
    # ==========================================================================
    # Endpoint - Saúde da API
    # ==========================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Verifica se a API está online.
        
        Returns:
            Dict com status da API.
            
        Example:
            >>> api.health_check()
            {'status': 'Agente Online', 'ano': 2026}
        """
        response = self._request_with_retry("GET", "/")
        self._handle_response(response)
        return response.json()
