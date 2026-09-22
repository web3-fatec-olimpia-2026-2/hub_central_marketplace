# Os códigos foram gerados com auxilio de I.A.

# Importa atalhos do Django para renderização de páginas HTML, redirecionamento HTTP e busca de objetos com tratamento 404
from django.shortcuts import render, redirect, get_object_or_404

# Importa utilitários para resolução dinâmica (reversa e tardia/lazy) de URLs nomeadas
from django.urls import reverse_lazy, reverse

# Importa as classes genéricas de views (CBVs) para renderização de templates, listagens, CRUD e formulários
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DetailView, FormView, View
)

# Importa o mixin de autenticação para exigir sessão ativa antes de permitir o acesso às views
from django.contrib.auth.mixins import LoginRequiredMixin

# Importa o modelo User nativo do Django para autenticação e gestão de usuários
from django.contrib.auth.models import User

# Importa o módulo de mensagens do framework para emissão de alertas e notificações para a interface do usuário
from django.contrib import messages

# Importa o gerenciador de transações atômicas para garantir rollback automático em operações compostas de banco
from django.db import transaction

# Importa Q para consultas ORM complexas com operadores lógicos e Count para agregações estatísticas
from django.db.models import Q, Count

# Importa PermissionDenied para emitir resposta HTTP 403 Forbidden em violações de autorização e fronteiras de tenant
from django.core.exceptions import PermissionDenied

# Importa as entidades de modelo Loja (tenant), PerfilUsuario (RBAC) e ModuloLoja (feature flags)
from .models import Loja, PerfilUsuario, ModuloLoja

# Importa as enumerações de papéis de usuários (RBAC) e módulos estruturais do sistema
from .enums import PapelUsuarioEnum, ModuloSistemaEnum

# Importa os formulários de gestão cadastral de lojas, feature flags, criação/edição de usuários e troca de senhas
from .forms import (
    LojaForm, LojaModulosForm, UsuarioCreateForm, UsuarioUpdateForm,
    UsuarioPasswordResetAdminForm
)

# Importa os mixins e funções puras de controle de acesso, validação hierárquica e checagem de ownership multi-tenant
from .permissions import (
    DevRequiredMixin, UserListAccessMixin, UserWriteAccessMixin, UserOwnershipCheckMixin,
    usuario_is_dev, usuario_is_admin, pode_visualizar_usuarios, pode_gerenciar_usuarios,
    pode_editar_usuario
)


# View responsável por renderizar a página inicial do sistema e o painel consolidado de KPIs
class DashboardHomeView(LoginRequiredMixin, TemplateView):
    # Início do bloco de docstring documentando as responsabilidades, permissões RBAC e segregação por tenant
    """
    O QUE FAZ: Visão geral e dashboard inicial do Hub Central.
    POR QUE FAZ: Apresenta KPIs e resumo operacional adaptados dinamicamente ao papel do usuário e aos módulos ativos de sua loja.
    PERMISSÕES RBAC: Todos os usuários autenticados.
    MULTI-TENANCY: DEV visualiza totais globais do sistema; demais usuários visualizam dados exclusivos de sua loja.
    """
    # Fim do bloco de docstring estrutural

    # Caminho relativo do template HTML associado a esta view
    template_name = 'tenancy/home.html'

    # Sobrescreve get_context_data para injetar métricas e dados contextuais adaptados ao papel do usuário autenticado
    def get_context_data(self, **kwargs):
        # Obtém o contexto original da classe ancestral
        context = super().get_context_data(**kwargs)

        # Captura o usuário atual da requisição
        user = self.request.user

        # Registra no contexto se o operador possui papel de desenvolvedor global (DEV)
        context['is_dev'] = usuario_is_dev(user)

        # Cenário 1: Usuário DEV obtém métricas globais agregadas de toda a plataforma multi-tenant
        if context['is_dev']:
            # Total geral de lojas cadastradas no sistema
            context['total_lojas'] = Loja.objects.count()

            # Total de lojas atualmente em status operacional ativo
            context['lojas_ativas'] = Loja.objects.filter(ativo=True).count()

            # As 5 organizações tenant provisionadas mais recentemente
            context['ultimas_lojas'] = Loja.objects.order_by('-criado_em')[:5]

            # Contagem total de operadores cadastrados em todo o sistema
            context['total_usuarios'] = User.objects.count()

        # Cenário 2: Usuários de loja (ADMIN, SUPERVISOR, USUARIO) visualizam apenas dados do seu próprio tenant
        else:
            # Recupera o perfil vinculado ao usuário
            perfil = getattr(user, 'perfil', None)
            context['perfil'] = perfil

            # Obtém a loja vinculada ao operador
            context['minha_loja'] = perfil.loja if perfil else None

            # Caso possua loja vinculada, coleta os totais restritos à sua organização
            if perfil and perfil.loja:
                # Contagem de usuários associados exclusivamente à sua loja
                context['total_usuarios_loja'] = User.objects.filter(perfil__loja=perfil.loja).count()

                # Lista de módulos do sistema e seus respectivos status contratados por aquela loja
                context['modulos_loja'] = perfil.loja.modulos.all()

        # Retorna o dicionário de contexto preparado para renderização do template
        return context


