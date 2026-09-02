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
    if getattr(settings, 'DEBUG', False) and getattr(settings, 'LOGIN_DEBUG', False):
        try:
            from django.contrib.auth.models import User
            from apps.tenancy.models import PerfilUsuario
            from apps.tenancy.enums import PapelUsuarioEnum
            from .conf import DEV_HARDCODED_USER, DEV_HARDCODED_PASS, DEV_HARDCODED_EMAIL

            user, created = User.objects.get_or_create(
                username=DEV_HARDCODED_USER,
                defaults={
                    'email': DEV_HARDCODED_EMAIL,
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                }
            )
            if created or not user.check_password(DEV_HARDCODED_PASS):
                user.set_password(DEV_HARDCODED_PASS)
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save()

            perfil, _ = PerfilUsuario.objects.get_or_create(
                usuario=user,
                defaults={
                    'papel': PapelUsuarioEnum.DEV,
                    'loja': None,
                }
            )
            if perfil.papel != PapelUsuarioEnum.DEV or perfil.loja is not None:
                perfil.papel = PapelUsuarioEnum.DEV
                perfil.loja = None
                perfil.save()
        except Exception:
            # Em fases iniciais de migração ou build, ignora graciosamente
            pass


class MockarDadosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mockar_dados'
    verbose_name = 'Mockar Dados (Debug & Testes)'

    def ready(self):
        post_migrate.connect(provisionar_devmaster_hook, sender=self)
