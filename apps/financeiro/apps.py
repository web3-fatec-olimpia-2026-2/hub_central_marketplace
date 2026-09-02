# Os códigos foram gerados com auxilio de I.A.
from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    """
    O QUE FAZ: Configuração do aplicativo Django apps.financeiro.
    POR QUE FAZ: Registra o Motor de Inteligência Financeira, Simulador Promocional e parâmetros tributários por loja.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Parametrização financeira por loja.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.financeiro'
    verbose_name = 'Motor de Inteligência Financeira e Promoções'
