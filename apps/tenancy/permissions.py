# Os códigos foram gerados com auxilio de I.A.

# Importa o decorador wraps do functools para preservar metadados originais (docstring, nome) de funções decoradas
from functools import wraps

# Importa a classe base AccessMixin do framework de autenticação do Django para controle de permissões em CBVs
from django.contrib.auth.mixins import AccessMixin

# Importa a exceção PermissionDenied para disparar respostas HTTP 403 Forbidden em caso de recusa de acesso
from django.core.exceptions import PermissionDenied

# Importa o atalho redirect para redirecionamento de usuários não autenticados
from django.shortcuts import redirect

# Importa o framework de mensagens para exibir alertas amigáveis na interface do usuário
from django.contrib import messages

# Importa os enums de papéis de usuários (RBAC) e módulos estruturais do sistema
from .enums import PapelUsuarioEnum, ModuloSistemaEnum


# ==============================================================================
# FEATURE FLAG GUARD POR TENANT (MÓDULOS DE SISTEMA)
# ==============================================================================

# Declaração do mixin de autorização por Feature Flags de módulos em nível de tenant
class ModuloRequeridoMixin(AccessMixin):
    # Início do bloco de docstring que documenta o objetivo, desacoplamento por tenant, RBAC e isolamento multi-tenant
    """
    O QUE FAZ: Mixin de controle de acesso que valida se o módulo funcional exigido está contratado/ativo para a Loja do usuário.
    POR QUE FAZ: Implementa o desacoplamento de funcionalidades por Feature Flags em nível de Tenant. Permite que o usuário DEV ative ou revogue módulos individualmente para cada loja.
    PERMISSÕES RBAC:
      - DEV: Possui bypass total e irrestrito (acesso global a todos os módulos e lojas).
      - ADMIN, SUPERVISOR, USUARIO: Valida se o módulo está ativo (ativo=True) para a loja vinculada ao perfil.
    MULTI-TENANCY: Garante que os usuários de uma Loja não acessem rotas ou funcionalidades de módulos não contratados por aquele tenant.
    """
    # Fim da docstring explicativa

    # Identificador do módulo exigido, sobrescrito pelas subclasses (ex: 'catalogo', 'pedidos')
    modulo_requerido: str = None  # Definido na subclasse (ex: 'catalogo', 'pedidos', 'marketplaces', 'financeiro')

    # Mensagem de erro padrão para o caso de o módulo estar desabilitado para o tenant
    mensagem_modulo_inativo: str = "Acesso negado: o módulo solicitado não está ativo para a sua loja."

    # Intercepta o despacho da requisição para aplicar as validações de autenticação, bypass e feature flags
    def dispatch(self, request, *args, **kwargs):
        # Exige autenticação prévia; caso anônimo, aciona o manipulador padrão de redirecionamento para o login
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # 1. Bypass total para o perfil Desenvolvedor (DEV) ou superusuário
        # Desenvolvedores possuem visão global e acesso irrestrito a todos os módulos independentemente da loja
        if usuario_is_dev(request.user):
            return super().dispatch(request, *args, **kwargs)

        # 2. Usuário comum deve possuir perfil e loja vinculada
        # Obtém o perfil de acesso do usuário autenticado
        perfil = getattr(request.user, 'perfil', None)
        # Bloqueia com HTTP 403 caso o usuário não tenha perfil estruturado ou não esteja vinculado a uma loja
        if not perfil or not perfil.loja:
            raise PermissionDenied("Acesso negado: usuário não vinculado a nenhuma loja ativa.")

        # 3. Validação da Feature Flag do Módulo para a Loja
        # Se a view declarou um módulo específico como obrigatório
        if self.modulo_requerido:
            loja = perfil.loja
            # Bloqueia caso a loja esteja inativa ou o módulo específico não esteja habilitado para aquele tenant
            if not loja.ativo or not loja.tem_modulo_ativo(self.modulo_requerido):
                # Registra notificação visual de erro para o usuário
                messages.error(
                    request,
                    f"O módulo '{self.obter_nome_modulo_display()}' não está habilitado para a sua loja."
                )
                # Levanta exceção de acesso negado (HTTP 403 Forbidden)
                raise PermissionDenied(self.mensagem_modulo_inativo)

        # Se todas as validações foram satisfeitas, prossegue com o processamento normal da CBV
        return super().dispatch(request, *args, **kwargs)

    # Resolve o rótulo amigável legível por humanos a partir do enum do módulo
    def obter_nome_modulo_display(self) -> str:
        """Retorna o nome legível do módulo a partir do enum."""
        for choice_val, choice_label in ModuloSistemaEnum.choices:
            if choice_val == self.modulo_requerido:
                return choice_label
        return self.modulo_requerido or "Módulo"


