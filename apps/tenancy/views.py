# Os códigos foram gerados com auxilio de I.A.
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DetailView, FormView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.core.exceptions import PermissionDenied

from .models import Loja, PerfilUsuario, ModuloLoja
from .enums import PapelUsuarioEnum, ModuloSistemaEnum
from .forms import (
    LojaForm, LojaModulosForm, UsuarioCreateForm, UsuarioUpdateForm,
    UsuarioPasswordResetAdminForm
)
from .permissions import (
    DevRequiredMixin, UserListAccessMixin, UserWriteAccessMixin, UserOwnershipCheckMixin,
    usuario_is_dev, usuario_is_admin, pode_visualizar_usuarios, pode_gerenciar_usuarios,
    pode_editar_usuario
)


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    """
    O QUE FAZ: Visão geral e dashboard inicial do Hub Central.
    POR QUE FAZ: Apresenta KPIs e resumo operacional adaptados dinamicamente ao papel do usuário e aos módulos ativos de sua loja.
    PERMISSÕES RBAC: Todos os usuários autenticados.
    MULTI-TENANCY: DEV visualiza totais globais do sistema; demais usuários visualizam dados exclusivos de sua loja.
    """
    template_name = 'tenancy/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)

        if context['is_dev']:
            context['total_lojas'] = Loja.objects.count()
            context['lojas_ativas'] = Loja.objects.filter(ativo=True).count()
            context['ultimas_lojas'] = Loja.objects.order_by('-criado_em')[:5]
            context['total_usuarios'] = User.objects.count()
        else:
            perfil = getattr(user, 'perfil', None)
            context['perfil'] = perfil
            context['minha_loja'] = perfil.loja if perfil else None
            if perfil and perfil.loja:
                context['total_usuarios_loja'] = User.objects.filter(perfil__loja=perfil.loja).count()
                context['modulos_loja'] = perfil.loja.modulos.all()

        return context


# ==============================================================================
# GESTÃO DE LOJAS (TENANTS) & FEATURE FLAGS — EXCLUSIVO DEV (RF-01)
# ==============================================================================