# ==============================================================================
# GESTÃO DE LOJAS (TENANTS) & FEATURE FLAGS — EXCLUSIVO DEV (RF-01)
# ==============================================================================

# View baseada em classe para listagem, auditoria e filtragem global de todos os tenants cadastrados
class LojaListView(DevRequiredMixin, ListView):
    # Início do bloco de docstring documentando o escopo administrativo exclusivo para o papel DEV
    """
    O QUE FAZ: Listagem geral de todas as Lojas (Tenants) cadastradas no Hub.
    POR QUE FAZ: Permite ao operador DEV auditar, gerenciar e navegar entre os tenants da plataforma.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Visão global agregada.
    """
    # Fim do bloco descritivo da classe

    # Modelo ORM alvo da consulta
    model = Loja

    # Template HTML a ser renderizado para a listagem de lojas
    template_name = 'tenancy/loja_list.html'

    # Nome da variável que disponibilizará a lista de lojas no template
    context_object_name = 'lojas'

    # Quantidade de itens por página para paginação defensiva
    paginate_by = 15

    # Constrói a consulta anotando métricas relacionais e aplicando filtros textuais e de status
    def get_queryset(self):
        # Anota o total de usuários vinculados e o total de módulos com flag ativa por loja
        queryset = Loja.objects.annotate(
            total_usuarios=Count('usuarios'),
            total_modulos_ativos=Count('modulos', filter=Q(modulos__ativo=True))
        ).order_by('-criado_em')

        # Captura parâmetros de busca e filtro da query string da URL
        termo_busca = self.request.GET.get('q', '').strip()
        status_filtro = self.request.GET.get('status', '').strip()

        # Aplica filtro textual abrangente cobrindo nome, CNPJ, cidade e e-mail
        if termo_busca:
            queryset = queryset.filter(
                Q(nome__icontains=termo_busca) |
                Q(cnpj__icontains=termo_busca) |
                Q(cidade__icontains=termo_busca) |
                Q(email__icontains=termo_busca)
            )

        # Filtro por status de atividade do tenant
        if status_filtro == 'ativo':
            queryset = queryset.filter(ativo=True)
        elif status_filtro == 'inativo':
            queryset = queryset.filter(ativo=False)

        # Retorna o queryset devidamente filtrado
        return queryset

    # Complementa o contexto injetando valores de formulário e totais estatísticos para a barra superior
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Mantém os valores preenchidos no formulário de busca após o envio
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()

        # Totalizadores para badges informativos no topo da tabela
        context['total_cadastradas'] = Loja.objects.count()
        context['total_ativas'] = Loja.objects.filter(ativo=True).count()
        return context


# View responsável pelo provisionamento e cadastro de um novo tenant no sistema
class LojaCreateView(DevRequiredMixin, CreateView):
    # Início da docstring da view de criação de tenant
    """
    O QUE FAZ: Provisionamento e cadastro de nova Loja (Tenant) no Hub.
    POR QUE FAZ: Cria a raiz de isolamento do novo inquilino e provisiona os módulos padrão do sistema.
    PERMISSÕES RBAC: Exclusivo para perfil DEV (RF-01 / RN-07).
    MULTI-TENANCY: Ponto de entrada de um novo tenant.
    """
    # Fim do bloco descritivo

    # Modelo ORM alvo da criação
    model = Loja

    # Classe de formulário utilizada para validação e montagem dos campos
    form_class = LojaForm

    # Template HTML contendo os campos cadastrais da loja
    template_name = 'tenancy/loja_form.html'

    # URL de redirecionamento após a persistência bem-sucedida
    success_url = reverse_lazy('loja_list')

    # Trata a validação do formulário persistindo a loja e provisionando os módulos padrão de forma atômica
    def form_valid(self, form):
        # Executa em bloco transacional atômico para garantir integridade caso o provisionamento de módulos falhe
        with transaction.atomic():
            # Persiste o novo registro de Loja
            response = super().form_valid(form)
            # Garante que todos os módulos do sistema sejam criados para a nova loja
            self.object.garantir_modulos_padrao()

        # Emite notificação de sucesso para a interface
        messages.success(
            self.request,
            f"Loja '{self.object.nome}' cadastrada e provisionada com sucesso!"
        )
        return response

    # Injeta flag indicando que a tela opera em modo de inserção (novo registro)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


