# apps/mockar_dados/conf.py
# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Resolve dinamicamente as credenciais de desenvolvimento do superusuário DEV mestre a partir do .env / settings.
POR QUE FAZ: Elimina credenciais hardcoded no código-fonte, garantindo segurança e flexibilidade configurada via .env.
REGRAS DE SEGURANÇA E AMBIENTE:
- Estas credenciais são estritamente para uso em desenvolvimento local (DEBUG=True e LOGIN_DEBUG=True).
- O aplicativo mockar_dados e estas credenciais não devem ser utilizados em ambiente de produção.
"""
import os
from django.conf import settings


def get_dev_debug_username() -> str:
    """Retorna o nome de usuário DEV definido nas configurações ou .env (padrão: 'devmaster')."""
    return getattr(settings, 'LOGIN_DEBUG_USERNAME', None) or os.getenv('LOGIN_DEBUG_USERNAME', 'devmaster')


def get_dev_debug_password() -> str:
    """Retorna a senha DEV definida nas configurações ou .env."""
    return getattr(settings, 'LOGIN_DEBUG_PASSWORD', None) or os.getenv('LOGIN_DEBUG_PASSWORD', '')


def get_dev_debug_email() -> str:
    """Retorna o e-mail DEV definido nas configurações ou .env."""
    username = get_dev_debug_username()
    return getattr(settings, 'LOGIN_DEBUG_EMAIL', None) or os.getenv('LOGIN_DEBUG_EMAIL', f'{username}@hub.local')


def __getattr__(name: str):
    """
    Permite resolução dinâmica de variáveis para retrocompatibilidade sem valores estáticos hardcoded.
    Garante que @override_settings em testes reflita imediatamente o novo valor.
    """
    if name in ('DEV_HARDCODED_USER', 'DEV_DEBUG_USER', 'DEV_DEBUG_USERNAME'):
        return get_dev_debug_username()
    if name in ('DEV_HARDCODED_PASS', 'DEV_DEBUG_PASS', 'DEV_DEBUG_PASSWORD'):
        return get_dev_debug_password()
    if name in ('DEV_HARDCODED_EMAIL', 'DEV_DEBUG_EMAIL'):
        return get_dev_debug_email()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
