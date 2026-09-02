# Os códigos foram gerados com auxilio de I.A.
from functools import wraps
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

from .enums import PapelUsuarioEnum, ModuloSistemaEnum


# ==============================================================================
# FEATURE FLAG GUARD POR TENANT (MÓDULOS DE SISTEMA)
# ==============================================================================

class ModuloRequeridoMixin(AccessMixin):
    """
    O QUE FAZ: Mixin de controle de acesso que valida se o módulo funcional exigido está contratado/ativo para a Loja do usuário.
    POR QUE FAZ: Implementa o desacoplamento de funcionalidades por Feature Flags em nível de Tenant. Permite que o usuário DEV ative ou revogue módulos individualmente para cada loja.
    PERMISSÕES RBAC:
      - DEV: Possui bypass total e irrestrito (acesso global a todos os módulos e lojas).
      - ADMIN, SUPERVISOR, USUARIO: Valida se o módulo está ativo (ativo=True) para a loja vinculada ao perfil.
    MULTI-TENANCY: Garante que os usuários de uma Loja não acessem rotas ou funcionalidades de módulos não contratados por aquele tenant.
    """
    modulo_requerido: str = None  # Definido na subclasse (ex: 'catalogo', 'pedidos', 'marketplaces', 'financeiro')
    mensagem_modulo_inativo: str = "Acesso negado: o módulo solicitado não está ativo para a sua loja."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # 1. Bypass total para o perfil Desenvolvedor (DEV) ou superusuário
        if usuario_is_dev(request.user):
            return super().dispatch(request, *args, **kwargs)

        # 2. Usuário comum deve possuir perfil e loja vinculada
        perfil = getattr(request.user, 'perfil', None)
        if not perfil or not perfil.loja:
            raise PermissionDenied("Acesso negado: usuário não vinculado a nenhuma loja ativa.")

        # 3. Validação da Feature Flag do Módulo para a Loja
        if self.modulo_requerido:
            loja = perfil.loja
            if not loja.ativo or not loja.tem_modulo_ativo(self.modulo_requerido):
                messages.error(
                    request,
                    f"O módulo '{self.obter_nome_modulo_display()}' não está habilitado para a sua loja."
                )
                raise PermissionDenied(self.mensagem_modulo_inativo)

        return super().dispatch(request, *args, **kwargs)

    def obter_nome_modulo_display(self) -> str:
        """Retorna o nome legível do módulo a partir do enum."""
        for choice_val, choice_label in ModuloSistemaEnum.choices:
            if choice_val == self.modulo_requerido:
                return choice_label
        return self.modulo_requerido or "Módulo"


# ==============================================================================
# GUARDS E FUNÇÕES DE CHECAGEM PURAS (RBAC E MULTI-TENANT)
# ==============================================================================

def get_papel_usuario(user):
    """
    O QUE FAZ: Retorna o papel do usuário ou None se não autenticado/sem perfil.
    POR QUE FAZ: Centraliza a leitura segura do papel de acesso evitando AttributeError.
    PERMISSÕES RBAC: Qualquer usuário autenticado.
    MULTI-TENANCY: Acesso neutro à propriedade de perfil.
    """
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return PapelUsuarioEnum.DEV
    if hasattr(user, 'perfil') and user.perfil:
        return user.perfil.papel
    return None


def usuario_is_dev(user):
    """
    O QUE FAZ: Verifica se o usuário possui papel DEV ou é superuser.
    POR QUE FAZ: Identifica operadores globais com bypass de tenants e módulos.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Global.
    """
    return get_papel_usuario(user) == PapelUsuarioEnum.DEV


def usuario_is_admin(user):
    """
    O QUE FAZ: Verifica se o usuário possui papel ADMIN de loja.
    POR QUE FAZ: Permite autorização administrativa no escopo da loja.
    PERMISSÕES RBAC: ADMIN.
    MULTI-TENANCY: Escopo da loja.
    """
    return get_papel_usuario(user) == PapelUsuarioEnum.ADMIN


def usuario_is_supervisor(user):
    """
    O QUE FAZ: Verifica se o usuário possui papel SUPERVISOR de loja.
    POR QUE FAZ: Permite autorização operacional intermediária (preço, estoque, sincronização).
    PERMISSÕES RBAC: SUPERVISOR.
    MULTI-TENANCY: Escopo da loja.
    """
    return get_papel_usuario(user) == PapelUsuarioEnum.SUPERVISOR


def usuario_is_usuario_padrao(user):
    """
    O QUE FAZ: Verifica se o usuário possui papel USUARIO de loja.
    POR QUE FAZ: Permite aplicar restrições de escrita restrita (apenas avaria e descritivos).
    PERMISSÕES RBAC: USUARIO.
    MULTI-TENANCY: Escopo da loja.
    """
    return get_papel_usuario(user) == PapelUsuarioEnum.USUARIO


