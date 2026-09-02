# Os códigos foram gerados com auxilio de I.A.
from django.apps import AppConfig


class TenancyConfig(AppConfig):
    """
    O QUE FAZ: Configuração do aplicativo Django apps.tenancy.
    POR QUE FAZ: Registra o domínio de Tenancy, Identidade e Módulos do Sistema no ecossistema Django.
    PERMISSÕES RBAC: Nível de infraestrutura / framework.
    MULTI-TENANCY: Ponto de inicialização do suporte multi-tenant.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenancy'
    verbose_name = 'Gestão de Tenants e Identidade'
