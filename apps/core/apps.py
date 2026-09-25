# Os códigos foram gerados com auxilio de I.A.

# Importa a classe AppConfig do Django, utilizada para configurar propriedades e metadados da aplicação instalada
from django.apps import AppConfig


# Declara a classe de configuração específica do módulo core, herdando de AppConfig
class CoreConfig(AppConfig):
    # Define o tipo de campo de chave primária padrão para os modelos do app como inteiro auto-incremental de 64 bits (BigAutoField)
    default_auto_field = 'django.db.models.BigAutoField'

    # Especifica o caminho completo do pacote Python para que o Django localize o aplicativo no sistema
    name = 'apps.core'

    # Define o nome amigável e legível exibido para este módulo nas interfaces administrativas do sistema
    verbose_name = 'Módulo Core e Governança'
