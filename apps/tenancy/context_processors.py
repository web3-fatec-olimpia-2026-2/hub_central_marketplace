# Os códigos foram gerados com auxilio de I.A.
from .enums import ModuloSistemaEnum, PapelUsuarioEnum
from .permissions import usuario_is_dev


def modulos_loja_context(request):
    """
    O QUE FAZ: Context Processor global que injeta no contexto de todos os templates as flags de módulos ativos, identificação de DEV e dados da loja do usuário.
    POR QUE FAZ: Permite que o template mestre (base.html) renderize links de navegação condicionalmente de acordo com as permissões e módulos habilitados para o tenant do usuário.
    PERMISSÕES RBAC:
      - DEV: Recebe todos os módulos com status True (bypass de visibilidade).
      - ADMIN, SUPERVISOR, USUARIO: Recebe o status real das feature flags configuradas para a sua Loja vinculada.
      - Não autenticado: Recebe dicionário com todos os módulos desativados.
    MULTI-TENANCY: Garante que os menus reflitam exclusivamente o estado das contratações do tenant logado.
    """
    if not request.user.is_authenticated:
        return {
            'is_dev': False,
            'loja_atual': None,
            'modulos_ativos': {modulo: False for modulo in ModuloSistemaEnum.values},
        }

    is_dev = usuario_is_dev(request.user)
    perfil = getattr(request.user, 'perfil', None)
    loja = perfil.loja if perfil else None

    # DEV tem visão e bypass irrestrito de todos os módulos
    if is_dev:
        return {
            'is_dev': True,
            'loja_atual': loja,
            'modulos_ativos': {modulo: True for modulo in ModuloSistemaEnum.values},
        }

    if not loja or not loja.ativo:
        return {
            'is_dev': False,
            'loja_atual': loja,
            'modulos_ativos': {modulo: False for modulo in ModuloSistemaEnum.values},
        }

    # Consulta os módulos ativos da Loja do usuário
    modulos_qs = loja.modulos.filter(ativo=True).values_list('modulo', flat=True)
    modulos_ativos_set = set(modulos_qs)

    modulos_dict = {
        modulo: (modulo in modulos_ativos_set)
        for modulo in ModuloSistemaEnum.values
    }

    return {
        'is_dev': False,
        'loja_atual': loja,
        'modulos_ativos': modulos_dict,
    }