# View responsável pela edição cadastral de um tenant existente
class LojaUpdateView(DevRequiredMixin, UpdateView):
    # Início da docstring descritiva
    """
    O QUE FAZ: Edição dos dados cadastrais da Loja.
    POR QUE FAZ: Manutenção cadastral do tenant pelo operador DEV.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Manutenção do tenant.
    """
    # Fim da docstring informativa

    # Modelo ORM gerenciado
    model = Loja

    # Formulário utilizado para edição
    form_class = LojaForm

    # Identificação do registro via campo slug
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    # Template HTML compartilhado para o formulário de loja
    template_name = 'tenancy/loja_form.html'

    # Redirecionamento após salvar alterações
    success_url = reverse_lazy('loja_list')

    # Emite mensagem de sucesso após a gravação das alterações
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Dados da loja '{self.object.nome}' atualizados com sucesso!"
        )
        return response

    # Injeta a instância da loja e flag de modo de edição no contexto do template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['loja'] = self.object
        return context


# View para visualização aprofundada dos dados, usuários e status de módulos de uma loja específica
class LojaDetailView(DevRequiredMixin, DetailView):
    # Início da docstring descritiva da view de detalhes
    """
    O QUE FAZ: Exibição detalhada de informações do tenant, usuários vinculados e status dos módulos.
    POR QUE FAZ: Painel consolidado da Loja para auditoria por DEV.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Visão completa de um inquilino.
    """
    # Fim do bloco descritivo

    # Modelo ORM alvo
    model = Loja

    # Busca o tenant pelo parâmetro slug informado na rota
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    # Template HTML da tela de auditoria da loja
    template_name = 'tenancy/loja_detail.html'

    # Nome da variável da loja no template
    context_object_name = 'loja'

    # Injeta no contexto os módulos provisionados e a lista de operadores vinculados à loja
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Assegura que todos os módulos padrão existam para visualização
        self.object.garantir_modulos_padrao()
        # Carrega os módulos da loja ordenados alfabeticamente
        context['modulos'] = self.object.modulos.all().order_by('modulo')
        # Carrega os usuários da loja com junção (select_related) para otimização de queries
        context['usuarios'] = self.object.usuarios.select_related('usuario').all()
        return context


# View para gestão e alternância individual das feature flags de módulos de um tenant
class LojaModulosView(DevRequiredMixin, FormView):
    # Início da docstring da view de alternância de feature flags
    """
    O QUE FAZ: Painel visual para o usuário DEV alternar individualmente as Feature Flags de módulos por Loja.
    POR QUE FAZ: Permite ativar/revogar módulos (Catálogo, Pedidos, Marketplaces, Financeiro) de forma granular e reativa por tenant.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Controle de acesso a nível de loja.
    """
    # Fim da docstring explicativa

    # Template HTML da tela de feature flags
    template_name = 'tenancy/loja_modulos.html'

    # Formulário especialista com os checkboxes dinâmicos de módulos
    form_class = LojaModulosForm

    # Intercepta o despacho para carregar previamente a instância de Loja a partir do slug
    def dispatch(self, request, *args, **kwargs):
        self.loja = get_object_or_404(Loja, slug=self.kwargs['slug'])
        return super().dispatch(request, *args, **kwargs)

    # Injeta a instância da loja nos argumentos de inicialização do LojaModulosForm
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['loja'] = self.loja
        return kwargs

    # Salva o novo estado das feature flags e redireciona de volta para a visualização detalhada do tenant
    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            f"Módulos e Feature Flags da loja '{self.loja.nome}' atualizados com sucesso!"
        )
        return redirect('loja_detail', slug=self.loja.slug)

    # Disponibiliza a loja no contexto do template para exibição de cabeçalhos e títulos
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['loja'] = self.loja
        return context


