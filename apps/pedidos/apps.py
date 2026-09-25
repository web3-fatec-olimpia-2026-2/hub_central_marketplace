# Os códigos foram gerados com auxilio de I.A.

# Importa a classe AppConfig do framework Django, utilizada para configurar propriedades e metadados da aplicação
from django.apps import AppConfig


# Declaração da classe de configuração do aplicativo apps.pedidos herdando de AppConfig
class PedidosConfig(AppConfig):
    # Início do bloco de docstring que contextualiza as responsabilidades arquiteturais, RBAC e multi-tenancy do módulo
    """
    O QUE FAZ: Configuração do aplicativo Django apps.pedidos.
    POR QUE FAZ: Registra o domínio de Vendas, Webhooks assíncronos e Baixa Atômica Concorrente de Estoque.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Processamento de pedidos isolado por loja.
    """
    # Fim do bloco descritivo da classe

    # Define o tipo padrão para chaves primárias autoincrementais como BigAutoField (inteiro de 64 bits)
    default_auto_field = 'django.db.models.BigAutoField'

    # Caminho Python completo do pacote da aplicação registrado no INSTALLED_APPS
    name = 'apps.pedidos'

    # Nome descritivo legível por humanos exibido no Django Admin, painéis do sistema e logs de inicialização
    verbose_name = 'Vendas, Webhooks e Pedidos Multicanal'