def pode_visualizar_usuarios(user):
    """
    O QUE FAZ: Regra RBAC de Leitura de Usuários.
    POR QUE FAZ: DEV visualiza todas as lojas; ADMIN e SUPERVISOR visualizam sua própria loja; USUARIO não tem acesso.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Filtro por loja para não-DEV.
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
    O QUE FAZ: Regra RBAC de Escrita de Usuários (Criar, Editar, Status, Senha).
    POR QUE FAZ: DEV gerencia globalmente; ADMIN gerencia subordinados da sua loja; outros são bloqueados.
    PERMISSÕES RBAC: DEV, ADMIN.
    MULTI-TENANCY: ADMIN restrito à própria loja.
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
    O QUE FAZ: Valida se o autor tem permissão para criar um usuário com o papel e a loja informados.
    POR QUE FAZ: Garante hierarquia estrita: ADMIN não cria DEV nem ADMIN, apenas SUPERVISOR e USUARIO na própria loja.
    PERMISSÕES RBAC: DEV cria qualquer perfil; ADMIN cria SUPERVISOR/USUARIO em sua loja.
    MULTI-TENANCY: Loja obrigatória para não-DEV e estritamente igual à do autor ADMIN.
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
        if papel_alvo not in [PapelUsuarioEnum.SUPERVISOR, PapelUsuarioEnum.USUARIO]:
            return False
        return loja_alvo == perfil_autor.loja

    return False


def pode_editar_usuario(autor, usuario_alvo):
    """
    O QUE FAZ: Valida se o autor pode editar o usuário alvo (Ownership Check e Hierarquia).
    POR QUE FAZ: Impede que ADMIN edite DEV ou ADMIN de outra ou da mesma loja (apenas subordinados).
    PERMISSÕES RBAC: DEV edita todos; ADMIN edita SUPERVISOR/USUARIO de sua loja.
    MULTI-TENANCY: Validação estrita loja_id autor == loja_id alvo.
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

        if perfil_autor.loja_id != perfil_alvo.loja_id:
            return False

        if perfil_alvo.papel in [PapelUsuarioEnum.DEV, PapelUsuarioEnum.ADMIN]:
            return False

        return True

    return False


def pode_alterar_papel(autor, usuario_alvo, novo_papel):
    """
    O QUE FAZ: Valida a troca de papel de um usuário subordinado.
    POR QUE FAZ: Nenhum usuário altera o próprio papel; DEV altera para qualquer papel; ADMIN apenas SUPERVISOR/USUARIO.
    PERMISSÕES RBAC: DEV (qualquer), ADMIN (subordinados).
    MULTI-TENANCY: Isolado por loja.
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
    O QUE FAZ: Valida se o usuário pode alterar preço de venda (RN-09).
    POR QUE FAZ: Protege a precificação contra alterações por operadores sem autorização comercial (USUARIO).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
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
    O QUE FAZ: Valida se o usuário pode realizar ajuste geral de saldo de estoque (RN-09).
    POR QUE FAZ: USUARIO tem acesso apenas a baixa pontual por avaria.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    return pode_alterar_preco(user)


def pode_excluir_catalogo(user):
    """
    O QUE FAZ: Valida se o usuário pode excluir Produtos ou Categorias (RN-09).
    POR QUE FAZ: Exclusão é ação destrutiva restrita a gestores.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    return pode_alterar_preco(user)


def pode_dar_baixa_avaria(user):
    """
    O QUE FAZ: Valida se o usuário pode registrar baixa pontual de estoque por avaria/perda (RN-09).
    POR QUE FAZ: Permite que operadores de galpão (USUARIO) registrem perdas físicas com justificativa.
    PERMISSÕES RBAC: Todos os usuários autenticados vinculados a uma Loja.
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    return perfil is not None and perfil.loja is not None


def pode_acessar_objeto_loja(user, obj):
    """
    O QUE FAZ: Ownership Check genérico para qualquer entidade vinculada a uma Loja (RN-01).
    POR QUE FAZ: Impede que o usuário A visualize ou manipule recursos da loja B.
    PERMISSÕES RBAC: DEV tem visão global; outros apenas se obj.loja_id == user.perfil.loja_id.
    MULTI-TENANCY: Base de validação horizontal entre tenants.
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if not perfil or not perfil.loja_id:
        return False
    return getattr(obj, 'loja_id', None) == perfil.loja_id


