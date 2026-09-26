# Os códigos foram gerados com auxilio de I.A.

# Importa a classe base AppConfig do Django, utilizada para configurar e inicializar aplicações instaladas
from django.apps import AppConfig


# Define a classe de configuração específica do módulo de anúncios, herdando de AppConfig
class AnunciosConfig(AppConfig):
    # Início do bloco de docstring que documenta o propósito, escopo de segurança e multi-tenancy do módulo
    """
    O QUE FAZ: Configuração do aplicativo Django apps.anuncios.
    POR QUE FAZ: Registra o domínio comercial de Anúncios e Composições/Kits de Marketplaces.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Particionamento comercial por loja/conta.
    """
    # Fim do bloco de documentação arquitetural do módulo

    # Define o tipo de campo primário automático padrão para os modelos deste app como inteiros de 64 bits (BigAutoField)
    default_auto_field = 'django.db.models.BigAutoField'

    # Especifica o caminho completo do módulo Python para que o Django localize o app no ecossistema de pastas
    name = 'apps.anuncios'

    # Define o nome amigável e legível exibido no painel de administração (Django Admin) para este aplicativo
    verbose_name = 'Gestão de Anúncios e Kits de Marketplaces'

    # Método de ciclo de vida executado automaticamente pelo Django assim que todas as aplicações forem carregadas no registro
    def ready(self):
        # Importa o módulo de sinais (signals) para registrar ouvintes e gatilhos de eventos sem gerar avisos de importação não utilizada (# noqa)
        import apps.anuncios.signals  # noqa