class LojaListView(DevRequiredMixin, ListView):
    """
    O QUE FAZ: Listagem geral de todas as Lojas (Tenants) cadastradas no Hub.
    POR QUE FAZ: Permite ao operador DEV auditar, gerenciar e navegar entre os tenants da plataforma.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Visão global agregada.
    """
    model = Loja
    template_name = 'tenancy/loja_list.html'
    context_object_name = 'lojas'
    paginate_by = 15

    def get_queryset(self):
        queryset = Loja.objects.annotate(
            total_usuarios=Count('usuarios'),
            total_modulos_ativos=Count('modulos', filter=Q(modulos__ativo=True))
        ).order_by('-criado_em')

        termo_busca = self.request.GET.get('q', '').strip()
        status_filtro = self.request.GET.get('status', '').strip()

        if termo_busca:
            queryset = queryset.filter(
                Q(nome__icontains=termo_busca) |
                Q(cnpj__icontains=termo_busca) |
                Q(cidade__icontains=termo_busca) |
                Q(email__icontains=termo_busca)
            )

        if status_filtro == 'ativo':
            queryset = queryset.filter(ativo=True)
        elif status_filtro == 'inativo':
            queryset = queryset.filter(ativo=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['total_cadastradas'] = Loja.objects.count()
        context['total_ativas'] = Loja.objects.filter(ativo=True).count()
        return context


class LojaCreateView(DevRequiredMixin, CreateView):
    """
    O QUE FAZ: Provisionamento e cadastro de nova Loja (Tenant) no Hub.
    POR QUE FAZ: Cria a raiz de isolamento do novo inquilino e provisiona os módulos padrão do sistema.
    PERMISSÕES RBAC: Exclusivo para perfil DEV (RF-01 / RN-07).
    MULTI-TENANCY: Ponto de entrada de um novo tenant.
    """
    model = Loja
    form_class = LojaForm
    template_name = 'tenancy/loja_form.html'
    success_url = reverse_lazy('loja_list')

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.garantir_modulos_padrao()
        messages.success(
            self.request,
            f"Loja '{self.object.nome}' cadastrada e provisionada com sucesso!"
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


class LojaUpdateView(DevRequiredMixin, UpdateView):
    """
    O QUE FAZ: Edição dos dados cadastrais da Loja.
    POR QUE FAZ: Manutenção cadastral do tenant pelo operador DEV.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Manutenção do tenant.
    """
    model = Loja
    form_class = LojaForm
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'tenancy/loja_form.html'
    success_url = reverse_lazy('loja_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Dados da loja '{self.object.nome}' atualizados com sucesso!"
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['loja'] = self.object
        return context


class LojaDetailView(DevRequiredMixin, DetailView):
    """
    O QUE FAZ: Exibição detalhada de informações do tenant, usuários vinculados e status dos módulos.
    POR QUE FAZ: Painel consolidado da Loja para auditoria por DEV.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Visão completa de um inquilino.
    """
    model = Loja
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'tenancy/loja_detail.html'
    context_object_name = 'loja'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.garantir_modulos_padrao()
        context['modulos'] = self.object.modulos.all().order_by('modulo')
        context['usuarios'] = self.object.usuarios.select_related('usuario').all()
        return context


class LojaModulosView(DevRequiredMixin, FormView):
    """
    O QUE FAZ: Painel visual para o usuário DEV alternar individualmente as Feature Flags de módulos por Loja.
    POR QUE FAZ: Permite ativar/revogar módulos (Catálogo, Pedidos, Marketplaces, Financeiro) de forma granular e reativa por tenant.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Controle de acesso a nível de loja.
    """
    template_name = 'tenancy/loja_modulos.html'
    form_class = LojaModulosForm

    def dispatch(self, request, *args, **kwargs):
        self.loja = get_object_or_404(Loja, slug=self.kwargs['slug'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['loja'] = self.loja
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            f"Módulos e Feature Flags da loja '{self.loja.nome}' atualizados com sucesso!"
        )
        return redirect('loja_detail', slug=self.loja.slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['loja'] = self.loja
        return context


# ==============================================================================
# GESTÃO DE USUÁRIOS COM RBAC E MULTI-TENANT (RF-02)
# ==============================================================================

class UsuarioListView(UserListAccessMixin, ListView):
    """
    O QUE FAZ: Listagem de Usuários com isolamento multi-tenant estrito.
    POR QUE FAZ: DEV visualiza todos os usuários; ADMIN e SUPERVISOR visualizam apenas usuários de sua loja; USUARIO é bloqueado.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Filtro mandatário por loja do usuário não-DEV.
    """
    model = User
    template_name = 'tenancy/usuario_list.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.select_related('perfil', 'perfil__loja').order_by('-date_joined')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(perfil__loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return User.objects.none()
            queryset = queryset.filter(perfil__loja=perfil.loja)

        papel_filtro = self.request.GET.get('papel', '').strip()
        if papel_filtro:
            queryset = queryset.filter(perfil__papel=papel_filtro)

        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro == 'ativo':
            queryset = queryset.filter(is_active=True)
        elif status_filtro == 'inativo':
            queryset = queryset.filter(is_active=False)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(username__icontains=busca) |
                Q(first_name__icontains=busca) |
                Q(last_name__icontains=busca) |
                Q(email__icontains=busca)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['is_admin'] = usuario_is_admin(user)
        context['is_supervisor'] = getattr(user, 'perfil', None) and user.perfil.is_supervisor
        context['pode_gerenciar'] = pode_gerenciar_usuarios(user)

        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['papel_filtro'] = self.request.GET.get('papel', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        context['papeis_disponiveis'] = PapelUsuarioEnum.choices
        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


class UsuarioCreateView(UserWriteAccessMixin, FormView):
    """
    O QUE FAZ: Cadastro de novo usuário e perfil no Hub.
    POR QUE FAZ: Permite que DEV e ADMIN criem usuários respeitando matriz RBAC e tenant bounds.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Vínculo compulsório de loja para não-DEV.
    """
    form_class = UsuarioCreateForm
    template_name = 'tenancy/usuario_form.html'
    success_url = reverse_lazy('usuario_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            novo_usuario = form.save()
        messages.success(
            self.request,
            f"Usuário '{novo_usuario.username}' cadastrado com sucesso!"
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


class UsuarioUpdateView(UserWriteAccessMixin, UserOwnershipCheckMixin, UpdateView):
    """
    O QUE FAZ: Edição cadastral e alteração de papel de usuário com Ownership Check estrito.
    POR QUE FAZ: Garante que um ADMIN altere apenas subordinados de sua própria loja.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Isolado por loja.
    """
    model = User
    form_class = UsuarioUpdateForm
    template_name = 'tenancy/usuario_form.html'
    success_url = reverse_lazy('usuario_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Dados do usuário '{self.object.username}' atualizados com sucesso!"
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['usuario_alvo'] = self.object
        return context


class UsuarioToggleStatusView(UserWriteAccessMixin, View):
    """
    O QUE FAZ: Ativação / Desativação rápida de usuário com validação de Ownership.
    POR QUE FAZ: Permite bloquear acesso de subordinados sem exclusão de dados.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Isolado por loja.
    """
    def post(self, request, pk, *args, **kwargs):
        usuario_alvo = get_object_or_404(User.objects.select_related('perfil', 'perfil__loja'), pk=pk)

        if not pode_editar_usuario(request.user, usuario_alvo):
            raise PermissionDenied("Acesso negado: você não possui permissão para alterar o status deste usuário.")

        if request.user == usuario_alvo:
            messages.error(request, "Você não pode desativar a sua própria conta.")
            return redirect('usuario_list')

        novo_status = not usuario_alvo.is_active
        usuario_alvo.is_active = novo_status
        usuario_alvo.save()

        status_str = "ativado" if novo_status else "desativado"
        messages.success(request, f"Usuário '{usuario_alvo.username}' foi {status_str} com sucesso.")
        return redirect('usuario_list')


class UsuarioPasswordResetAdminView(UserWriteAccessMixin, FormView):
    """
    O QUE FAZ: Redefinição de senha de usuário subordinado por DEV ou ADMIN.
    POR QUE FAZ: Suporte operacional e recuperação de acesso local.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Restrito à própria loja para ADMIN.
    """
    form_class = UsuarioPasswordResetAdminForm
    template_name = 'tenancy/usuario_password_reset.html'
    success_url = reverse_lazy('usuario_list')

    def dispatch(self, request, *args, **kwargs):
        self.usuario_alvo = get_object_or_404(
            User.objects.select_related('perfil', 'perfil__loja'), pk=self.kwargs['pk']
        )
        if not pode_editar_usuario(request.user, self.usuario_alvo):
            raise PermissionDenied("Acesso negado: você não possui permissão para alterar a senha deste usuário.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save(self.usuario_alvo)
        messages.success(
            self.request,
            f"Senha do usuário '{self.usuario_alvo.username}' redefinida com sucesso!"
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario_alvo'] = self.usuario_alvo
        return context
