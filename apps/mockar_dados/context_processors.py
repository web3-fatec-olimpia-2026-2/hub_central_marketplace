# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o objetivo do context processor e suas restrições de segurança
"""
O QUE FAZ: Injeta variáveis de credenciais de teste para o template de login quando em modo debug.
POR QUE FAZ: Facilita a autenticação em 1 clique durante o desenvolvimento, mantendo controle estrito via flags .env.
REGRAS DE SEGURANÇA E AMBIENTE:
- Injeta credenciais APENAS se settings.DEBUG e settings.LOGIN_DEBUG forem ambos True.
- Em qualquer outro cenário, retorna login_debug=False e strings vazias.
"""
# Fim do bloco de docstring estrutural

# Importa o módulo settings do Django para verificação das flags de ambiente em tempo de execução
from django.conf import settings

# Importa as funções de resolução dinâmica das credenciais de desenvolvimento
from .conf import get_dev_debug_username, get_dev_debug_password

# Importa as funções para provisionamento do usuário devmaster e consulta do status da flag de simulação de rotas mock
from .services import garantir_usuario_devmaster, is_simular_rotas_mock_ativo


# Declaração da função do context processor que injeta variáveis no contexto de renderização dos templates
def login_debug_context(request):
    # Avalia se o modo DEBUG global do projeto Django está ativado (padrão False se omitido)
    is_debug = getattr(settings, 'DEBUG', False)

    # Avalia se a flag específica LOGIN_DEBUG está ativada nas configurações (padrão False se omitida)
    is_login_debug = getattr(settings, 'LOGIN_DEBUG', False)

    # Condição restritiva de segurança: ambas as flags precisam ser estritamente True
    if is_debug and is_login_debug:
        # Garante a existência e sincronização do usuário devmaster no banco a partir do .env
        # Bloco protegido para assegurar que falhas de banco ou migrações pendentes não quebrem a renderização
        try:
            # Executa o provisionamento ou atualização idempotente do usuário devmaster
            garantir_usuario_devmaster()
        except Exception:
            # Ignora silenciosamente qualquer falha transitória durante o provisionamento
            pass

        # Retorna o dicionário com as credenciais de depuração e estado da simulação mock ativos
        return {
            'login_debug': True,
            'dev_debug_user': get_dev_debug_username(),
            'dev_debug_pass': get_dev_debug_password(),
            'simular_rotas_mock': is_simular_rotas_mock_ativo(request),
        }

    # Caso qualquer uma das flags seja False (ambiente de produção ou debug com login seguro), neutraliza os valores
    return {
        'login_debug': False,
        'dev_debug_user': '',
        'dev_debug_pass': '',
        'simular_rotas_mock': is_simular_rotas_mock_ativo(request),
    }
