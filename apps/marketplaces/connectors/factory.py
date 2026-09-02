# Os códigos foram gerados com auxilio de I.A.
from typing import Optional
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import CanalMarketplaceEnum
from .base import BaseMarketplaceConnector
from .mercadolivre import MercadoLivreConnector
from .shopee import ShopeeConnector
from .magalu import MagaluConnector
from .amazon import AmazonConnector


CONNECTOR_REGISTRY = {
    CanalMarketplaceEnum.MERCADOLIVRE: MercadoLivreConnector,
    CanalMarketplaceEnum.SHOPEE: ShopeeConnector,
    CanalMarketplaceEnum.MAGALU: MagaluConnector,
    CanalMarketplaceEnum.AMAZON: AmazonConnector,
}


def get_connector_for_conta(conta: ContaMarketplace) -> BaseMarketplaceConnector:
    """
    O QUE FAZ: Instancia e retorna o conector adequado para a ContaMarketplace informada (Factory Pattern).
    POR QUE FAZ: Centraliza a resolução do conector correto sem espalhar condicionais de canal no código.
    PERMISSÕES RBAC: Infraestrutura / Serviços.
    MULTI-TENANCY: O conector retornado fica vinculado aos dados e credenciais da conta do tenant.
    """
    connector_cls = CONNECTOR_REGISTRY.get(conta.canal, MercadoLivreConnector)
    return connector_cls(conta=conta)


def get_connector_for_canal(canal: str, conta: Optional[ContaMarketplace] = None) -> BaseMarketplaceConnector:
    """
    O QUE FAZ: Instancia e retorna o conector com base na chave do canal.
    """
    connector_cls = CONNECTOR_REGISTRY.get(canal, MercadoLivreConnector)
    return connector_cls(conta=conta)
