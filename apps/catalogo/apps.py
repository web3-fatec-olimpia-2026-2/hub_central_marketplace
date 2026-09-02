# Os códigos foram gerados com auxilio de I.A.
from django.apps import AppConfig


class CatalogoConfig(AppConfig):
    """
    O QUE FAZ: Configuração do aplicativo Django apps.catalogo.
    POR QUE FAZ: Registra o domínio de Produtos, Categorias, Anúncios Multicanal e Histórico de Preços.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Particionamento de catálogo por loja.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.catalogo'
    verbose_name = 'Gestão de Catálogo e Produtos'
