from functools import wraps
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

from .enums import PapelUsuarioEnum


# ==============================================================================
# GUARDS E FUNÇÕES DE CHECAGEM PURAS (DESACOPLADAS E EXTENSÍVEIS)
# ==============================================================================

def get_papel_usuario(user):
    """
    Retorna o papel do usuário ou None se não autenticado/sem perfil.
    """
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return PapelUsuarioEnum.DEV
    if hasattr(user, 'perfil') and user.perfil:
        return user.perfil.papel
    return None


def usuario_is_dev(user):
    """Verifica se o usuário possui papel DEV (ou é superusuário)."""
    return get_papel_usuario(user) == PapelUsuarioEnum.DEV


def usuario_is_admin(user):
    """Verifica se o usuário possui papel ADMIN de loja."""
    return get_papel_usuario(user) == PapelUsuarioEnum.ADMIN


def usuario_is_supervisor(user):
    """Verifica se o usuário possui papel SUPERVISOR de loja."""
    return get_papel_usuario(user) == PapelUsuarioEnum.SUPERVISOR


def usuario_is_usuario_padrao(user):
    """Verifica se o usuário possui papel USUARIO de loja."""
    return get_papel_usuario(user) == PapelUsuarioEnum.USUARIO


def pode_visualizar_usuarios(user):
    """
    Regra RBAC de Leitura:
    - DEV: Visualiza usuários de todas as lojas (Cross-Tenant).
    - ADMIN e SUPERVISOR: Visualizam usuários da sua própria loja (Single-Tenant).
    - USUARIO: Bloqueado (No-Access / 403).
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.loja and perfil.papel in [PapelUsuarioEnum.ADMIN, PapelUsuarioEnum.SUPERVISOR]:
        return True
    return False


def pode_gerenciar_usuarios(user):
    """
    Regra RBAC de Escrita (Criar, Editar, Desativar, Resetar Senha):
    - DEV: Gerencia globalmente.
    - ADMIN: Gerencia subordinados da sua própria loja.
    - SUPERVISOR: Bloqueado em escrita (Read-Only no módulo).
    - USUARIO: Bloqueado (No-Access).
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    if usuario_is_admin(user):
        return True
    return False


def pode_criar_usuario(autor, papel_alvo, loja_alvo):
    """
    Valida se o autor tem permissão para criar um usuário com o papel e a loja informados.
    - DEV: Pode criar qualquer papel (DEV, ADMIN, SUPERVISOR, USUARIO) para qualquer loja (ou None se DEV).
    - ADMIN: Pode criar APENAS SUPERVISOR e USUARIO para a SUA própria loja.
    - Outros: False.
    """
    if not autor or not autor.is_authenticated:
        return False

    if usuario_is_dev(autor):
        if papel_alvo == PapelUsuarioEnum.DEV:
            return True
        return loja_alvo is not None

    if usuario_is_admin(autor):
        perfil_autor = getattr(autor, 'perfil', None)
        if not perfil_autor or not perfil_autor.loja:
            return False
        # ADMIN só pode criar SUPERVISOR ou USUARIO
        if papel_alvo not in [PapelUsuarioEnum.SUPERVISOR, PapelUsuarioEnum.USUARIO]:
            return False
        # ADMIN só pode criar para a sua própria loja
        return loja_alvo == perfil_autor.loja

    return False


def pode_editar_usuario(autor, usuario_alvo):
    """
    Valida se o autor pode editar/gerenciar o usuário alvo (Ownership Check e Hierarquia):
    - DEV: Pode editar qualquer usuário.
    - ADMIN:
      - O usuário alvo DEVE pertencer à mesma loja do ADMIN.
      - O usuário alvo NÃO PODE ser DEV nem outro ADMIN (apenas subordinados: SUPERVISOR ou USUARIO).
    - Outros perfis: False.
    """
    if not autor or not autor.is_authenticated or not usuario_alvo:
        return False

    if usuario_is_dev(autor):
        return True

    if usuario_is_admin(autor):
        perfil_autor = getattr(autor, 'perfil', None)
        perfil_alvo = getattr(usuario_alvo, 'perfil', None)
        
        if not perfil_autor or not perfil_autor.loja or not perfil_alvo or not perfil_alvo.loja:
            return False

        # Validação de Tenant (Ownership Check estrito)
        if perfil_autor.loja_id != perfil_alvo.loja_id:
            return False

        # Validação Hierárquica: ADMIN não edita DEV nem outro ADMIN
        if perfil_alvo.papel in [PapelUsuarioEnum.DEV, PapelUsuarioEnum.ADMIN]:
            return False

        return True

    return False


def pode_alterar_papel(autor, usuario_alvo, novo_papel):
    """
    Valida a troca de papel de um usuário:
    - Nenhum usuário pode alterar o próprio papel.
    - DEV: Pode atribuir qualquer papel (incluindo DEV - RN-08).
    - ADMIN: Pode alternar APENAS entre SUPERVISOR e USUARIO de sua loja.
    """
    if autor == usuario_alvo:
        return False

    if not pode_editar_usuario(autor, usuario_alvo):
        return False

    if usuario_is_dev(autor):
        return True

    if usuario_is_admin(autor):
        return novo_papel in [PapelUsuarioEnum.SUPERVISOR, PapelUsuarioEnum.USUARIO]

    return False


# ==============================================================================
# MIXINS PARA CLASS-BASED VIEWS
# ==============================================================================

class DevRequiredMixin(AccessMixin):
    """
    Mixin exigindo que o usuário possua papel DEV (exclusivo para provisionamento de tenants).
    """
    permission_denied_message = "Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV)."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not usuario_is_dev(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class UserListAccessMixin(AccessMixin):
    """
    Mixin para a tela de listagem de usuários.
    Permite acesso a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403.
    """
    permission_denied_message = "Acesso restrito: seu perfil não possui permissão para visualizar este módulo."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_visualizar_usuarios(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class UserWriteAccessMixin(AccessMixin):
    """
    Mixin para mutações de usuários (criação, edição, status, redefinição de senha).
    Permite acesso apenas a DEV e ADMIN.
    Bloqueia SUPERVISOR (Read-Only) e USUARIO (No-Access) com 403 Forbidden.
    """
    permission_denied_message = "Acesso negado: seu perfil não possui permissão para alterar usuários."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_gerenciar_usuarios(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class UserOwnershipCheckMixin:
    """
    Mixin aplicado a views que manipulam um usuário específico (User/PerfilUsuario).
    Executa verificação de Ownership e Hierarquia no get_object() antes de permitir a operação.
    """
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        # O objeto pode ser User ou PerfilUsuario
        target_user = obj if hasattr(obj, 'perfil') else obj.usuario
        if not pode_editar_usuario(self.request.user, target_user):
            raise PermissionDenied("Acesso negado: você não possui permissão para gerenciar este usuário.")
        return obj


# ==============================================================================
# DECORATORS PARA FUNCTION-BASED VIEWS
# ==============================================================================

def dev_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not usuario_is_dev(request.user):
            messages.error(request, "Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
            raise PermissionDenied("Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

