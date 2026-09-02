# Os códigos foram gerados com auxilio de I.A.
from django.apps import AppConfig


class MarketplacesConfig(AppConfig):
    """
    O QUE FAZ: Configuração do aplicativo Django apps.marketplaces.
    POR QUE FAZ: Registra o Hub Multicanal, conectores de API e modelos de auditoria no ecossistema Django.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Registro dos conectores de canal por loja.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketplaces'
    verbose_name = 'Hub de Integração e Conectores de Marketplaces'