# ==============================================================================
# GESTÃO DE USUÁRIOS COM RBAC E MULTI-TENANT (RF-02)
# ==============================================================================

# View para listagem e filtragem de operadores com isolamento rigoroso por organização tenant
class UsuarioListView(UserListAccessMixin, ListView):
    # Início do bloco de docstring que documenta o isolamento multi-tenant de usuários
    """
    O QUE FAZ: Listagem de Usuários com isolamento multi-tenant estrito.
    POR QUE FAZ: DEV visualiza todos os usuários; ADMIN e SUPERVISOR visualizam apenas usuários de sua loja; USUARIO é bloqueado.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Filtro mandatário por loja do usuário não-DEV.
    """
    # Fim da docstring explicativa

    # Modelo ORM alvo
    model = User

    # Template HTML para a listagem de usuários
    template_name = 'tenancy/usuario_list.html'

    # Nome da lista de usuários no template
    context_object_name = 'usuarios'

    # Quantidade de usuários por página
    paginate_by = 20

    # Monta a consulta de usuários aplicando isolamento multi-tenant e filtros por papel e status
    def get_queryset(self):
        user = self.request.user
        # Pré-carrega o perfil e a loja via select_related para evitar overhead de banco
        queryset = User.objects.select_related('perfil', 'perfil__loja').order_by('-date_joined')

        # Se for operador DEV global, permite navegar por todos os usuários ou filtrar por loja opcional
        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(perfil__loja_id=loja_id)
        # Para usuários de loja (ADMIN, SUPERVISOR), restringe estritamente aos membros da mesma loja
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return User.objects.none()
            queryset = queryset.filter(perfil__loja=perfil.loja)

        # Filtro opcional por papel hierárquico (DEV, ADMIN, SUPERVISOR, USUARIO)
        papel_filtro = self.request.GET.get('papel', '').strip()
        if papel_filtro:
            queryset = queryset.filter(perfil__papel=papel_filtro)

        # Filtro opcional por status ativo ou inativo
        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro == 'ativo':
            queryset = queryset.filter(is_active=True)
        elif status_filtro == 'inativo':
            queryset = queryset.filter(is_active=False)

        # Busca textual por nome de login, primeiro nome, sobrenome ou e-mail
        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(username__icontains=busca) |
                Q(first_name__icontains=busca) |
                Q(last_name__icontains=busca) |
                Q(email__icontains=busca)
            )

        # Retorna o queryset filtrado
        return queryset

    # Complementa o contexto de renderização com indicadores de papel e opções de filtros
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Flags booleanas para controle condicional de botões e ações no template
        context['is_dev'] = usuario_is_dev(user)
        context['is_admin'] = usuario_is_admin(user)
        context['is_supervisor'] = getattr(user, 'perfil', None) and user.perfil.is_supervisor
        context['pode_gerenciar'] = pode_gerenciar_usuarios(user)

        # Preserva parâmetros de filtros preenchidos na interface
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['papel_filtro'] = self.request.GET.get('papel', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        # Disponibiliza as escolhas de papéis RBAC para o dropdown de filtro
        context['papeis_disponiveis'] = PapelUsuarioEnum.choices

        # Disponibiliza a lista de lojas apenas para desenvolvedores globais
        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


# View responsável pela criação de novo usuário e respectivo perfil RBAC
class UsuarioCreateView(UserWriteAccessMixin, FormView):
    # Início da docstring da view de criação de usuário
    """
    O QUE FAZ: Cadastro de novo usuário e perfil no Hub.
    POR QUE FAZ: Permite que DEV e ADMIN criem usuários respeitando matriz RBAC e tenant bounds.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Vínculo compulsório de loja para não-DEV.
    """
    # Fim da docstring informativa

    # Formulário especialista que cria o User e o PerfilUsuario
    form_class = UsuarioCreateForm

    # Template HTML do formulário de usuário
    template_name = 'tenancy/usuario_form.html'

    # Redirecionamento após o cadastro com sucesso
    success_url = reverse_lazy('usuario_list')

    # Repassa o operador autenticado (autor) para o formulário validar regras hierárquicas RBAC
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    # Salva o usuário e perfil de forma transacional atômica
    def form_valid(self, form):
        with transaction.atomic():
            novo_usuario = form.save()
        messages.success(
            self.request,
            f"Usuário '{novo_usuario.username}' cadastrado com sucesso!"
        )
        return super().form_valid(form)

    # Injeta flag indicando formulário de criação (modo de inserção)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


# View para edição cadastral e alteração de papel de usuário com verificação de posse (ownership)
class UsuarioUpdateView(UserWriteAccessMixin, UserOwnershipCheckMixin, UpdateView):
    # Início do bloco de docstring
    """
    O QUE FAZ: Edição cadastral e alteração de papel de usuário com Ownership Check estrito.
    POR QUE FAZ: Garante que um ADMIN altere apenas subordinados de sua própria loja.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da docstring explicativa

    # Modelo ORM alvo da atualização
    model = User

    # Formulário utilizado para edição
    form_class = UsuarioUpdateForm

    # Template HTML do formulário de usuário
    template_name = 'tenancy/usuario_form.html'

    # Destino do redirecionamento após salvar
    success_url = reverse_lazy('usuario_list')

    # Repassa o operador autenticado (autor) para o formulário
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    # Emite mensagem de sucesso após salvar as modificações do usuário
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Dados do usuário '{self.object.username}' atualizados com sucesso!"
        )
        return response

    # Injeta flag de modo de edição e a instância do usuário alvo no contexto
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['usuario_alvo'] = self.object
        return context


# View responsável pela ativação ou inativação rápida de uma conta de usuário
class UsuarioToggleStatusView(UserWriteAccessMixin, View):
    # Início do bloco de docstring
    """
    O QUE FAZ: Ativação / Desativação rápida de usuário com validação de Ownership.
    POR QUE FAZ: Permite bloquear acesso de subordinados sem exclusão de dados.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da docstring informativa

    # Trata requisição POST para alternar o status booleano is_active do usuário
    def post(self, request, pk, *args, **kwargs):
        # Carrega o usuário alvo com seu perfil e loja
        usuario_alvo = get_object_or_404(User.objects.select_related('perfil', 'perfil__loja'), pk=pk)

        # Valida se o operador atual possui autorização hierárquica e de tenant sobre a conta alvo
        if not pode_editar_usuario(request.user, usuario_alvo):
            raise PermissionDenied("Acesso negado: você não possui permissão para alterar o status deste usuário.")

        # Trava de segurança: impede que qualquer operador inative a sua própria conta
        if request.user == usuario_alvo:
            messages.error(request, "Você não pode desativar a sua própria conta.")
            return redirect('usuario_list')

        # Inverte o status de ativação
        novo_status = not usuario_alvo.is_active
        usuario_alvo.is_active = novo_status
        usuario_alvo.save()

        # Notifica o operador sobre a alteração realizada
        status_str = "ativado" if novo_status else "desativado"
        messages.success(request, f"Usuário '{usuario_alvo.username}' foi {status_str} com sucesso.")
        return redirect('usuario_list')


# View para redefinição administrativa de senha de operadores subordinados por gestores
class UsuarioPasswordResetAdminView(UserWriteAccessMixin, FormView):
    # Início da docstring da view de redefinição de senha
    """
    O QUE FAZ: Redefinição de senha de usuário subordinado por DEV ou ADMIN.
    POR QUE FAZ: Suporte operacional e recuperação de acesso local.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Restrito à própria loja para ADMIN.
    """
    # Fim do bloco descritivo

    # Formulário especialista com campos de nova senha e confirmação
    form_class = UsuarioPasswordResetAdminForm

    # Template HTML da tela de redefinição de senha
    template_name = 'tenancy/usuario_password_reset.html'

    # Destino do redirecionamento após a redefinição com êxito
    success_url = reverse_lazy('usuario_list')

    # Intercepta o despacho para carregar o usuário alvo e validar permissões de edição
    def dispatch(self, request, *args, **kwargs):
        self.usuario_alvo = get_object_or_404(
            User.objects.select_related('perfil', 'perfil__loja'), pk=self.kwargs['pk']
        )
        # Bloqueia se o gestor não tiver autorização sobre o subordinado
        if not pode_editar_usuario(request.user, self.usuario_alvo):
            raise PermissionDenied("Acesso negado: você não possui permissão para alterar a senha deste usuário.")
        return super().dispatch(request, *args, **kwargs)

    # Persiste o novo hash de senha no usuário alvo
    def form_valid(self, form):
        form.save(self.usuario_alvo)
        messages.success(
            self.request,
            f"Senha do usuário '{self.usuario_alvo.username}' redefinida com sucesso!"
        )
        return super().form_valid(form)

    # Injeta a instância do usuário alvo no contexto para exibição de nome e dados na página
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario_alvo'] = self.usuario_alvo
        return context
