# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o objetivo do módulo e as diretrizes de segurança de ambiente
"""
O QUE FAZ: Resolve dinamicamente as credenciais de desenvolvimento do superusuário DEV mestre a partir do .env / settings.
POR QUE FAZ: Elimina credenciais hardcoded no código-fonte, garantindo segurança e flexibilidade configurada via .env.
REGRAS DE SEGURANÇA E AMBIENTE:
- Estas credenciais são estritamente para uso em desenvolvimento local (DEBUG=True e LOGIN_DEBUG=True).
- O aplicativo mockar_dados e estas credenciais não devem ser utilizados em ambiente de produção.
"""
# Fim do bloco de docstring descritivo do módulo

# Importa o módulo os para permitir a leitura direta de variáveis de ambiente do sistema operacional
import os

# Importa o módulo settings do Django para acessar configurações da aplicação
from django.conf import settings


# Função para obter dinamicamente o nome de usuário do superusuário de desenvolvimento
def get_dev_debug_username() -> str:
    # Docstring explicativa indicando a ordem de precedência e o valor padrão adotado
    """Retorna o nome de usuário DEV definido nas configurações ou .env (padrão: 'devmaster')."""
    # Consulta settings.LOGIN_DEBUG_USERNAME; se ausente, recorre a os.getenv com fallback para 'devmaster'
    return getattr(settings, 'LOGIN_DEBUG_USERNAME', None) or os.getenv('LOGIN_DEBUG_USERNAME', 'devmaster')


# Função para obter dinamicamente a senha do usuário de desenvolvimento
def get_dev_debug_password() -> str:
    # Docstring explicativa da função
    """Retorna a senha DEV definida nas configurações ou .env."""
    # Consulta settings.LOGIN_DEBUG_PASSWORD; se ausente, busca a variável de ambiente correspondente ou string vazia
    return getattr(settings, 'LOGIN_DEBUG_PASSWORD', None) or os.getenv('LOGIN_DEBUG_PASSWORD', '')


# Função para obter dinamicamente o e-mail do usuário de desenvolvimento
def get_dev_debug_email() -> str:
    # Docstring explicativa da função
    """Retorna o e-mail DEV definido nas configurações ou .env."""
    # Obtém o username resolvido para compor o e-mail de fallback padrão
    username = get_dev_debug_username()
    # Consulta settings.LOGIN_DEBUG_EMAIL; se ausente, busca no ambiente ou compõe '<username>@hub.local'
    return getattr(settings, 'LOGIN_DEBUG_EMAIL', None) or os.getenv('LOGIN_DEBUG_EMAIL', f'{username}@hub.local')


# Gancho a nível de módulo (PEP 562) para interceptar acessos a atributos que não existem explicitamente no arquivo
def __getattr__(name: str):
    # Início do bloco de docstring documentando retrocompatibilidade e tolerância a override_settings em suítes de teste
    """
    Permite resolução dinâmica de variáveis para retrocompatibilidade sem valores estáticos hardcoded.
    Garante que @override_settings em testes reflita imediatamente o novo valor.
    """
    # Fim da docstring explicativa

    # Mapeia aliases legados de username para a função dinâmica correspondente
    if name in ('DEV_HARDCODED_USER', 'DEV_DEBUG_USER', 'DEV_DEBUG_USERNAME'):
        return get_dev_debug_username()
    # Mapeia aliases legados de senha para a função dinâmica correspondente
    if name in ('DEV_HARDCODED_PASS', 'DEV_DEBUG_PASS', 'DEV_DEBUG_PASSWORD'):
        return get_dev_debug_password()
    # Mapeia aliases legados de e-mail para a função dinâmica correspondente
    if name in ('DEV_HARDCODED_EMAIL', 'DEV_DEBUG_EMAIL'):
        return get_dev_debug_email()
    # Lança exceção de atributo inexistente caso o identificador consultado não faça parte do mapeamento dinâmico
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
