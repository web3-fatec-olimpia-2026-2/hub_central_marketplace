# Os códigos foram gerados com auxilio de I.A.
import abc
from decimal import Decimal
from typing import Tuple, Dict, Any, List, Optional

from apps.marketplaces.models import ContaMarketplace, LogSincronizacao


class BaseMarketplaceConnector(abc.ABC):
    """
    O QUE FAZ: Contrato abstrato (Strategy Pattern) que define os métodos padronizados de integração para qualquer marketplace.
    POR QUE FAZ: Garante o desacoplamento arquitetural, permitindo adicionar novos canais (Shopee, Magalu, Amazon) sem alterar a lógica de negócio central ou as views da aplicação.
    PERMISSÕES RBAC: Utilizado internamente por serviços e disparado por DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Cada instância do conector é parametrizada com uma ContaMarketplace associada a um tenant (Loja) específico.
    """

    def __init__(self, conta: Optional[ContaMarketplace] = None):
        """
        Inicializa o conector vinculado a uma ContaMarketplace específica da Loja.
        """
        self.conta = conta

    @property
    @abc.abstractmethod
    def canal_nome(self) -> str:
        """Retorna o identificador textual do canal (ex: 'mercadolivre', 'shopee')."""
        pass

    @abc.abstractmethod
    def autenticar(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        O QUE FAZ: Valida credenciais ou testa conectividade com a API externa (ex: GET /users/me).
        POR QUE FAZ: Confirma se a conta está ativa e autorizada antes de sincronizar dados.
        RETORNO: (sucesso: bool, mensagem: str, dados_resposta: dict)
        """
        pass

    @abc.abstractmethod
    def atualizar_preco(
        self, item_id_externo: str, novo_preco: Decimal, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """
        O QUE FAZ: Sincroniza o preço de venda unitário de um anúncio no marketplace externo.
        POR QUE FAZ: Garante que o marketplace reflita a precificação atualizada no Hub (Fonte Única da Verdade / RF-05).
        RETORNO: (sucesso: bool, mensagem: str, log: LogSincronizacao)
        """
        pass

    @abc.abstractmethod
    def atualizar_estoque(
        self, item_id_externo: str, novo_estoque: int, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """
        O QUE FAZ: Sincroniza a quantidade de saldo de inventário disponível no anúncio externo.
        POR QUE FAZ: Aplica clamping obrigatório max(0, estoque) para prevenir falhas de API por saldo negativo (RN-05 / RN-06).
        RETORNO: (sucesso: bool, mensagem: str, log: LogSincronizacao)
        """
        pass

    @abc.abstractmethod
    def publicar_anuncio(
        self, dados_anuncio: Dict[str, Any], usuario=None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        O QUE FAZ: Cria e publica um novo anúncio no marketplace a partir dos dados do produto no Hub (RF-04).
        POR QUE FAZ: Automatiza o onboarding de produtos em múltiplos canais.
        RETORNO: (sucesso: bool, mensagem: str, dados_anuncio_criado: dict)
        """
        pass

    @abc.abstractmethod
    def buscar_pedidos(
        self, data_inicio=None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        O QUE FAZ: Consulta e recupera lista de pedidos recentes na API do marketplace para conciliação ou polling.
        POR QUE FAZ: Complementa o fluxo de webhooks assíncronos de vendas (RF-06).
        RETORNO: (sucesso: bool, mensagem: str, pedidos: list[dict])
        """
        pass
