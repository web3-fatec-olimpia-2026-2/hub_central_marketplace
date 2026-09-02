# apps/mockar_dados/conf.py
# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Define as credenciais estáticas de desenvolvimento do superusuário DEV mestre.
POR QUE FAZ: Centraliza o acesso de teste do ambiente local/debug para injeção automática e provisionamento.
REGRAS DE SEGURANÇA E AMBIENTE:
- Estas credenciais são estritamente para uso em desenvolvimento local (DEBUG=True e LOGIN_DEBUG=True).
- O aplicativo mockar_dados e estas credenciais não devem ser utilizados em ambiente de produção.
"""

DEV_HARDCODED_USER = "devmaster"
DEV_HARDCODED_PASS = "adgorvhub"
DEV_HARDCODED_EMAIL = "devmaster@hub.local"
