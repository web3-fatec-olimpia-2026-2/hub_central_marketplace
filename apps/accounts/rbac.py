# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Módulo de RBAC com registro das 4 funcionalidades reservadas do ecossistema e guards de autorização (Doc ① §17.4 e §17.5).
POR QUE FAZ: Padroniza os papéis hierárquicos e o controle de acesso baseado em funcionalidades com a matriz canônica.
PERMISSÕES RBAC:
  - accounts.matriz: ver e editar matriz RBAC (Grupos 3 e 4, não delegável).
  - accounts.atribuir_perfis: atribuir perfis com regras de elevação (Grupos 3 e 4, não delegável).
  - site.tema_editar: configurar tema visual (Grupos 3 e 4, delegável).
  - site.visibilidade_publica: alternar visibilidade pública de páginas (Grupos 3 e 4, delegável).
MULTI-TENANCY: Aplicável com escopo global (DEV/Grupo 4) ou de tenant (ADMIN/Grupo 3).
"""

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin

# Chaves das Funcionalidades Reservadas do Ecossistema (Doc ① §17.5)
FUNC_ACCOUNTS_MATRIZ = 'accounts.matriz'
FUNC_ACCOUNTS_ATRIBUIR_PERFIS = 'accounts.atribuir_perfis'
FUNC_SITE_TEMA_EDITAR = 'site.tema_editar'
FUNC_SITE_VISIBILIDADE_PUBLICA = 'site.visibilidade_publica'

# Catálogo oficial das permissões reservadas
FUNCIONALIDADES_RESERVADAS = {
    FUNC_ACCOUNTS_MATRIZ: {
        'nome': 'Ver e editar a matriz RBAC',
        'padrao_grupos': [3, 4],  # Administrador e Desenvolvedor
        'delegavel': False,
    },
    FUNC_ACCOUNTS_ATRIBUIR_PERFIS: {
        'nome': 'Atribuir perfis hierárquicos',
        'padrao_grupos': [3, 4],
        'delegavel': False,
    },
    FUNC_SITE_TEMA_EDITAR: {
        'nome': 'Alterar o tema do sistema',
        'padrao_grupos': [3, 4],
        'delegavel': True,
    },
    FUNC_SITE_VISIBILIDADE_PUBLICA: {
        'nome': 'Ativar/desativar as páginas públicas',
        'padrao_grupos': [3, 4],
        'delegavel': True,
    },
}

# Mapeamento dos papéis existentes no sistema para os números de grupos canônicos (Doc ① §17.4)
# Grupo 4: Desenvolvedor (DEV)
# Grupo 3: Administrador (ADMIN)
# Grupo 1: Supervisor (SUPERVISOR)
# Grupo 0: Usuário Padrão (USUARIO)
PAPEL_PARA_GRUPO = {
    'DEV': 4,
    'ADMIN': 3,
    'SUPERVISOR': 1,
    'USUARIO': 0,
}


def get_grupo_usuario(user) -> int:
    """Retorna o nível de grupo numérico do usuário (0 a 4) conforme Doc ① §17.4."""
    if not user or not user.is_authenticated:
        return -1
    if user.is_superuser:
        return 4
    perfil = getattr(user, 'perfil', None)
    if perfil:
        papel = getattr(perfil, 'papel', None)
        return PAPEL_PARA_GRUPO.get(papel, 0)
    return 0


def tem_funcionalidade(user, codigo_funcionalidade: str) -> bool:
    """
    O QUE FAZ: Avalia se o usuário possui acesso à funcionalidade solicitada.
    POR QUE FAZ: Fonte única para checagem no backend, visibilidade de menus e templates (Doc ① §17.4 e §17.5).
    """
    if not user or not user.is_authenticated:
        return False

    # Superusuários nativos e perfil DEV (Grupo 4) possuem acesso total
    if user.is_superuser:
        return True

    grupo = get_grupo_usuario(user)
    if grupo == 4:
        return True

    # Validação para as funcionalidades reservadas do ecossistema
    if codigo_funcionalidade in FUNCIONALIDADES_RESERVADAS:
        meta = FUNCIONALIDADES_RESERVADAS[codigo_funcionalidade]
        # Por padrão, grupos 3 e 4 têm permissão
        if grupo in meta['padrao_grupos']:
            return True
        return False

    # Outras funcionalidades operacionais da loja
    return False


class RBACFuncionalidadeRequiredMixin(AccessMixin):
    """Mixin para CBVs que exige determinada funcionalidade do RBAC."""
    funcionalidade_requerida = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.funcionalidade_requerida and not tem_funcionalidade(request.user, self.funcionalidade_requerida):
            raise PermissionDenied(f"Acesso negado: funcionalidade '{self.funcionalidade_requerida}' necessária.")

        return super().dispatch(request, *args, **kwargs)


def require_funcionalidade(codigo_funcionalidade: str):
    """Decorador de função para validação RBAC de views."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.shortcuts import redirect
                from django.conf import settings
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
            if not tem_funcionalidade(request.user, codigo_funcionalidade):
                raise PermissionDenied(f"Acesso negado: funcionalidade '{codigo_funcionalidade}' necessária.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
