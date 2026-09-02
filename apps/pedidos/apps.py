# Os códigos foram gerados com auxilio de I.A.
from django.apps import AppConfig


class PedidosConfig(AppConfig):
    """
    O QUE FAZ: Configuração do aplicativo Django apps.pedidos.
    POR QUE FAZ: Registra o domínio de Vendas, Webhooks assíncronos e Baixa Atômica Concorrente de Estoque.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Processamento de pedidos isolado por loja.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pedidos'
    verbose_name = 'Vendas, Webhooks e Pedidos Multicanal'
