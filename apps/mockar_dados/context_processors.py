# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Injeta variáveis de credenciais de teste para o template de login quando em modo debug.
POR QUE FAZ: Facilita a autenticação em 1 clique durante o desenvolvimento, mantendo controle estrito via flags .env.
REGRAS DE SEGURANÇA E AMBIENTE:
- Injeta credenciais APENAS se settings.DEBUG e settings.LOGIN_DEBUG forem ambos True.
- Em qualquer outro cenário, retorna login_debug=False e strings vazias.
"""
from django.conf import settings
from .conf import get_dev_debug_username, get_dev_debug_password
from .services import garantir_usuario_devmaster, is_simular_rotas_mock_ativo


def login_debug_context(request):
    is_debug = getattr(settings, 'DEBUG', False)
    is_login_debug = getattr(settings, 'LOGIN_DEBUG', False)

    if is_debug and is_login_debug:
        # Garante a existência e sincronização do usuário devmaster no banco a partir do .env
        try:
            garantir_usuario_devmaster()
        except Exception:
            pass

        return {
            'login_debug': True,
            'dev_debug_user': get_dev_debug_username(),
            'dev_debug_pass': get_dev_debug_password(),
            'simular_rotas_mock': is_simular_rotas_mock_ativo(request),
        }

    return {
        'login_debug': False,
        'dev_debug_user': '',
        'dev_debug_pass': '',
        'simular_rotas_mock': is_simular_rotas_mock_ativo(request),
    }
