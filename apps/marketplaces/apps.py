# Os códigos foram gerados com auxilio de I.A.

# Importa a classe AppConfig do Django, utilizada para configurar metadados e ciclo de vida da aplicação instalada
from django.apps import AppConfig


# Declara a classe de configuração específica do módulo marketplaces herdando de AppConfig
class MarketplacesConfig(AppConfig):
    # Início do bloco de docstring que documenta o propósito, escopo de RBAC e multi-tenancy do módulo
    """
    O QUE FAZ: Configuração do aplicativo Django apps.marketplaces.
    POR QUE FAZ: Registra o Hub Multicanal, conectores de API e modelos de auditoria no ecossistema Django.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Registro dos conectores de canal por loja.
    """
    # Fim do bloco de documentação estrutural do aplicativo

    # Configura o tipo padrão de chave primária para os modelos do app como inteiro auto-incremental de 64 bits (BigAutoField)
    default_auto_field = 'django.db.models.BigAutoField'

    # Especifica o caminho completo do pacote Python para que o Django localize e inicialize a aplicação corretamente
    name = 'apps.marketplaces'

    # Define o nome amigável e legível exibido para este módulo nas interfaces do Django Admin
    verbose_name = 'Hub de Integração e Conectores de Marketplaces'