def pode_configurar_integracao(user, loja=None):
    """
    O QUE FAZ: Valida permissão para cadastrar/editar credenciais e contas de marketplaces.
    POR QUE FAZ: Credenciais de canais contêm segredos de API e devem ser restritas a administradores.
    PERMISSÕES RBAC: DEV (qualquer loja); ADMIN (sua própria loja); SUPERVISOR/USUARIO (bloqueados).
    MULTI-TENANCY: Isolado por loja.
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
    O QUE FAZ: Valida permissão para disparar sincronização manual de preços e anúncios para marketplaces externos.
    POR QUE FAZ: Evita sobrecarga de API externa por operadores não autorizados.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.papel in [PapelUsuarioEnum.ADMIN, PapelUsuarioEnum.SUPERVISOR]:
        return True
    return False


def pode_acessar_inteligencia_financeira(user):
    """
    O QUE FAZ: Valida acesso ao simulador promocional e formação de preço.
    POR QUE FAZ: Informações estratégicas de margem, elasticidade e custos fixos são restritas a gestores.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    return pode_disparar_sincronizacao(user)


# ==============================================================================
# MIXINS PARA CLASS-BASED VIEWS
# ==============================================================================

class DevRequiredMixin(AccessMixin):
    """
    O QUE FAZ: Exige que o usuário possua papel DEV (exclusivo para provisionamento de tenants e gestão global de flags).
    POR QUE FAZ: Protege rotas de infraestrutura e tenant management global.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Acesso global.
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
    O QUE FAZ: Mixin para listagem de usuários com isolamento multi-tenant.
    POR QUE FAZ: Permite acesso a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Isolado por loja.
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
    O QUE FAZ: Mixin para criação, edição e alteração de status de usuários.
    POR QUE FAZ: Permite acesso a DEV e ADMIN. Bloqueia SUPERVISOR e USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN.
    MULTI-TENANCY: ADMIN restrito à própria loja.
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
    O QUE FAZ: Mixin aplicado a views que manipulam um usuário específico.
    POR QUE FAZ: Valida ownership e hierarquia de acesso antes de executar operações em get_object().
    PERMISSÕES RBAC: DEV edita todos; ADMIN edita apenas subordinados da sua loja.
    MULTI-TENANCY: Checagem estrita de pertencimento de tenant.
    """
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        target_user = obj if hasattr(obj, 'perfil') else getattr(obj, 'usuario', obj)
        if not pode_editar_usuario(self.request.user, target_user):
            raise PermissionDenied("Acesso negado: você não possui permissão para gerenciar este usuário.")
        return obj


class CatalogOwnershipCheckMixin:
    """
    O QUE FAZ: Mixin para views de Produto e Categoria validando isolamento horizontal de loja.
    POR QUE FAZ: Garante que um lojista não visualize nem altere o catálogo de outro lojista.
    PERMISSÕES RBAC: DEV ou usuário pertencente à mesma loja do objeto.
    MULTI-TENANCY: Validação estrita obj.loja_id == request.user.perfil.loja_id.
    """
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if not pode_acessar_objeto_loja(self.request.user, obj):
            raise PermissionDenied("Acesso negado: este registro pertence a outra loja.")
        return obj


class CatalogDeletePermissionMixin(AccessMixin):
    """
    O QUE FAZ: Mixin para exclusão de Produtos e Categorias.
    POR QUE FAZ: Bloqueia o perfil USUARIO com 403 Forbidden (RN-09).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Isolado por loja.
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
    O QUE FAZ: Mixin para views de configuração de canais e credenciais de marketplaces.
    POR QUE FAZ: Permite acesso a DEV e ADMIN. Bloqueia SUPERVISOR e USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN.
    MULTI-TENANCY: ADMIN restrito à sua própria loja.
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
    O QUE FAZ: Mixin para disparo manual de sincronização com marketplaces.
    POR QUE FAZ: Permite acesso a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    permission_denied_message = "Acesso negado: seu perfil não possui permissão para disparar sincronizações com marketplaces."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_disparar_sincronizacao(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class FinancialAccessMixin(AccessMixin):
    """
    O QUE FAZ: Mixin para o simulador financeiro e formação de preço.
    POR QUE FAZ: Restrito a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    permission_denied_message = "Acesso negado: seu perfil não possui permissão para acessar o simulador financeiro promocional."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_acessar_inteligencia_financeira(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


def dev_required(view_func):
    """
    O QUE FAZ: Decorator para Function-Based Views exigindo papel DEV.
    POR QUE FAZ: Protege endpoints exclusivos de infraestrutura / desenvolvedor.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Global.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not usuario_is_dev(request.user):
            messages.error(request, "Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
            raise PermissionDenied("Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
