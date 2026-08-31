# Os códigos foram gerados com auxilio de I.A.
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DetailView, FormView, View, DeleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import (
    Loja, PerfilUsuario, LogAuditoria, Categoria, Produto, HistoricoPreco,
    LogSincronizacao, PedidoVenda, ItemPedidoVenda
)
from .enums import (
    PapelUsuarioEnum, EventoAuditoriaEnum, StatusProdutoEnum,
    StatusSincronizacaoEnum, TipoAjusteEstoqueEnum, MarketplaceEnum, StatusPedidoEnum
)
from .forms import (
    LojaForm, UsuarioCreateForm, UsuarioUpdateForm, UsuarioPasswordResetAdminForm,
    CategoriaForm, ProdutoForm, ProdutoBaixaAvariaForm, ProdutoAjusteEstoqueForm,
    LojaIntegracaoMeliForm, ProdutoSincronizacaoLoteForm, ProdutoBroadcastLoteForm
)
from .permissions import (
    DevRequiredMixin, UserListAccessMixin, UserWriteAccessMixin, UserOwnershipCheckMixin,
    CatalogOwnershipCheckMixin, CatalogDeletePermissionMixin,
    IntegracaoConfigPermissionMixin, SyncPermissionMixin,
    usuario_is_dev, usuario_is_admin, pode_visualizar_usuarios, pode_gerenciar_usuarios,
    pode_editar_usuario, pode_alterar_preco, pode_ajustar_estoque_geral,
    pode_excluir_catalogo, pode_dar_baixa_avaria, pode_acessar_objeto_loja,
    pode_configurar_integracao, pode_disparar_sincronizacao
)
from .services import MercadoLivreService, BroadcastEstoqueService


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
            context['total_produtos'] = Produto.objects.count()
            context['total_categorias'] = Categoria.objects.count()
            context['total_logs_sincronizacao'] = LogSincronizacao.objects.count()
            context['total_pedidos'] = PedidoVenda.objects.count()
            context['total_pedidos_ruptura'] = PedidoVenda.objects.filter(teve_ruptura_estoque=True).count()
            context['faturamento_total'] = PedidoVenda.objects.filter(processado_com_sucesso=True).aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
            context['ultimos_pedidos'] = PedidoVenda.objects.select_related('loja').order_by('-criado_em')[:5]
        else:
            perfil = getattr(user, 'perfil', None)
            context['perfil'] = perfil
            context['minha_loja'] = perfil.loja if perfil else None
            if perfil and perfil.loja:
                context['total_usuarios_loja'] = User.objects.filter(perfil__loja=perfil.loja).count()
                context['total_produtos_loja'] = Produto.objects.filter(loja=perfil.loja).count()
                context['total_categorias_loja'] = Categoria.objects.filter(loja=perfil.loja).count()
                context['produtos_sem_estoque'] = Produto.objects.filter(loja=perfil.loja, estoque=0).count()
                context['produtos_estoque_negativo'] = Produto.objects.filter(loja=perfil.loja, estoque__lt=0).count()
                context['produtos_sincronizados'] = Produto.objects.filter(
                    loja=perfil.loja, status_sincronizacao=StatusSincronizacaoEnum.SINCRONIZADO
                ).count()
                context['total_logs_loja'] = LogSincronizacao.objects.filter(loja=perfil.loja).count()
                context['total_pedidos_loja'] = PedidoVenda.objects.filter(loja=perfil.loja).count()
                context['pedidos_ruptura_loja'] = PedidoVenda.objects.filter(loja=perfil.loja, teve_ruptura_estoque=True).count()
                context['faturamento_loja'] = PedidoVenda.objects.filter(loja=perfil.loja, processado_com_sucesso=True).aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
                context['ultimos_pedidos'] = PedidoVenda.objects.filter(loja=perfil.loja).order_by('-criado_em')[:5]

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
    Cadastro de novo usuário no Hub.
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


# ==============================================================================
# GESTÃO DE CATEGORIAS (RF-03 / RN-01)
# ==============================================================================

