# Os códigos foram gerados com auxilio de I.A.

# Importa a classe AppConfig do Django, utilizada para configurar metadados e ciclo de vida da aplicação instalada
from django.apps import AppConfig


# Declara a classe de configuração exclusiva do módulo financeiro herdando das definições de AppConfig
class FinanceiroConfig(AppConfig):
    # Início do bloco de docstring que contextualiza a responsabilidade comercial, escopo RBAC e multi-tenancy do módulo
    """
    O QUE FAZ: Configuração do aplicativo Django apps.financeiro.
    POR QUE FAZ: Registra o Motor de Inteligência Financeira, Simulador Promocional e parâmetros tributários por loja.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Parametrização financeira por loja.
    """
    # Fim do bloco de documentação estrutural do aplicativo

    # Configura o tipo padrão de chave primária para os modelos do app como inteiro auto-incremental de 64 bits (BigAutoField)
    default_auto_field = 'django.db.models.BigAutoField'

    # Define o caminho completo do pacote Python para que o Django registre e localize a aplicação no ecossistema
    name = 'apps.financeiro'

    # Especifica o nome amigável e legível exibido para este aplicativo no painel do Django Admin
    verbose_name = 'Motor de Inteligência Financeira e Promoções'