from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.core.exceptions import PermissionDenied

from .models import Loja, PerfilUsuario, LogAuditoria
from .enums import PapelUsuarioEnum, EventoAuditoriaEnum
from .forms import LojaForm, UsuarioCreateForm, UsuarioUpdateForm, UsuarioPasswordResetAdminForm
from .permissions import (
    DevRequiredMixin, UserListAccessMixin, UserWriteAccessMixin, UserOwnershipCheckMixin,
    usuario_is_dev, usuario_is_admin, pode_visualizar_usuarios, pode_gerenciar_usuarios,
    pode_editar_usuario
)


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    """
    Visão geral inicial da plataforma, adaptada dinamicamente conforme o papel do usuário.
    """
    template_name = 'core/home.html'

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

        return context


# ==============================================================================
# GESTÃO DE LOJAS (TENANTS) — EXCLUSIVO DEV (RF-01)
# ==============================================================================

class LojaListView(DevRequiredMixin, ListView):
    """
    Listagem de todas as Lojas (Tenants) cadastradas. Exclusivo para perfil DEV.
    """
    model = Loja
    template_name = 'core/loja_list.html'
    context_object_name = 'lojas'
    paginate_by = 15

    def get_queryset(self):
        queryset = Loja.objects.annotate(total_usuarios=Count('usuarios')).order_by('-criado_em')
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
    Tela de provisionamento e cadastro de nova Loja (Tenant) no Hub.
    Restrita exclusivamente ao perfil DEV (RF-01 / RN-07).
    """
    model = Loja
    form_class = LojaForm
    template_name = 'core/loja_form.html'
    success_url = reverse_lazy('loja_list')

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            LogAuditoria.objects.create(
                loja=self.object,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.CRIACAO_LOJA,
                detalhes=f"Loja '{self.object.nome}' (CNPJ: {self.object.cnpj}) provisionada no Hub.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
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
    Tela de edição dos dados cadastrais e credenciais da Loja.
    Restrita exclusivamente ao perfil DEV.
    """
    model = Loja
    form_class = LojaForm
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'core/loja_form.html'
    success_url = reverse_lazy('loja_list')

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            LogAuditoria.objects.create(
                loja=self.object,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EDICAO_LOJA,
                detalhes=f"Dados cadastrais da loja '{self.object.nome}' atualizados.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
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
    Exibição completa das informações cadastrais, status e credenciais de uma Loja.
    """
    model = Loja
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'core/loja_detail.html'
    context_object_name = 'loja'


# ==============================================================================
# GESTÃO DE USUÁRIOS COM RBAC E MULTI-TENANT (RF-02)
# ==============================================================================

class UsuarioListView(UserListAccessMixin, ListView):
    """
    Listagem de Usuários com isolamento multi-tenant estrito:
    - DEV: Visualiza todos os usuários de todos os tenants (cross-tenant) com filtros por loja e papel.
    - ADMIN e SUPERVISOR: Visualizam apenas os usuários vinculados à sua própria loja (single-tenant).
    - USUARIO: Bloqueado via UserListAccessMixin (403 Forbidden).
    """
    model = User
    template_name = 'core/usuario_list.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.select_related('perfil', 'perfil__loja').order_by('-date_joined')

        # Isolamento Multi-Tenant compulsório no Backend
        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(perfil__loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return User.objects.none()
            queryset = queryset.filter(perfil__loja=perfil.loja)

        # Filtros adicionais (Papel, Status e Busca Textual)
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
        
        # Filtros contextuais
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
    Cadastro de novo usuário no Hub.
    - DEV: Cria qualquer papel para qualquer loja (ou global).
    - ADMIN: Cria apenas SUPERVISOR e USUARIO para a sua própria loja.
    - SUPERVISOR: Bloqueado (Read-Only).
    - USUARIO: Bloqueado (No-Access).
    """
    form_class = UsuarioCreateForm
    template_name = 'core/usuario_form.html'
    success_url = reverse_lazy('usuario_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            novo_usuario = form.save()
            loja_nome = novo_usuario.perfil.loja.nome if novo_usuario.perfil.loja else "Global"
            
            # Registro compulsório em LogAuditoria
            LogAuditoria.objects.create(
                loja=novo_usuario.perfil.loja,
                autor=self.request.user,
                usuario_afetado=novo_usuario,
                evento=EventoAuditoriaEnum.CRIACAO_USUARIO,
                detalhes=(
                    f"Usuário '{novo_usuario.username}' cadastrado com o papel "
                    f"'{novo_usuario.perfil.get_papel_display()}' na loja '{loja_nome}'."
                ),
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

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
    Edição cadastral e de papel RBAC de usuário com Ownership Check estrito.
    """
    model = User
    form_class = UsuarioUpdateForm
    template_name = 'core/usuario_form.html'
    success_url = reverse_lazy('usuario_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        usuario_antigo = User.objects.get(pk=self.object.pk)
        perfil_antigo_papel = usuario_antigo.perfil.papel if hasattr(usuario_antigo, 'perfil') else None
        
        with transaction.atomic():
            usuario_atualizado = form.save()
            perfil_novo_papel = usuario_atualizado.perfil.papel if hasattr(usuario_atualizado, 'perfil') else None

            # Detecta se houve troca de papel
            if perfil_antigo_papel != perfil_novo_papel:
                evento = EventoAuditoriaEnum.TROCA_PAPEL
                detalhes = (
                    f"Papel do usuário '{usuario_atualizado.username}' alterado de "
                    f"'{perfil_antigo_papel}' para '{perfil_novo_papel}'."
                )
            else:
                evento = EventoAuditoriaEnum.EDICAO_USUARIO
                detalhes = f"Dados cadastrais do usuário '{usuario_atualizado.username}' atualizados."

            LogAuditoria.objects.create(
                loja=usuario_atualizado.perfil.loja if hasattr(usuario_atualizado, 'perfil') else None,
                autor=self.request.user,
                usuario_afetado=usuario_atualizado,
                evento=evento,
                detalhes=detalhes,
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        messages.success(
            self.request,
            f"Dados do usuário '{usuario_atualizado.username}' atualizados com sucesso!"
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['usuario_alvo'] = self.object
        return context


class UsuarioToggleStatusView(UserWriteAccessMixin, View):
    """
    Ativação / Desativação rápida de usuário com validação de Ownership.
    """
    def post(self, request, pk, *args, **kwargs):
        usuario_alvo = get_object_or_404(User.objects.select_related('perfil', 'perfil__loja'), pk=pk)

        # Validação de Ownership e Hierarquia
        if not pode_editar_usuario(request.user, usuario_alvo):
            raise PermissionDenied("Acesso negado: você não possui permissão para alterar o status deste usuário.")

        if request.user == usuario_alvo:
            messages.error(request, "Você não pode desativar a sua própria conta.")
            return redirect('usuario_list')

        with transaction.atomic():
            novo_status = not usuario_alvo.is_active
            usuario_alvo.is_active = novo_status
            usuario_alvo.save()

            status_str = "ativado" if novo_status else "desativado"
            LogAuditoria.objects.create(
                loja=usuario_alvo.perfil.loja if hasattr(usuario_alvo, 'perfil') else None,
                autor=request.user,
                usuario_afetado=usuario_alvo,
                evento=EventoAuditoriaEnum.STATUS_USUARIO,
                detalhes=f"Usuário '{usuario_alvo.username}' foi {status_str}.",
                ip_origem=request.META.get('REMOTE_ADDR')
            )

        messages.success(request, f"Usuário '{usuario_alvo.username}' foi {status_str} com sucesso.")
        return redirect('usuario_list')


class UsuarioPasswordResetAdminView(UserWriteAccessMixin, FormView):
    """
    Redefinição de senha de usuário subordinado por DEV ou ADMIN.
    """
    form_class = UsuarioPasswordResetAdminForm
    template_name = 'core/usuario_password_reset.html'
    success_url = reverse_lazy('usuario_list')

    def dispatch(self, request, *args, **kwargs):
        self.usuario_alvo = get_object_or_404(
            User.objects.select_related('perfil', 'perfil__loja'), pk=self.kwargs['pk']
        )
        if not pode_editar_usuario(request.user, self.usuario_alvo):
            raise PermissionDenied("Acesso negado: você não possui permissão para alterar a senha deste usuário.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            form.save(self.usuario_alvo)
            LogAuditoria.objects.create(
                loja=self.usuario_alvo.perfil.loja if hasattr(self.usuario_alvo, 'perfil') else None,
                autor=self.request.user,
                usuario_afetado=self.usuario_alvo,
                evento=EventoAuditoriaEnum.RESET_SENHA,
                detalhes=f"Senha do usuário '{self.usuario_alvo.username}' foi redefinida por um administrador.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        messages.success(
            self.request,
            f"Senha do usuário '{self.usuario_alvo.username}' redefinida com sucesso!"
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario_alvo'] = self.usuario_alvo
        return context


