# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta os objetivos do aplicativo e as diretrizes de segurança de ambiente
"""
O QUE FAZ: Configuração do aplicativo mockar_dados com rotina de inicialização segura.
POR QUE FAZ: Garante o provisionamento automático do usuário devmaster apenas em ambiente de desenvolvimento quando DEBUG e LOGIN_DEBUG estiverem ativos.
REGRAS DE SEGURANÇA E AMBIENTE:
- A rotina de inicialização é estritamente condicionada a settings.DEBUG=True e settings.LOGIN_DEBUG=True.
- Não afeta ambientes de produção.
"""
# Fim do bloco de docstring estrutural

# Importa a classe base AppConfig do Django para configuração e ciclo de vida do aplicativo
from django.apps import AppConfig

# Importa o módulo settings para inspeção de flags e parâmetros de ambiente
from django.conf import settings

# Importa o sinal post_migrate, acionado imediatamente após a conclusão das migrações de banco de dados
from django.db.models.signals import post_migrate


# Declaração da função receptora do sinal (hook) responsável por provisionar o usuário administrador padrão de desenvolvimento
def provisionar_devmaster_hook(sender, **kwargs):
    # Início do bloco de docstring da função de hook
    """
    Hook executado após migrações para assegurar que o usuário devmaster exista quando em modo debug.
    """
    # Fim da docstring explicativa

    # Bloco protegido para evitar que falhas de importação ou tabelas ausentes interrompam o processo de migração
    try:
        # Importação tardia do serviço para evitar importações circulares durante o carregamento inicial de apps
        from .services import garantir_usuario_devmaster
        # Executa o provisionamento idempotente do usuário desenvolvedor
        garantir_usuario_devmaster()
    # Captura exceções genéricas durante builds parciais ou etapas iniciais de migração
    except Exception:
        # Em fases iniciais de migração ou build, ignora graciosamente
        pass


# Declaração da classe de configuração do aplicativo herdando de AppConfig
class MockarDadosConfig(AppConfig):
    # Define o tipo padrão de chave primária automática como inteiros de 64 bits (BigAutoField)
    default_auto_field = 'django.db.models.BigAutoField'

    # Caminho Python completo do pacote do aplicativo
    name = 'apps.mockar_dados'

    # Nome descritivo legível exibido no painel de administração e logs do Django
    verbose_name = 'Mockar Dados (Debug & Testes)'

    # Método de ciclo de vida executado quando o registro de aplicativos do Django está totalmente pronto
    def ready(self):
        # Conecta o hook provisionar_devmaster_hook ao sinal post_migrate, restringindo o disparo apenas a este aplicativo (sender=self)
        post_migrate.connect(provisionar_devmaster_hook, sender=self)