# ==============================================================================
# GUARDS E FUNÇÕES DE CHECAGEM PURAS (RBAC E MULTI-TENANT)
# ==============================================================================

# Função utilitária pura para obter com segurança o papel RBAC do usuário
def get_papel_usuario(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Retorna o papel do usuário ou None se não autenticado/sem perfil.
    POR QUE FAZ: Centraliza a leitura segura do papel de acesso evitando AttributeError.
    PERMISSÕES RBAC: Qualquer usuário autenticado.
    MULTI-TENANCY: Acesso neutro à propriedade de perfil.
    """
    # Fim da docstring informativa

    # Se o objeto de usuário for nulo ou anônimo, retorna None
    if not user or not user.is_authenticated:
        return None
    # Superusuários nativos do Django são equiparados diretamente ao papel DEV
    if user.is_superuser:
        return PapelUsuarioEnum.DEV
    # Se possui PerfilUsuario registrado, retorna o papel cadastrado
    if hasattr(user, 'perfil') and user.perfil:
        return user.perfil.papel
    return None


# Verifica se o usuário autenticado possui o papel mestre DEV ou privilégio de superusuário
def usuario_is_dev(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Verifica se o usuário possui papel DEV ou é superuser.
    POR QUE FAZ: Identifica operadores globais com bypass de tenants e módulos.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Global.
    """
    # Fim da docstring explicativa
    return get_papel_usuario(user) == PapelUsuarioEnum.DEV


# Verifica se o usuário possui o papel de Administrador de Loja (ADMIN)
def usuario_is_admin(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Verifica se o usuário possui papel ADMIN de loja.
    POR QUE FAZ: Permite autorização administrativa no escopo da loja.
    PERMISSÕES RBAC: ADMIN.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring informativa
    return get_papel_usuario(user) == PapelUsuarioEnum.ADMIN


# Verifica se o usuário possui o papel intermediário de Supervisor de Loja (SUPERVISOR)
def usuario_is_supervisor(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Verifica se o usuário possui papel SUPERVISOR de loja.
    POR QUE FAZ: Permite autorização operacional intermediária (preço, estoque, sincronização).
    PERMISSÕES RBAC: SUPERVISOR.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring explicativa
    return get_papel_usuario(user) == PapelUsuarioEnum.SUPERVISOR


# Verifica se o usuário possui o papel restrito de Usuário Operacional (USUARIO)
def usuario_is_usuario_padrao(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Verifica se o usuário possui papel USUARIO de loja.
    POR QUE FAZ: Permite aplicar restrições de escrita restrita (apenas avaria e descritivos).
    PERMISSÕES RBAC: USUARIO.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring explicativa
    return get_papel_usuario(user) == PapelUsuarioEnum.USUARIO


# Regra RBAC para conceder ou negar a permissão de visualização/listagem de usuários
def pode_visualizar_usuarios(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Regra RBAC de Leitura de Usuários.
    POR QUE FAZ: DEV visualiza todas as lojas; ADMIN e SUPERVISOR visualizam sua própria loja; USUARIO não tem acesso.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Filtro por loja para não-DEV.
    """
    # Fim da docstring informativa

    # Nega acesso para usuários anônimos
    if not user or not user.is_authenticated:
        return False
    # Concede acesso irrestrito para desenvolvedores
    if usuario_is_dev(user):
        return True
    # Para operadores com perfil e loja, autoriza apenas ADMIN e SUPERVISOR
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.loja and perfil.papel in [PapelUsuarioEnum.ADMIN, PapelUsuarioEnum.SUPERVISOR]:
        return True
    return False


# Regra RBAC para conceder ou negar permissões de escrita (criação, edição, status e senhas) de usuários
def pode_gerenciar_usuarios(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Regra RBAC de Escrita de Usuários (Criar, Editar, Status, Senha).
    POR QUE FAZ: DEV gerencia globalmente; ADMIN gerencia subordinados da sua loja; outros são bloqueados.
    PERMISSÕES RBAC: DEV, ADMIN.
    MULTI-TENANCY: ADMIN restrito à própria loja.
    """
    # Fim da docstring explicativa

    # Nega se não autenticado
    if not user or not user.is_authenticated:
        return False
    # Concede gestão global a desenvolvedores
    if usuario_is_dev(user):
        return True
    # Concede gestão local a administradores de tenant
    if usuario_is_admin(user):
        return True
    return False


# Valida se determinado autor possui privilégios para criar uma conta com papel e loja específicos
def pode_criar_usuario(autor, papel_alvo, loja_alvo):
    # Início do bloco de docstring que documenta as restrições de hierarquia estrita
    """
    O QUE FAZ: Valida se o autor tem permissão para criar um usuário com o papel e a loja informados.
    POR QUE FAZ: Garante hierarquia estrita: ADMIN não cria DEV nem ADMIN, apenas SUPERVISOR e USUARIO na própria loja.
    PERMISSÕES RBAC: DEV cria qualquer perfil; ADMIN cria SUPERVISOR/USUARIO em sua loja.
    MULTI-TENANCY: Loja obrigatória para não-DEV e estritamente igual à do autor ADMIN.
    """
    # Fim da docstring explicativa

    # Rejeita requisições não autenticadas
    if not autor or not autor.is_authenticated:
        return False

    # Regras aplicáveis ao autor DEV
    if usuario_is_dev(autor):
        # Se for criar outro DEV, dispensa vinculação com loja
        if papel_alvo == PapelUsuarioEnum.DEV:
            return True
        # Se for criar perfis não-DEV, exige obrigatoriamente a indicação de uma loja
        return loja_alvo is not None

    # Regras aplicáveis ao autor ADMIN
    if usuario_is_admin(autor):
        perfil_autor = getattr(autor, 'perfil', None)
        # Exige que o administrador possua perfil e loja associados
        if not perfil_autor or not perfil_autor.loja:
            return False
        # Impede que ADMIN crie outros ADMINs ou DEVs (permite apenas SUPERVISOR e USUARIO)
        if papel_alvo not in [PapelUsuarioEnum.SUPERVISOR, PapelUsuarioEnum.USUARIO]:
            return False
        # Garante que o novo usuário seja vinculado estritamente à mesma loja do administrador
        return loja_alvo == perfil_autor.loja

    # Demais papéis não possuem autorização para criar usuários
    return False


# Valida se determinado autor pode editar os dados de um usuário alvo (Ownership e Hierarquia)
def pode_editar_usuario(autor, usuario_alvo):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida se o autor pode editar o usuário alvo (Ownership Check e Hierarquia).
    POR QUE FAZ: Impede que ADMIN edite DEV ou ADMIN de outra ou da mesma loja (apenas subordinados).
    PERMISSÕES RBAC: DEV edita todos; ADMIN edita SUPERVISOR/USUARIO de sua loja.
    MULTI-TENANCY: Validação estrita loja_id autor == loja_id alvo.
    """
    # Fim da docstring explicativa

    # Validações defensivas básicas de autenticação e existência do usuário alvo
    if not autor or not autor.is_authenticated or not usuario_alvo:
        return False

    # Usuário DEV possui autorização irrestrita para editar qualquer conta
    if usuario_is_dev(autor):
        return True

    # Regras de edição aplicáveis a administradores de loja
    if usuario_is_admin(autor):
        perfil_autor = getattr(autor, 'perfil', None)
        perfil_alvo = getattr(usuario_alvo, 'perfil', None)

        # Exige perfil e vínculo de loja válidos para ambos os usuários
        if not perfil_autor or not perfil_autor.loja or not perfil_alvo or not perfil_alvo.loja:
            return False

        # Bloqueia manipulação se o usuário alvo pertencer a uma loja diferente
        if perfil_autor.loja_id != perfil_alvo.loja_id:
            return False

        # Impede que o administrador edite contas DEV ou outros administradores (apenas subordinados)
        if perfil_alvo.papel in [PapelUsuarioEnum.DEV, PapelUsuarioEnum.ADMIN]:
            return False

        return True

    return False


# Valida se o autor pode alterar o papel hierárquico de um usuário existente
def pode_alterar_papel(autor, usuario_alvo, novo_papel):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida a troca de papel de um usuário subordinado.
    POR QUE FAZ: Nenhum usuário altera o próprio papel; DEV altera para qualquer papel; ADMIN apenas SUPERVISOR/USUARIO.
    PERMISSÕES RBAC: DEV (qualquer), ADMIN (subordinados).
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da docstring explicativa

    # Trava de segurança: impede que qualquer operador altere o seu próprio papel
    if autor == usuario_alvo:
        return False

    # Exige que o autor tenha privilégios gerais de edição sobre o usuário alvo
    if not pode_editar_usuario(autor, usuario_alvo):
        return False

    # DEV pode promover ou rebaixar usuários para qualquer papel
    if usuario_is_dev(autor):
        return True

    # ADMIN pode alterar o papel de subordinados apenas alternando entre SUPERVISOR e USUARIO
    if usuario_is_admin(autor):
        return novo_papel in [PapelUsuarioEnum.SUPERVISOR, PapelUsuarioEnum.USUARIO]

    return False


# ==============================================================================
# GUARDS DE PRODUTOS, CATEGORIAS E ESTOQUE (RF-03 / RN-09)
# ==============================================================================

# Valida permissão para modificar preços de venda de produtos físicos ou anúncios (RN-09)
def pode_alterar_preco(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida se o usuário pode alterar preço de venda (RN-09).
    POR QUE FAZ: Protege a precificação contra alterações por operadores sem autorização comercial (USUARIO).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring explicativa

    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    # Autoriza administradores e supervisores; bloqueia usuários comuns
    if perfil and perfil.papel in [PapelUsuarioEnum.ADMIN, PapelUsuarioEnum.SUPERVISOR]:
        return True
    return False


# Valida se o operador tem permissão para realizar ajustes arbitrários no saldo de estoque geral
def pode_ajustar_estoque_geral(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida se o usuário pode realizar ajuste geral de saldo de estoque (RN-09).
    POR QUE FAZ: USUARIO tem acesso apenas a baixa pontual por avaria.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring explicativa
    return pode_alterar_preco(user)


# Valida permissão para efetuar a exclusão de entidades de catálogo (Produtos ou Categorias)
def pode_excluir_catalogo(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida se o usuário pode excluir Produtos ou Categorias (RN-09).
    POR QUE FAZ: Exclusão é ação destrutiva restrita a gestores.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring explicativa
    return pode_alterar_preco(user)


# Valida permissão para registrar perdas pontuais ou avarias físicas de produtos
def pode_dar_baixa_avaria(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida se o usuário pode registrar baixa pontual de estoque por avaria/perda (RN-09).
    POR QUE FAZ: Permite que operadores de galpão (USUARIO) registrem perdas físicas com justificativa.
    PERMISSÕES RBAC: Todos os usuários autenticados vinculados a uma Loja.
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    # Fim da docstring explicativa

    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    # Qualquer usuário autenticado associado a uma loja possui permissão para apontar avarias
    perfil = getattr(user, 'perfil', None)
    return perfil is not None and perfil.loja is not None


# Validação universal de posse multi-tenant para qualquer entidade com chave estrangeira para Loja (RN-01)
def pode_acessar_objeto_loja(user, obj):
    # Início do bloco de docstring
    """
    O QUE FAZ: Ownership Check genérico para qualquer entidade vinculada a uma Loja (RN-01).
    POR QUE FAZ: Impede que o usuário A visualize ou manipule recursos da loja B.
    PERMISSÕES RBAC: DEV tem visão global; outros apenas se obj.loja_id == user.perfil.loja_id.
    MULTI-TENANCY: Base de validação horizontal entre tenants.
    """
    # Fim da docstring explicativa

    if not user or not user.is_authenticated:
        return False
    # DEV acessa dados de qualquer loja
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if not perfil or not perfil.loja_id:
        return False
    # Compara a loja associada ao objeto com a loja do usuário autenticado
    return getattr(obj, 'loja_id', None) == perfil.loja_id


# Valida se o usuário pode manipular credenciais e parâmetros das integrações de marketplaces
def pode_configurar_integracao(user, loja=None):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida permissão para cadastrar/editar credenciais e contas de marketplaces.
    POR QUE FAZ: Credenciais de canais contêm segredos de API e devem ser restritas a administradores.
    PERMISSÕES RBAC: DEV (qualquer loja); ADMIN (sua própria loja); SUPERVISOR/USUARIO (bloqueados).
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da docstring explicativa

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


# Valida permissão para acionar rotinas de sincronização manual de produtos, preços e estoques
def pode_disparar_sincronizacao(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida permissão para disparar sincronização manual de preços e anúncios para marketplaces externos.
    POR QUE FAZ: Evita sobrecarga de API externa por operadores não autorizados.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring explicativa

    if not user or not user.is_authenticated:
        return False
    if usuario_is_dev(user):
        return True
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.papel in [PapelUsuarioEnum.ADMIN, PapelUsuarioEnum.SUPERVISOR]:
        return True
    return False


# Valida permissão para visualizar relatórios de rentabilidade, markups e simulador de preços
def pode_acessar_inteligencia_financeira(user):
    # Início do bloco de docstring
    """
    O QUE FAZ: Valida acesso ao simulador promocional e formação de preço.
    POR QUE FAZ: Informações estratégicas de margem, elasticidade e custos fixos são restritas a gestores.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR = True; USUARIO = False.
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim da docstring explicativa
    return pode_disparar_sincronizacao(user)


# ==============================================================================
# MIXINS PARA CLASS-BASED VIEWS
# ==============================================================================

# Mixin restritivo que exige categoricamente o papel de Desenvolvedor (DEV)
class DevRequiredMixin(AccessMixin):
    # Início do bloco de docstring
    """
    O QUE FAZ: Exige que o usuário possua papel DEV (exclusivo para provisionamento de tenants e gestão global de flags).
    POR QUE FAZ: Protege rotas de infraestrutura e tenant management global.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Acesso global.
    """
    # Fim da docstring explicativa

    # Mensagem de recusa padronizada
    permission_denied_message = "Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV)."

    # Valida a requisição antes do despacho
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Bloqueia qualquer usuário que não seja DEV
        if not usuario_is_dev(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


# Mixin para controle de acesso à tela de listagem de usuários do tenant
class UserListAccessMixin(AccessMixin):
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin para listagem de usuários com isolamento multi-tenant.
    POR QUE FAZ: Permite acesso a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da docstring explicativa

    permission_denied_message = "Acesso restrito: seu perfil não possui permissão para visualizar este módulo."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Bloqueia operadores operacionais comuns (USUARIO)
        if not pode_visualizar_usuarios(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


# Mixin para views de criação, edição e alteração de status de contas de usuários
class UserWriteAccessMixin(AccessMixin):
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin para criação, edição e alteração de status de usuários.
    POR QUE FAZ: Permite acesso a DEV e ADMIN. Bloqueia SUPERVISOR e USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN.
    MULTI-TENANCY: ADMIN restrito à própria loja.
    """
    # Fim da docstring explicativa

    permission_denied_message = "Acesso negado: seu perfil não possui permissão para alterar usuários."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Bloqueia se não for DEV ou ADMIN
        if not pode_gerenciar_usuarios(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


# Mixin aplicado em views de detalhe/edição para validar posse e hierarquia sobre um usuário alvo
class UserOwnershipCheckMixin:
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin aplicado a views que manipulam um usuário específico.
    POR QUE FAZ: Valida ownership e hierarquia de acesso antes de executar operações em get_object().
    PERMISSÕES RBAC: DEV edita todos; ADMIN edita apenas subordinados da sua loja.
    MULTI-TENANCY: Checagem estrita de pertencimento de tenant.
    """
    # Fim da docstring explicativa

    def get_object(self, queryset=None):
        # Carrega o objeto da view ancestral
        obj = super().get_object(queryset=queryset)
        # Extrai a instância de User independentemente de o modelo ser User ou PerfilUsuario
        target_user = obj if hasattr(obj, 'perfil') else getattr(obj, 'usuario', obj)
        # Valida as regras de autorização de edição sobre o usuário alvo
        if not pode_editar_usuario(self.request.user, target_user):
            raise PermissionDenied("Acesso negado: você não possui permissão para gerenciar este usuário.")
        return obj


# Mixin para garantir que entidades de catálogo (Produto, Categoria) pertençam ao mesmo tenant do usuário
class CatalogOwnershipCheckMixin:
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin para views de Produto e Categoria validando isolamento horizontal de loja.
    POR QUE FAZ: Garante que um lojista não visualize nem altere o catálogo de outro lojista.
    PERMISSÕES RBAC: DEV ou usuário pertencente à mesma loja do objeto.
    MULTI-TENANCY: Validação estrita obj.loja_id == request.user.perfil.loja_id.
    """
    # Fim da docstring explicativa

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        # Rejeita requisição com HTTP 403 caso o registro pertença a outro tenant
        if not pode_acessar_objeto_loja(self.request.user, obj):
            raise PermissionDenied("Acesso negado: este registro pertence a outra loja.")
        return obj


# Mixin para proteger ações destrutivas de exclusão no catálogo de produtos
class CatalogDeletePermissionMixin(AccessMixin):
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin para exclusão de Produtos e Categorias.
    POR QUE FAZ: Bloqueia o perfil USUARIO com 403 Forbidden (RN-09).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da docstring explicativa

    permission_denied_message = "Acesso negado: seu perfil não possui permissão para excluir itens do catálogo."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_excluir_catalogo(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


# Mixin para restringir telas de credenciamento de contas e canais integrados
class IntegracaoConfigPermissionMixin(AccessMixin):
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin para views de configuração de canais e credenciais de marketplaces.
    POR QUE FAZ: Permite acesso a DEV e ADMIN. Bloqueia SUPERVISOR e USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN.
    MULTI-TENANCY: ADMIN restrito à sua própria loja.
    """
    # Fim da docstring explicativa

    permission_denied_message = "Acesso negado: apenas administradores da loja ou desenvolvedores podem gerenciar credenciais de integração."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_configurar_integracao(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


# Mixin para autorização de disparo manual de sincronizações de catálogo e estoques
class SyncPermissionMixin(AccessMixin):
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin para disparo manual de sincronização com marketplaces.
    POR QUE FAZ: Permite acesso a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    # Fim da docstring explicativa

    permission_denied_message = "Acesso negado: seu perfil não possui permissão para disparar sincronizações com marketplaces."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_disparar_sincronizacao(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


# Mixin para autorizar acesso aos motores de inteligência e simuladores financeiros
class FinancialAccessMixin(AccessMixin):
    # Início do bloco de docstring
    """
    O QUE FAZ: Mixin para o simulador financeiro e formação de preço.
    POR QUE FAZ: Restrito a DEV, ADMIN e SUPERVISOR. Bloqueia USUARIO com 403 Forbidden.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    # Fim da docstring explicativa

    permission_denied_message = "Acesso negado: seu perfil não possui permissão para acessar o simulador financeiro promocional."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode_acessar_inteligencia_financeira(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


# Decorador funcional para views baseadas em função (FBVs) exigindo papel DEV
def dev_required(view_func):
    # Início do bloco de docstring
    """
    O QUE FAZ: Decorator para Function-Based Views exigindo papel DEV.
    POR QUE FAZ: Protege endpoints exclusivos de infraestrutura / desenvolvedor.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Global.
    """
    # Fim da docstring explicativa

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Redireciona para o login se não autenticado
        if not request.user.is_authenticated:
            return redirect('login')
        # Emite mensagem e lança PermissionDenied (HTTP 403) se o operador não for DEV
        if not usuario_is_dev(request.user):
            messages.error(request, "Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
            raise PermissionDenied("Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
