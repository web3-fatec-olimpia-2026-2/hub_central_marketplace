# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Injeta variáveis de credenciais de teste para o template de login quando em modo debug.
POR QUE FAZ: Facilita a autenticação em 1 clique durante o desenvolvimento, mantendo controle estrito via flags .env.
REGRAS DE SEGURANÇA E AMBIENTE:
- Injeta credenciais APENAS se settings.DEBUG e settings.LOGIN_DEBUG forem ambos True.
- Em qualquer outro cenário, retorna login_debug=False e strings vazias.
"""
from django.conf import settings
from .conf import DEV_HARDCODED_USER, DEV_HARDCODED_PASS, DEV_HARDCODED_EMAIL


def login_debug_context(request):
    is_debug = getattr(settings, 'DEBUG', False)
    is_login_debug = getattr(settings, 'LOGIN_DEBUG', False)

    if is_debug and is_login_debug:
        # Garante a existência do usuário devmaster no banco caso ainda não tenha sido criado
        try:
            from django.contrib.auth.models import User
            from apps.tenancy.models import PerfilUsuario
            from apps.tenancy.enums import PapelUsuarioEnum

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
            pass

        return {
            'login_debug': True,
            'dev_debug_user': DEV_HARDCODED_USER,
            'dev_debug_pass': DEV_HARDCODED_PASS,
        }
    return {
        'login_debug': False,
        'dev_debug_user': '',
        'dev_debug_pass': '',
    }
