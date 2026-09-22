# Os códigos foram gerados com auxilio de I.A.

# Importa a classe base AppConfig do módulo de aplicações do Django para configuração e registro do app
from django.apps import AppConfig


# Declaração da classe de configuração do aplicativo apps.tenancy herdando de AppConfig
class TenancyConfig(AppConfig):
    # Início do bloco de docstring que documenta o objetivo, justificativa arquitetural, permissões e papel no multi-tenancy
    """
    O QUE FAZ: Configuração do aplicativo Django apps.tenancy.
    POR QUE FAZ: Registra o domínio de Tenancy, Identidade e Módulos do Sistema no ecossistema Django.
    PERMISSÕES RBAC: Nível de infraestrutura / framework.
    MULTI-TENANCY: Ponto de inicialização do suporte multi-tenant.
    """
    # Fim do bloco de docstring estrutural

    # Define o tipo padrão para chaves primárias autoincrementais como BigAutoField (inteiro de 64 bits)
    default_auto_field = 'django.db.models.BigAutoField'

    # Caminho Python completo do pacote da aplicação conforme registrado no INSTALLED_APPS
    name = 'apps.tenancy'

    # Nome descritivo legível exibido no Django Admin, painéis do sistema e logs de inicialização
    verbose_name = 'Gestão de Tenants e Identidade'
