# Os códigos foram gerados com auxilio de I.A.
from django.apps import AppConfig


class AnunciosConfig(AppConfig):
    """
    O QUE FAZ: Configuração do aplicativo Django apps.anuncios.
    POR QUE FAZ: Registra o domínio comercial de Anúncios e Composições/Kits de Marketplaces.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Particionamento comercial por loja/conta.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.anuncios'
    verbose_name = 'Gestão de Anúncios e Kits de Marketplaces'
