# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Configuração do aplicativo mockar_dados com rotina de inicialização segura.
POR QUE FAZ: Garante o provisionamento automático do usuário devmaster apenas em ambiente de desenvolvimento quando DEBUG e LOGIN_DEBUG estiverem ativos.
REGRAS DE SEGURANÇA E AMBIENTE:
- A rotina de inicialização é estritamente condicionada a settings.DEBUG=True e settings.LOGIN_DEBUG=True.
- Não afeta ambientes de produção.
"""
from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def provisionar_devmaster_hook(sender, **kwargs):
    """
    Hook executado após migrações para assegurar que o usuário devmaster exista quando em modo debug.
    """
    try:
        from .services import garantir_usuario_devmaster
        garantir_usuario_devmaster()
    except Exception:
        # Em fases iniciais de migração ou build, ignora graciosamente
        pass


class MockarDadosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mockar_dados'
    verbose_name = 'Mockar Dados (Debug & Testes)'

    def ready(self):
        post_migrate.connect(provisionar_devmaster_hook, sender=self)
