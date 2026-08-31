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
# GUARDS DE PRODUTOS, CATEGORIAS E ESTOQUE (RF-03 / RN-09)
# ==============================================================================

def pode_alterar_preco(user):
    """
    RN-09: Preço de venda só pode ser definido/alterado por DEV, ADMIN ou SUPERVISOR.
    USUARIO possui permissão apenas de leitura sobre preços.
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.papel in [PapelUsuarioEnum.ADMIN, PapelUsuarioEnum.SUPERVISOR]:
        return True
    return False


def pode_ajustar_estoque_geral(user):
    """
    RN-09: Ajuste geral de saldo de estoque é restrito a DEV, ADMIN e SUPERVISOR.
    USUARIO não altera o estoque na edição geral de produtos.
    """
    return pode_alterar_preco(user)


def pode_excluir_catalogo(user):
    """
    RN-09: Exclusão de Produtos e Categorias é restrita a DEV, ADMIN e SUPERVISOR.
    USUARIO não tem permissão para excluir itens do catálogo (403 Forbidden).
    """
    return pode_alterar_preco(user)


def pode_dar_baixa_avaria(user):
    """
    RN-09: Todos os perfis autenticados vinculados a uma loja (inclusive USUARIO)
    podem registrar baixa pontual de estoque por motivo de avaria/perda.
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    return perfil is not None and perfil.loja is not None


def pode_acessar_objeto_loja(user, obj):
    """
    Ownership Check para qualquer modelo com FK 'loja' (Produto, Categoria, HistoricoPreco):
    - DEV: Acesso global a qualquer loja.
    - Demais perfis: Acesso estritamente permitido se obj.loja_id == user.perfil.loja_id.
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if not perfil or not perfil.loja_id:
        return False
    return obj.loja_id == perfil.loja_id


# ==============================================================================
# GUARDS DE INTEGRAÇÃO COM MARKETPLACES (RF-05)
# ==============================================================================

def pode_configurar_integracao(user, loja=None):
    """
    RN-09 / Matriz RBAC: Configuração de credenciais do Mercado Livre (Client ID, Secret, Tokens)
    é permitida exclusivamente para:
    - DEV: em qualquer loja (escopo global);
    - ADMIN: estritamente na sua própria loja.
    SUPERVISOR e USUARIO não possuem acesso a credenciais.
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    if usuario_is_admin(user):
        if loja is None:
            return True
        perfil = getattr(user, 'perfil', None)
        return perfil is not None and perfil.loja_id == loja.id
    return False


def pode_disparar_sincronizacao(user):
    """
    RN-09 / Matriz RBAC: Disparo de sincronização de preços (unitária ou em lote)
    é permitido para DEV, ADMIN e SUPERVISOR.
    USUARIO é estritamente bloqueado (403 Forbidden).
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.papel in [PapelUsuarioEnum.ADMIN, PapelUsuarioEnum.SUPERVISOR]:
        return True
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
        target_user = obj if hasattr(obj, 'perfil') else obj.usuario
        if not pode_editar_usuario(self.request.user, target_user):
            raise PermissionDenied("Acesso negado: você não possui permissão para gerenciar este usuário.")
        return obj


class CatalogOwnershipCheckMixin:
    """
    Mixin para views de Produto e Categoria.
    Garante que o objeto pertença à mesma loja do usuário logado (Ownership Check estrito).
    """
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if not pode_acessar_objeto_loja(self.request.user, obj):
            raise PermissionDenied("Acesso negado: este registro pertence a outra loja.")
        return obj


class CatalogDeletePermissionMixin(AccessMixin):
    """
    Mixin para exclusão de Produtos e Categorias.
    Bloqueia o perfil USUARIO com 403 Forbidden (RN-09).
    """
    permission_denied_message = "Acesso negado: seu perfil não possui permissão para excluir itens do catálogo."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_excluir_catalogo(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class IntegracaoConfigPermissionMixin(AccessMixin):
    """
    Mixin para a tela de configuração de credenciais e integrações da Loja (RF-05).
    Permite acesso a DEV e ADMIN. Bloqueia SUPERVISOR e USUARIO com 403 Forbidden.
    """
    permission_denied_message = "Acesso negado: apenas administradores da loja ou desenvolvedores podem gerenciar credenciais de integração."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_configurar_integracao(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class SyncPermissionMixin(AccessMixin):
    """
    Mixin para views de disparo de sincronização com marketplaces (RF-05).
    Permite acesso a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403 Forbidden.
    """
    permission_denied_message = "Acesso negado: seu perfil não possui permissão para disparar sincronizações com marketplaces."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_disparar_sincronizacao(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


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