class CategoriaListView(LoginRequiredMixin, ListView):
    """
    Listagem de Categorias com isolamento multi-tenant.
    """
    model = Categoria
    template_name = 'core/categoria_list.html'
    context_object_name = 'categorias'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Categoria.objects.select_related('loja').annotate(total_produtos=Count('produtos')).order_by('nome')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return Categoria.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro == 'ativo':
            queryset = queryset.filter(ativo=True)
        elif status_filtro == 'inativo':
            queryset = queryset.filter(ativo=False)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(Q(nome__icontains=busca) | Q(slug__icontains=busca))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['pode_excluir'] = pode_excluir_catalogo(user)
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


class CategoriaCreateView(LoginRequiredMixin, CreateView):
    """
    Cadastro de nova Categoria com isolamento multi-tenant.
    """
    model = Categoria
    form_class = CategoriaForm
    template_name = 'core/categoria_form.html'
    success_url = reverse_lazy('categoria_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.CRIACAO_CATEGORIA,
                detalhes=f"Categoria '{self.object.nome}' cadastrada na loja '{self.object.loja.nome}'.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
        messages.success(self.request, f"Categoria '{self.object.nome}' cadastrada com sucesso!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


class CategoriaUpdateView(LoginRequiredMixin, CatalogOwnershipCheckMixin, UpdateView):
    """
    Edição de Categoria com Ownership Check.
    """
    model = Categoria
    form_class = CategoriaForm
    template_name = 'core/categoria_form.html'
    success_url = reverse_lazy('categoria_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EDICAO_CATEGORIA,
                detalhes=f"Categoria '{self.object.nome}' atualizada.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
        messages.success(self.request, f"Categoria '{self.object.nome}' atualizada com sucesso!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        return context


class CategoriaDeleteView(LoginRequiredMixin, CatalogOwnershipCheckMixin, CatalogDeletePermissionMixin, DeleteView):
    """
    Exclusão de Categoria protegida (RN-09).
    """
    model = Categoria
    template_name = 'core/categoria_confirm_delete.html'
    success_url = reverse_lazy('categoria_list')

    def form_valid(self, form):
        if self.object.produtos.exists():
            messages.error(
                self.request,
                f"Não é possível excluir a categoria '{self.object.nome}', pois existem produtos associados a ela."
            )
            return redirect('categoria_list')

        with transaction.atomic():
            cat_nome = self.object.nome
            loja = self.object.loja
            LogAuditoria.objects.create(
                loja=loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EXCLUSAO_CATEGORIA,
                detalhes=f"Categoria '{cat_nome}' excluída da loja '{loja.nome}'.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
            messages.success(self.request, f"Categoria '{cat_nome}' excluída com sucesso.")
            return super().form_valid(form)


# ==============================================================================
# GESTÃO DE PRODUTOS E CATÁLOGO (RF-03 / RN-01 / RN-02 / RN-06 / RN-09)
# ==============================================================================

class ProdutoListView(LoginRequiredMixin, ListView):
    """
    Catálogo de Produtos com isolamento multi-tenant, filtros e badges contextuais.
    """
    model = Produto
    template_name = 'core/produto_list.html'
    context_object_name = 'produtos'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Produto.objects.select_related('loja', 'categoria').order_by('-criado_em')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return Produto.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        # Filtros adicionais
        categoria_id = self.request.GET.get('categoria', '').strip()
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)

        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro:
            queryset = queryset.filter(status=status_filtro)

        sync_filtro = self.request.GET.get('sync', '').strip()
        if sync_filtro:
            queryset = queryset.filter(status_sincronizacao=sync_filtro)

        estoque_filtro = self.request.GET.get('estoque', '').strip()
        if estoque_filtro == 'zerado':
            queryset = queryset.filter(estoque=0)
        elif estoque_filtro == 'disponivel':
            queryset = queryset.filter(estoque__gt=0)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(sku__icontains=busca) |
                Q(nome__icontains=busca) |
                Q(meli_item_id__icontains=busca)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['pode_alterar_preco'] = pode_alterar_preco(user)
        context['pode_ajustar_estoque_geral'] = pode_ajustar_estoque_geral(user)
        context['pode_excluir'] = pode_excluir_catalogo(user)
        context['pode_dar_baixa_avaria'] = pode_dar_baixa_avaria(user)

        # Filtros
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['categoria_filtro'] = self.request.GET.get('categoria', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['sync_filtro'] = self.request.GET.get('sync', '').strip()
        context['estoque_filtro'] = self.request.GET.get('estoque', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        context['status_choices'] = StatusProdutoEnum.choices
        context['sync_choices'] = StatusSincronizacaoEnum.choices

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
            context['categorias_disponiveis'] = Categoria.objects.filter(ativo=True).order_by('nome')
        else:
            loja = getattr(user.perfil, 'loja', None)
            context['minha_loja'] = loja
            context['categorias_disponiveis'] = Categoria.objects.filter(loja=loja, ativo=True).order_by('nome') if loja else []

        return context


class ProdutoCreateView(LoginRequiredMixin, CreateView):
    """
    Cadastro de novo Produto com controle de preço por perfil e registro em HistoricoPreco.
    """
    model = Produto
    form_class = ProdutoForm
    template_name = 'core/produto_form.html'
    success_url = reverse_lazy('produto_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            
            # Se cadastrado com preço > 0, cria o primeiro registro de HistoricoPreco
            if self.object.preco > Decimal('0.00'):
                HistoricoPreco.objects.create(
                    produto=self.object,
                    loja=self.object.loja,
                    preco_anterior=Decimal('0.00'),
                    preco_novo=self.object.preco,
                    usuario=self.request.user,
                    motivo="Preço de lançamento / Cadastro inicial"
                )

            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.CRIACAO_PRODUTO,
                detalhes=(
                    f"Produto '{self.object.nome}' (SKU: {self.object.sku}) cadastrado "
                    f"com preço R$ {self.object.preco} e estoque {self.object.estoque} na loja '{self.object.loja.nome}'."
                ),
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        messages.success(self.request, f"Produto '{self.object.nome}' (SKU: {self.object.sku}) cadastrado com sucesso!")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


class ProdutoUpdateView(LoginRequiredMixin, CatalogOwnershipCheckMixin, UpdateView):
    """
    Edição de Produto com Ownership Check, detecção de alteração de preço e gravação em HistoricoPreco.
    """
    model = Produto
    form_class = ProdutoForm
    template_name = 'core/produto_form.html'
    success_url = reverse_lazy('produto_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        produto_antigo = Produto.objects.get(pk=self.object.pk)
        preco_anterior = produto_antigo.preco
        estoque_anterior = produto_antigo.estoque

        with transaction.atomic():
            self.object = form.save()
            
            # Se o preço foi alterado, registra em HistoricoPreco
            if preco_anterior != self.object.preco:
                HistoricoPreco.objects.create(
                    produto=self.object,
                    loja=self.object.loja,
                    preco_anterior=preco_anterior,
                    preco_novo=self.object.preco,
                    usuario=self.request.user,
                    motivo="Alteração de preço manual pelo painel administrativo"
                )
                LogAuditoria.objects.create(
                    loja=self.object.loja,
                    autor=self.request.user,
                    evento=EventoAuditoriaEnum.ALTERACAO_PRECO,
                    detalhes=f"Preço do produto '{self.object.sku}' alterado de R$ {preco_anterior} para R$ {self.object.preco}.",
                    ip_origem=self.request.META.get('REMOTE_ADDR')
                )

            # Se estoque foi alterado diretamente na edição geral
            if estoque_anterior != self.object.estoque:
                LogAuditoria.objects.create(
                    loja=self.object.loja,
                    autor=self.request.user,
                    evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                    detalhes=f"Estoque do produto '{self.object.sku}' alterado de {estoque_anterior} para {self.object.estoque}.",
                    ip_origem=self.request.META.get('REMOTE_ADDR')
                )

            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EDICAO_PRODUTO,
                detalhes=f"Dados cadastrais do produto '{self.object.nome}' (SKU: {self.object.sku}) atualizados.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        messages.success(self.request, f"Produto '{self.object.nome}' atualizado com sucesso!")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['produto'] = self.object
        return context


class ProdutoDetailView(LoginRequiredMixin, CatalogOwnershipCheckMixin, DetailView):
    """
    Visualização detalhada do Produto, com histórico de preços e registros de movimentações.
    """
    model = Produto
    template_name = 'core/produto_detail.html'
    context_object_name = 'produto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['pode_alterar_preco'] = pode_alterar_preco(user)
        context['pode_ajustar_estoque_geral'] = pode_ajustar_estoque_geral(user)
        context['pode_excluir'] = pode_excluir_catalogo(user)
        context['pode_dar_baixa_avaria'] = pode_dar_baixa_avaria(user)
        context['historicos_preco'] = self.object.historico_precos.select_related('usuario').order_by('-criado_em')
        return context


class ProdutoDeleteView(LoginRequiredMixin, CatalogOwnershipCheckMixin, CatalogDeletePermissionMixin, DeleteView):
    """
    Exclusão de Produto (RN-09). Bloqueia USUARIO com 403 Forbidden.
    """
    model = Produto
    template_name = 'core/produto_confirm_delete.html'
    success_url = reverse_lazy('produto_list')

    def form_valid(self, form):
        with transaction.atomic():
            sku = self.object.sku
            nome = self.object.nome
            loja = self.object.loja
            LogAuditoria.objects.create(
                loja=loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EXCLUSAO_PRODUTO,
                detalhes=f"Produto '{nome}' (SKU: {sku}) excluído do catálogo da loja '{loja.nome}'.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
            messages.success(self.request, f"Produto '{nome}' (SKU: {sku}) excluído com sucesso.")
            return super().form_valid(form)


class ProdutoBaixaEstoqueView(LoginRequiredMixin, FormView):
    """
    Ação dedicada para Baixa Pontual de Estoque por Avaria ou Perda (RN-09).
    Disponível para todos os perfis da loja (incluindo USUARIO).
    """
    form_class = ProdutoBaixaAvariaForm
    template_name = 'core/produto_baixa_estoque.html'
    success_url = reverse_lazy('produto_list')

    def dispatch(self, request, *args, **kwargs):
        self.produto = get_object_or_404(
            Produto.objects.select_related('loja'), pk=self.kwargs['pk']
        )
        if not pode_acessar_objeto_loja(request.user, self.produto):
            raise PermissionDenied("Acesso negado: este produto pertence a outra loja.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['produto'] = self.produto
        return kwargs

    def form_valid(self, form):
        quantidade = form.cleaned_data['quantidade']
        tipo_baixa = form.cleaned_data['tipo_baixa']
        justificativa = form.cleaned_data['justificativa']

        with transaction.atomic():
            estoque_antigo = self.produto.estoque
            self.produto.estoque -= quantidade
            self.produto.save()

            tipo_baixa_nome = dict(form.fields['tipo_baixa'].choices).get(tipo_baixa, tipo_baixa)
            LogAuditoria.objects.create(
                loja=self.produto.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.BAIXA_AVARIA_ESTOQUE,
                detalhes=(
                    f"Baixa de {quantidade} un. no produto '{self.produto.sku}' "
                    f"(Saldo anterior: {estoque_antigo} -> Novo saldo: {self.produto.estoque}). "
                    f"Motivo: {tipo_baixa_nome}. Justificativa: '{justificativa}'."
                ),
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

            # RF-08: Dispara Broadcast Multi-Canal após baixa de avaria
            BroadcastEstoqueService.disparar_broadcast_produto(
                self.produto, usuario=self.request.user
            )

        messages.success(
            self.request,
            f"Baixa de {quantidade} unidade(s) registrada com sucesso para o produto '{self.produto.sku}'!"
        )
        return redirect(reverse('produto_detail', kwargs={'pk': self.produto.pk}))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['produto'] = self.produto
        return context


class ProdutoAjusteEstoqueView(LoginRequiredMixin, FormView):
    """
    Ajuste geral de saldo físico de estoque por gestores (DEV, ADMIN, SUPERVISOR).
    Bloqueia USUARIO com 403 Forbidden (RN-09).
    """
    form_class = ProdutoAjusteEstoqueForm
    template_name = 'core/produto_ajuste_estoque.html'
    success_url = reverse_lazy('produto_list')

    def dispatch(self, request, *args, **kwargs):
        if not pode_ajustar_estoque_geral(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não possui permissão para realizar ajustes gerais de estoque.")
        
        self.produto = get_object_or_404(
            Produto.objects.select_related('loja'), pk=self.kwargs['pk']
        )
        if not pode_acessar_objeto_loja(request.user, self.produto):
            raise PermissionDenied("Acesso negado: este produto pertence a outra loja.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        novo_estoque = form.cleaned_data['novo_estoque']
        tipo_ajuste = form.cleaned_data['tipo_ajuste']
        justificativa = form.cleaned_data['justificativa']

        with transaction.atomic():
            estoque_antigo = self.produto.estoque
            self.produto.estoque = novo_estoque
            self.produto.save()

            tipo_ajuste_nome = dict(form.fields['tipo_ajuste'].choices).get(tipo_ajuste, tipo_ajuste)
            LogAuditoria.objects.create(
                loja=self.produto.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                detalhes=(
                    f"Ajuste manual de estoque no produto '{self.produto.sku}': "
                    f"Saldo de {estoque_antigo} para {novo_estoque} un. "
                    f"Tipo: {tipo_ajuste_nome}. Justificativa: '{justificativa}'."
                ),
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

            # RF-08: Dispara Broadcast Multi-Canal após ajuste manual / reposição
            BroadcastEstoqueService.disparar_broadcast_produto(
                self.produto, usuario=self.request.user
            )

        messages.success(
            self.request,
            f"Saldo de estoque do produto '{self.produto.sku}' atualizado para {novo_estoque} un. com sucesso!"
        )
        return redirect(reverse('produto_detail', kwargs={'pk': self.produto.pk}))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['produto'] = self.produto
        return context


# ==============================================================================
# INTEGRAÇÃO COM MERCADO LIVRE (RF-05 / RN-01 / RN-04 / RN-09)
# ==============================================================================

class LojaIntegracaoMeliView(LoginRequiredMixin, IntegracaoConfigPermissionMixin, FormView):
    """
    Tela de configuração e teste das credenciais de integração com a API do Mercado Livre (RF-05).
    Acessível por DEV (qualquer loja) e ADMIN (apenas a sua própria loja).
    SUPERVISOR e USUARIO são bloqueados via IntegracaoConfigPermissionMixin (403 Forbidden).
    """
    form_class = LojaIntegracaoMeliForm
    template_name = 'core/loja_integracao_meli.html'
    success_url = reverse_lazy('loja_integracao_meli')

    def get_loja(self):
        user = self.request.user
        if usuario_is_dev(user):
            slug = self.kwargs.get('slug')
            if slug:
                return get_object_or_404(Loja, slug=slug)
            # Se for DEV sem slug, usa a primeira loja ou a selecionada
            loja_id = self.request.GET.get('loja')
            if loja_id:
                return get_object_or_404(Loja, pk=loja_id)
            primeira_loja = Loja.objects.first()
            if not primeira_loja:
                messages.warning(self.request, "Nenhuma loja cadastrada para configurar integrações.")
                return None
            return primeira_loja
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                raise PermissionDenied("Seu usuário não está vinculado a nenhuma loja ativa.")
            return perfil.loja

    def dispatch(self, request, *args, **kwargs):
        self.loja = self.get_loja()
        if self.loja and not pode_configurar_integracao(request.user, self.loja):
            raise PermissionDenied("Acesso negado: você não possui permissão para gerenciar as credenciais desta loja.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.loja:
            kwargs['instance'] = self.loja
        return kwargs

    def form_valid(self, form):
        acao = self.request.POST.get('acao', 'salvar')

        with transaction.atomic():
            self.loja = form.save()
            LogAuditoria.objects.create(
                loja=self.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.CONFIG_CREDENCIAIS_MELI,
                detalhes=f"Credenciais de integração com o Mercado Livre da loja '{self.loja.nome}' atualizadas.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        if acao == 'testar_conexao':
            sucesso, msg, info = MercadoLivreService.testar_conexao_loja(self.loja, self.request.user)
            if sucesso:
                messages.success(self.request, f"Credenciais salvas e {msg}")
            else:
                messages.error(self.request, f"Credenciais salvas, mas o teste falhou: {msg}")
        else:
            messages.success(self.request, f"Credenciais do Mercado Livre da loja '{self.loja.nome}' salvas com sucesso!")

        if usuario_is_dev(self.request.user) and self.kwargs.get('slug'):
            return redirect('loja_integracao_meli_slug', slug=self.loja.slug)
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['loja'] = self.loja
        context['is_dev'] = usuario_is_dev(self.request.user)
        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        return context


class ProdutoSincronizarPrecoMeliView(LoginRequiredMixin, SyncPermissionMixin, View):
    """
    Dispara a sincronização de preço unitária de um produto com a API do Mercado Livre (RF-05).
    """
    def post(self, request, pk, *args, **kwargs):
        produto = get_object_or_404(
            Produto.objects.select_related('loja'), pk=pk
        )

        # Ownership Check estrito
        if not pode_acessar_objeto_loja(request.user, produto):
            raise PermissionDenied("Acesso negado: este produto pertence a outra loja.")

        sucesso, msg, log = MercadoLivreService.sincronizar_preco_produto(produto, request.user)

        if sucesso:
            messages.success(request, msg)
        else:
            messages.error(request, msg)

        # Redireciona de volta para a tela de origem ou detalhe do produto
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(reverse('produto_detail', kwargs={'pk': produto.pk}))


class ProdutoSincronizarPrecoLoteView(LoginRequiredMixin, SyncPermissionMixin, View):
    """
    Dispara a sincronização de preço em lote para os produtos selecionados via checkboxes (RF-05).
    """
    def post(self, request, *args, **kwargs):
        form = ProdutoSincronizacaoLoteForm(request.POST)
        if not form.is_valid():
            erro_msg = form.errors.get('produtos_ids', ['Nenhum produto válido foi selecionado.'])[0]
            messages.error(request, erro_msg)
            return redirect('produto_list')

        produtos_ids = form.cleaned_data['produtos_ids']

        # Filtro estrito de Ownership pelo tenant do usuário logado
        if usuario_is_dev(request.user):
            produtos = Produto.objects.filter(id__in=produtos_ids).select_related('loja')
        else:
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja:
                raise PermissionDenied("Usuário sem loja vinculada.")
            produtos = Produto.objects.filter(id__in=produtos_ids, loja=perfil.loja).select_related('loja')

        if not produtos.exists():
            messages.error(request, "Nenhum produto válido encontrado no escopo da sua loja.")
            return redirect('produto_list')

        resultado = MercadoLivreService.sincronizar_precos_lote(produtos, request.user)

        total = resultado['total']
        sucessos = resultado['sucessos']
        erros = resultado['erros']

        if erros == 0:
            messages.success(
                request,
                f"Sincronização em lote concluída com sucesso! {sucessos} de {total} produto(s) atualizado(s) no Mercado Livre."
            )
        elif sucessos > 0:
            messages.warning(
                request,
                f"Sincronização em lote finalizada com alertas: {sucessos} produto(s) sincronizado(s) com sucesso e {erros} falha(s). Verifique os logs de integração."
            )
        else:
            messages.error(
                request,
                f"Falha na sincronização em lote: todos os {erros} produto(s) selecionados apresentaram erros. Verifique os logs de integração."
            )

        return redirect('produto_list')


# ==============================================================================
# PAINEL DE LOGS DE SINCRONIZAÇÃO E INTEGRAÇÃO (RF-05 / RN-01 / RN-04)
# ==============================================================================

class LogSincronizacaoListView(LoginRequiredMixin, ListView):
    """
    Painel de monitoramento e auditoria técnica de todas as integrações com marketplaces.
    - DEV: Visualiza logs de todas as lojas com filtro por tenant.
    - ADMIN, SUPERVISOR e USUARIO: Visualizam apenas os logs da sua própria loja.
    """
    model = LogSincronizacao
    template_name = 'core/log_sincronizacao_list.html'
    context_object_name = 'logs'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        queryset = LogSincronizacao.objects.select_related('loja', 'produto').order_by('-criado_em')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return LogSincronizacao.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        # Filtros adicionais
        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro == 'sucesso':
            queryset = queryset.filter(sucesso=True)
        elif status_filtro == 'erro':
            queryset = queryset.filter(sucesso=False)

        evento_filtro = self.request.GET.get('evento', '').strip()
        if evento_filtro:
            queryset = queryset.filter(evento=evento_filtro)

        marketplace_filtro = self.request.GET.get('marketplace', '').strip()
        if marketplace_filtro:
            queryset = queryset.filter(marketplace=marketplace_filtro)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(item_id_externo__icontains=busca) |
                Q(produto__sku__icontains=busca) |
                Q(produto__nome__icontains=busca) |
                Q(mensagem_erro__icontains=busca)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['evento_filtro'] = self.request.GET.get('evento', '').strip()
        context['marketplace_filtro'] = self.request.GET.get('marketplace', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        context['marketplaces_disponiveis'] = MarketplaceEnum.choices
        context['eventos_disponiveis'] = [
            (e.value, e.label) for e in EventoAuditoriaEnum if 'MELI' in e.value or 'SYNC' in e.value or 'BROADCAST' in e.value
        ]

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


# ==============================================================================
# WEBHOOK DE VENDAS E GESTÃO DE PEDIDOS (RF-06 / RF-07 / RN-01 / RN-04 / RN-05)
# ==============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class MercadoLivreWebhookView(View):
    """
    Endpoint HTTP público para recebimento e processamento de notificações de webhook do Mercado Livre.
    Processa eventos de venda ('orders_v2' / 'orders') e dispara baixa atômica de estoque concorrente (RF-06 / RF-07).
    """
    def post(self, request, slug=None, *args, **kwargs):
        loja_especifica = None
        if slug:
            loja_especifica = get_object_or_404(Loja, slug=slug, ativo=True)

        try:
            body = request.body.decode('utf-8')
            payload = json.loads(body) if body else {}
        except Exception as exc:
            return JsonResponse({'status': 'error', 'mensagem': f'JSON inválido: {str(exc)}'}, status=400)

        # Se for notificação em formato de lista ou dict
        if isinstance(payload, list) and len(payload) > 0:
            payload = payload[0]

        sucesso, mensagem, pedido = MercadoLivreService.processar_webhook_venda(
            payload, loja_especifica=loja_especifica
        )

        status_http = 200 if sucesso else 400
        return JsonResponse({
            'status': 'success' if sucesso else 'error',
            'mensagem': mensagem,
            'pedido_id': pedido.pedido_id_externo if pedido else None,
            'ruptura_estoque': pedido.teve_ruptura_estoque if pedido else False,
        }, status=status_http)

    def get(self, request, *args, **kwargs):
        """
        Endpoint para handshake, ping de monitoramento ou validação pelo Mercado Livre Developers.
        """
        return JsonResponse({
            'status': 'active',
            'service': 'Hub Marketplaces — Mercado Livre Webhook Listener',
            'topics_supported': ['orders_v2', 'orders', 'shipments', 'items'],
        })


class PedidoVendaListView(LoginRequiredMixin, ListView):
    """
    Painel corporativo de pedidos de venda recebidos via Webhook dos marketplaces.
    - DEV: Visualiza todos os pedidos com filtro por loja.
    - ADMIN, SUPERVISOR e USUARIO: Visualizam apenas pedidos da sua loja.
    """
    model = PedidoVenda
    template_name = 'core/pedido_venda_list.html'
    context_object_name = 'pedidos'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        queryset = PedidoVenda.objects.select_related('loja').prefetch_related('itens').order_by('-criado_em')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return PedidoVenda.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        # Filtros
        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro:
            queryset = queryset.filter(status=status_filtro)

        ruptura_filtro = self.request.GET.get('ruptura', '').strip()
        if ruptura_filtro == 'sim':
            queryset = queryset.filter(teve_ruptura_estoque=True)
        elif ruptura_filtro == 'nao':
            queryset = queryset.filter(teve_ruptura_estoque=False)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(pedido_id_externo__icontains=busca) |
                Q(comprador_nome__icontains=busca) |
                Q(comprador_documento__icontains=busca) |
                Q(itens__sku_informado__icontains=busca) |
                Q(itens__titulo_anuncio__icontains=busca)
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['ruptura_filtro'] = self.request.GET.get('ruptura', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()
        context['status_choices'] = StatusPedidoEnum.choices

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


class PedidoVendaDetailView(LoginRequiredMixin, DetailView):
    """
    Exibição dos detalhes de um Pedido de Venda e seus itens, incluindo estoque anterior/posterior.
    """
    model = PedidoVenda
    template_name = 'core/pedido_venda_detail.html'
    context_object_name = 'pedido'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if not pode_acessar_objeto_loja(self.request.user, obj):
            raise PermissionDenied("Acesso negado: este pedido pertence a outra loja.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['itens'] = self.object.itens.select_related('produto').all()
        return context


# ==============================================================================
# DISPARO MANUAL DE BROADCAST MULTI-CANAL DE ESTOQUE (RF-08)
# ==============================================================================

class ProdutoBroadcastEstoqueView(LoginRequiredMixin, SyncPermissionMixin, View):
    """
    Ação para disparo manual de broadcast de estoque de um produto para todos os canais integrados.
    """
    def post(self, request, pk, *args, **kwargs):
        produto = get_object_or_404(
            Produto.objects.select_related('loja'), pk=pk
        )
        if not pode_acessar_objeto_loja(request.user, produto):
            raise PermissionDenied("Acesso negado: este produto pertence a outra loja.")

        resultado = BroadcastEstoqueService.disparar_broadcast_produto(
            produto, usuario=request.user
        )

        if resultado['falhas'] == 0 and resultado['sucessos'] > 0:
            messages.success(
                request,
                f"Broadcast de estoque disparado com sucesso para '{produto.sku}'! {resultado['sucessos']} canal(is) atualizado(s)."
            )
        elif resultado['sucessos'] > 0 and resultado['falhas'] > 0:
            messages.warning(
                request,
                f"Broadcast parcial para '{produto.sku}': {resultado['sucessos']} sucesso(s) e {resultado['falhas']} falha(s)."
            )
        elif resultado['canais_tentados'] == 0:
            messages.info(
                request,
                f"Nenhum canal externo ativo configurado na loja '{produto.loja.nome}' para broadcast."
            )
        else:
            messages.error(
                request,
                f"Falha no broadcast de estoque para '{produto.sku}' em todos os canais tentados."
            )

        return redirect(reverse('produto_detail', kwargs={'pk': produto.pk}))


class ProdutoBroadcastEstoqueLoteView(LoginRequiredMixin, SyncPermissionMixin, View):
    """
    Ação para disparo de broadcast de estoque em lote para múltiplos produtos selecionados.
    """
    def post(self, request, *args, **kwargs):
        form = ProdutoBroadcastLoteForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Seleção inválida de produtos para broadcast.")
            return redirect(reverse('produto_list'))

        produtos_ids = form.cleaned_data['produtos_ids']
        user = request.user

        if usuario_is_dev(user):
            produtos = Produto.objects.filter(id__in=produtos_ids).select_related('loja')
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                raise PermissionDenied("Usuário sem loja vinculada.")
            produtos = Produto.objects.filter(id__in=produtos_ids, loja=perfil.loja).select_related('loja')

        if not produtos.exists():
            messages.warning(request, "Nenhum produto válido encontrado para o disparo de broadcast.")
            return redirect(reverse('produto_list'))

        resumo = BroadcastEstoqueService.disparar_broadcast_lote(produtos, usuario=user)

        messages.success(
            request,
            f"Broadcast em lote concluído para {resumo['total_produtos']} produto(s): "
            f"{resumo['sucessos']} com sucesso total, {resumo['falhas']} com pendências."
        )
        return redirect(reverse('produto_list'))






