# Os códigos foram gerados com auxilio de I.A.

# Importa a classe AppConfig do framework Django, utilizada para configurar propriedades e metadados de aplicativos registrados
from django.apps import AppConfig


# Declara a classe de configuração exclusiva do módulo de catálogo herdando das definições de AppConfig
class CatalogoConfig(AppConfig):
    # Início do bloco de docstring que contextualiza a responsabilidade comercial, RBAC e isolamento multi-tenant do app
    """
    O QUE FAZ: Configuração do aplicativo Django apps.catalogo.
    POR QUE FAZ: Registra o domínio de Produtos, Categorias, Anúncios Multicanal e Histórico de Preços.
    PERMISSÕES RBAC: Infraestrutura / Framework.
    MULTI-TENANCY: Particionamento de catálogo por loja.
    """
    # Fim do bloco de documentação estrutural do aplicativo

    # Configura o gerador de chave primária padrão para usar inteiros de 64 bits auto-incrementais (BigAutoField) nos modelos deste app
    default_auto_field = 'django.db.models.BigAutoField'

    # Especifica o caminho completo do módulo Python para que o Django localize e inicialize o pacote corretamente
    name = 'apps.catalogo'

    # Define o nome amigável e legível exibido para este módulo no cabeçalho das seções do Django Admin
    verbose_name = 'Gestão de Catálogo e Produtos'
