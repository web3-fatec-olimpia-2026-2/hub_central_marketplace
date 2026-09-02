# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, DeleteView, FormView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.core.exceptions import PermissionDenied

from apps.tenancy.models import Loja
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, CatalogOwnershipCheckMixin, CatalogDeletePermissionMixin,
    SyncPermissionMixin, usuario_is_dev, pode_alterar_preco, pode_ajustar_estoque_geral,
    pode_excluir_catalogo, pode_dar_baixa_avaria, pode_disparar_sincronizacao
)
from apps.marketplaces.models import LogAuditoria, ContaMarketplace
from apps.marketplaces.enums import EventoAuditoriaEnum, StatusSincronizacaoEnum
from apps.marketplaces.connectors.factory import get_connector_for_conta

from .models import Categoria, Produto, AnuncioMarketplace, HistoricoPreco
from .enums import StatusProdutoEnum, TipoAjusteEstoqueEnum
from .forms import (
    CategoriaForm, ProdutoForm, AnuncioMarketplaceForm, ProdutoBaixaAvariaForm,
    ProdutoAjusteEstoqueForm, ProdutoSincronizacaoLoteForm, PublicarAnuncioForm
)


# ==============================================================================
# GESTÃO DE CATEGORIAS (RF-03 / RN-01)
# ==============================================================================

class CategoriaListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Listagem de Categorias de Produtos com isolamento multi-tenant.
    POR QUE FAZ: Organização das categorias do catálogo filtradas pela loja do usuário.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (com módulo 'catalogo' ativo).
    MULTI-TENANCY: Isolamento horizontal por tenant.
    """
    modulo_requerido = 'catalogo'
    model = Categoria
    template_name = 'catalogo/categoria_list.html'
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


class CategoriaCreateView(LoginRequiredMixin, ModuloRequeridoMixin, CreateView):
    """
    O QUE FAZ: Cadastro de nova Categoria no catálogo da Loja.
    POR QUE FAZ: Estruturação taxonômica de produtos.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Vínculo à loja do usuário.
    """
    modulo_requerido = 'catalogo'
    model = Categoria
    form_class = CategoriaForm
    template_name = 'catalogo/categoria_form.html'
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


class CategoriaUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, CatalogOwnershipCheckMixin, UpdateView):
    """
    O QUE FAZ: Edição de Categoria existente com Ownership Check.
    POR QUE FAZ: Manutenção de categorias com validação de tenant.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Isolado por loja.
    """
    modulo_requerido = 'catalogo'
    model = Categoria
    form_class = CategoriaForm
    template_name = 'catalogo/categoria_form.html'
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


class CategoriaDeleteView(LoginRequiredMixin, ModuloRequeridoMixin, CatalogOwnershipCheckMixin, CatalogDeletePermissionMixin, DeleteView):
    """
    O QUE FAZ: Exclusão de Categoria protegida por RN-09.
    POR QUE FAZ: Bloqueia USUARIO (403 Forbidden) e impede remoção caso existam produtos vinculados.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Isolado por loja.
    """
    modulo_requerido = 'catalogo'
    model = Categoria
    template_name = 'catalogo/categoria_confirm_delete.html'
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
# GESTÃO DE PRODUTOS E ANÚNCIOS MULTICANAL (RF-03 / RN-01 / RN-02 / RN-06 / RN-09)
# ==============================================================================

class ProdutoListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Catálogo de Produtos com suporte multicanal, filtros e controle de acesso RBAC.
    POR QUE FAZ: Central de visualização de SKUs, estoque, preços e anúncios vinculados.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Filtro estrito por loja.
    """
    modulo_requerido = 'catalogo'
    model = Produto
    template_name = 'catalogo/produto_list.html'
    context_object_name = 'produtos'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Produto.objects.select_related('loja', 'categoria').prefetch_related('anuncios__conta_marketplace').order_by('-criado_em')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return Produto.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

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
        elif estoque_filtro == 'negativo':
            queryset = queryset.filter(estoque__lt=0)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(sku__icontains=busca) |
                Q(nome__icontains=busca) |
                Q(anuncios__item_id_externo__icontains=busca)
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['pode_alterar_preco'] = pode_alterar_preco(user)
        context['pode_ajustar_estoque_geral'] = pode_ajustar_estoque_geral(user)
        context['pode_excluir'] = pode_excluir_catalogo(user)
        context['pode_dar_baixa_avaria'] = pode_dar_baixa_avaria(user)
        context['pode_sincronizar'] = pode_disparar_sincronizacao(user)

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


class ProdutoCreateView(LoginRequiredMixin, ModuloRequeridoMixin, CreateView):
    """
    O QUE FAZ: Cadastro de novo Produto com gravação inicial em HistoricoPreco e LogAuditoria.
    POR QUE FAZ: Fonte Única da Verdade para produtos e preços do lojista.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (este último sem preço/estoque inicial).
    MULTI-TENANCY: Vínculo à loja do usuário.
    """
    modulo_requerido = 'catalogo'
    model = Produto
    form_class = ProdutoForm
    template_name = 'catalogo/produto_form.html'
    success_url = reverse_lazy('produto_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()

            if self.object.preco > Decimal('0.00'):
                HistoricoPreco.objects.create(
                    produto=self.object,
                    loja=self.object.loja,
                    preco_anterior=Decimal('0.00'),
                    preco_novo=self.object.preco,
                    usuario=self.request.user,
                    motivo="Preço inicial no cadastro"
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


class ProdutoDetailView(LoginRequiredMixin, ModuloRequeridoMixin, CatalogOwnershipCheckMixin, DetailView):
    """
    O QUE FAZ: Detalhes do Produto, histórico de mutações de preços e anúncios vinculados nos marketplaces.
    POR QUE FAZ: Gestão multicanal detalhada por SKU.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Ownership check estrito de tenant.
    """
    modulo_requerido = 'catalogo'
    model = Produto
    template_name = 'catalogo/produto_detail.html'
    context_object_name = 'produto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['anuncios'] = self.object.anuncios.select_related('conta_marketplace').all()
        context['historicos'] = self.object.historico_precos.select_related('usuario').order_by('-criado_em')[:10]
        context['form_anuncio'] = AnuncioMarketplaceForm(produto=self.object)
        context['pode_alterar_preco'] = pode_alterar_preco(self.request.user)
        context['pode_ajustar_estoque_geral'] = pode_ajustar_estoque_geral(self.request.user)
        context['pode_dar_baixa_avaria'] = pode_dar_baixa_avaria(self.request.user)
        return context


class ProdutoUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, CatalogOwnershipCheckMixin, UpdateView):
    """
    O QUE FAZ: Edição de Produto com detecção de mutação de preço/estoque e gravação de histórico (RN-04 / RN-09).
    POR QUE FAZ: Garante que alterações manuais fiquem registradas e que USUARIO não altere preço/estoque.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (Total); USUARIO (Apenas descritivos).
    MULTI-TENANCY: Ownership check por loja.
    """
    modulo_requerido = 'catalogo'
    model = Produto
    form_class = ProdutoForm
    template_name = 'catalogo/produto_form.html'
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

            if preco_anterior != self.object.preco:
                HistoricoPreco.objects.create(
                    produto=self.object,
                    loja=self.object.loja,
                    preco_anterior=preco_anterior,
                    preco_novo=self.object.preco,
                    usuario=self.request.user,
                    motivo="Alteração de preço manual pelo painel"
                )
                LogAuditoria.objects.create(
                    loja=self.object.loja,
                    autor=self.request.user,
                    evento=EventoAuditoriaEnum.ALTERACAO_PRECO,
                    detalhes=f"Preço do SKU '{self.object.sku}' alterado de R$ {preco_anterior} para R$ {self.object.preco}.",
                    ip_origem=self.request.META.get('REMOTE_ADDR')
                )

            if estoque_anterior != self.object.estoque:
                LogAuditoria.objects.create(
                    loja=self.object.loja,
                    autor=self.request.user,
                    evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                    detalhes=f"Estoque do SKU '{self.object.sku}' alterado de {estoque_anterior} para {self.object.estoque}.",
                    ip_origem=self.request.META.get('REMOTE_ADDR')
                )

            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EDICAO_PRODUTO,
                detalhes=f"Dados do produto '{self.object.nome}' (SKU: {self.object.sku}) atualizados.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        messages.success(self.request, f"Produto '{self.object.nome}' atualizado com sucesso!")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        return context


class ProdutoDeleteView(LoginRequiredMixin, ModuloRequeridoMixin, CatalogOwnershipCheckMixin, CatalogDeletePermissionMixin, DeleteView):
    """
    O QUE FAZ: Exclusão de Produto protegida por RN-09.
    POR QUE FAZ: Impede que o papel USUARIO exclua produtos.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Isolado por loja.
    """
    modulo_requerido = 'catalogo'
    model = Produto
    template_name = 'catalogo/produto_confirm_delete.html'
    success_url = reverse_lazy('produto_list')

    def form_valid(self, form):
        with transaction.atomic():
            sku = self.object.sku
            loja = self.object.loja
            LogAuditoria.objects.create(
                loja=loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EXCLUSAO_PRODUTO,
                detalhes=f"Produto '{sku}' excluído da loja '{loja.nome}'.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
            messages.success(self.request, f"Produto SKU '{sku}' excluído com sucesso.")
            return super().form_valid(form)


class ProdutoBaixaEstoqueView(LoginRequiredMixin, ModuloRequeridoMixin, CatalogOwnershipCheckMixin, FormView):
    """
    O QUE FAZ: Registro de baixa pontual de estoque por motivo de avaria ou perda física (RN-09).
    POR QUE FAZ: Permite que todos os usuários autenticados da loja (inclusive USUARIO) registrem perdas operacionais com motivo obrigatório.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Isolado por loja.
    """
    modulo_requerido = 'catalogo'
    template_name = 'catalogo/produto_baixa_estoque.html'
    form_class = ProdutoBaixaAvariaForm

    def dispatch(self, request, *args, **kwargs):
        self.produto = get_object_or_404(Produto, pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.produto

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['produto'] = self.produto
        return kwargs

    def form_valid(self, form):
        qtd = form.cleaned_data['quantidade']
        tipo_baixa = form.cleaned_data['tipo_baixa']
        justificativa = form.cleaned_data['justificativa']

        with transaction.atomic():
            prod_locked = Produto.objects.select_for_update().get(pk=self.produto.pk)
            saldo_anterior = prod_locked.estoque
            novo_saldo = saldo_anterior - qtd
            prod_locked.estoque = novo_saldo
            prod_locked.save(update_fields=['estoque', 'atualizado_em'])

            LogAuditoria.objects.create(
                loja=prod_locked.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.BAIXA_AVARIA,
                detalhes=(
                    f"Baixa de {qtd} un. do produto '{prod_locked.sku}' por motivo '{tipo_baixa}'. "
                    f"Saldo anterior: {saldo_anterior} -> Novo saldo: {novo_saldo}. "
                    f"Justificativa: {justificativa}"
                ),
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        messages.success(
            self.request,
            f"Baixa de {qtd} un. registrada com sucesso! Novo estoque: {novo_saldo} un."
        )
        return redirect('produto_detail', pk=self.produto.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['produto'] = self.produto
        return context


class ProdutoAjusteEstoqueView(LoginRequiredMixin, ModuloRequeridoMixin, CatalogOwnershipCheckMixin, FormView):
    """
    O QUE FAZ: Ajuste geral de saldo físico de estoque por gestores.
    POR QUE FAZ: Gestão e correção manual de balanço por DEV, ADMIN ou SUPERVISOR (RN-09).
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO é bloqueado).
    MULTI-TENANCY: Isolado por loja.
    """
    modulo_requerido = 'catalogo'
    template_name = 'catalogo/produto_ajuste_estoque.html'
    form_class = ProdutoAjusteEstoqueForm

    def dispatch(self, request, *args, **kwargs):
        if not pode_ajustar_estoque_geral(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não pode realizar ajuste geral de estoque (RN-09).")
        self.produto = get_object_or_404(Produto, pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.produto

    def form_valid(self, form):
        novo_saldo = form.cleaned_data['novo_estoque']
        tipo_ajuste = form.cleaned_data['tipo_ajuste']
        justificativa = form.cleaned_data['justificativa']

        with transaction.atomic():
            prod_locked = Produto.objects.select_for_update().get(pk=self.produto.pk)
            saldo_anterior = prod_locked.estoque
            prod_locked.estoque = novo_saldo
            prod_locked.save(update_fields=['estoque', 'atualizado_em'])

            LogAuditoria.objects.create(
                loja=prod_locked.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                detalhes=(
                    f"Ajuste geral de estoque do SKU '{prod_locked.sku}' ({tipo_ajuste}). "
                    f"Saldo anterior: {saldo_anterior} -> Novo saldo: {novo_saldo}. "
                    f"Justificativa: {justificativa}"
                ),
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )

        messages.success(
            self.request,
            f"Estoque do SKU '{self.produto.sku}' atualizado para {novo_saldo} un. com sucesso!"
        )
        return redirect('produto_detail', pk=self.produto.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['produto'] = self.produto
        return context


class AnuncioMarketplaceCreateView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Cria e vincula um novo AnuncioMarketplace a um produto local.
    POR QUE FAZ: Mapeia IDs externos de múltiplos canais (MLB..., Shopee ID).
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Valida loja do produto.
    """
    modulo_requerido = 'catalogo'

    def post(self, request, pk, *args, **kwargs):
        produto = get_object_or_404(Produto, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or produto.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        form = AnuncioMarketplaceForm(request.POST, produto=produto)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.produto = produto
            anuncio.save()
            messages.success(request, f"Anúncio '{anuncio.item_id_externo}' vinculado com sucesso ao produto!")
        else:
            messages.error(request, f"Erro ao vincular anúncio: {form.errors.as_text()}")

        return redirect('produto_detail', pk=produto.pk)


class AnuncioMarketplaceDeleteView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Remove o vínculo de um anúncio de marketplace de um produto.
    """
    modulo_requerido = 'catalogo'

    def post(self, request, pk, *args, **kwargs):
        anuncio = get_object_or_404(AnuncioMarketplace, pk=pk)
        produto = anuncio.produto
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or produto.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        item_id = anuncio.item_id_externo
        anuncio.delete()
        messages.success(request, f"Vínculo do anúncio '{item_id}' removido com sucesso.")
        return redirect('produto_detail', pk=produto.pk)


class ProdutoSincronizarPrecoView(LoginRequiredMixin, ModuloRequeridoMixin, SyncPermissionMixin, View):
    """
    O QUE FAZ: Dispara a sincronização de preço para todos os anúncios externos vinculados a este produto.
    POR QUE FAZ: Envia PUT para as APIs dos canais (Mercado Livre, Shopee, Magalu).
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Isolado por loja.
    """
    modulo_requerido = 'catalogo'

    def post(self, request, pk, *args, **kwargs):
        produto = get_object_or_404(Produto, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or produto.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        anuncios = produto.anuncios.select_related('conta_marketplace').all()
        if not anuncios.exists():
            messages.warning(request, f"O produto '{produto.sku}' não possui anúncios de marketplaces vinculados.")
            return redirect('produto_detail', pk=produto.pk)

        sucessos = 0
        falhas = 0
        for anuncio in anuncios:
            conta = anuncio.conta_marketplace
            connector = get_connector_for_conta(conta)
            sucesso, msg, log = connector.atualizar_preco(anuncio.item_id_externo, produto.preco, usuario=request.user)
            if sucesso:
                sucessos += 1
                anuncio.preco_sincronizado = produto.preco
                anuncio.save(update_fields=['preco_sincronizado', 'atualizado_em'])
            else:
                falhas += 1

        if falhas == 0:
            produto.status_sincronizacao = StatusSincronizacaoEnum.SINCRONIZADO
            produto.save(update_fields=['status_sincronizacao', 'atualizado_em'])
            messages.success(request, f"Preço de R$ {produto.preco} sincronizado com sucesso em {sucessos} anúncio(s)!")
        else:
            produto.status_sincronizacao = StatusSincronizacaoEnum.ERRO
            produto.save(update_fields=['status_sincronizacao', 'atualizado_em'])
            messages.warning(request, f"Sincronização finalizada: {sucessos} sucesso(s) e {falhas} falha(s).")

        return redirect('produto_detail', pk=produto.pk)


class ProdutoSincronizarPrecoLoteView(LoginRequiredMixin, ModuloRequeridoMixin, SyncPermissionMixin, FormView):
    """
    O QUE FAZ: Sincroniza preços em lote para os produtos selecionados.
    """
    modulo_requerido = 'catalogo'
    form_class = ProdutoSincronizacaoLoteForm

    def form_valid(self, form):
        produtos_ids = form.cleaned_data['produtos_ids']
        user = self.request.user
        qs = Produto.objects.filter(id__in=produtos_ids)
        if not usuario_is_dev(user):
            qs = qs.filter(loja=user.perfil.loja)

        total_anuncios = 0
        sucessos = 0
        for produto in qs:
            for anuncio in produto.anuncios.select_related('conta_marketplace').all():
                total_anuncios += 1
                connector = get_connector_for_conta(anuncio.conta_marketplace)
                sucesso, _, _ = connector.atualizar_preco(anuncio.item_id_externo, produto.preco, usuario=user)
                if sucesso:
                    sucessos += 1

        messages.success(self.request, f"Sincronização em lote: {sucessos} de {total_anuncios} anúncio(s) atualizados com sucesso.")
        return redirect('produto_list')

    def form_invalid(self, form):
        messages.error(self.request, "Nenhum produto válido selecionado para sincronização.")
        return redirect('produto_list')


# ==============================================================================
# PUBLICAÇÃO DE ANÚNCIOS EM MARKETPLACES (RF-04)
# ==============================================================================

class PublicarAnuncioView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Publica um produto do catálogo como anúncio ativo em uma conta de marketplace (RF-04).
    POR QUE FAZ: Conecta o produto do Hub à API do marketplace de destino, registrando o ID externo e telemetria.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO bloqueado com 403 Forbidden).
    MULTI-TENANCY: Restrito à loja do produto e conta do usuário (DEV com bypass global).
    """
    modulo_requerido = 'marketplaces'
    template_name = 'catalogo/anuncio_publicar_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user):
            raise PermissionDenied("Acesso negado: o perfil USUARIO não possui permissão para publicar anúncios em marketplaces.")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        user = self.request.user
        produto_id = self.kwargs.get('pk')
        if usuario_is_dev(user):
            return get_object_or_404(Produto, pk=produto_id)
        perfil = getattr(user, 'perfil', None)
        if not perfil or not perfil.loja:
            raise PermissionDenied("Usuário sem loja vinculada.")
        return get_object_or_404(Produto, pk=produto_id, loja=perfil.loja)

    def get(self, request, *args, **kwargs):
        produto = self.get_object()
        form = PublicarAnuncioForm(produto=produto, autor=request.user)
        context = {
            'produto': produto,
            'form': form,
            'is_dev': usuario_is_dev(request.user),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        produto = self.get_object()
        form = PublicarAnuncioForm(request.POST, produto=produto, autor=request.user)

        if not form.is_valid():
            context = {
                'produto': produto,
                'form': form,
                'is_dev': usuario_is_dev(request.user),
            }
            return render(request, self.template_name, context)

        conta = form.cleaned_data['conta_marketplace']
        listing_type_id = form.cleaned_data['listing_type_id']
        preco = form.cleaned_data['preco']
        category_id = form.cleaned_data['category_id']

        # Validação multi-tenant rigorosa (produto e conta devem ser da mesma loja, a menos que DEV)
        if not usuario_is_dev(request.user) and produto.loja_id != conta.loja_id:
            raise PermissionDenied("A conta de marketplace selecionada pertence a outra loja.")

        dados_extras = {
            'preco': preco,
            'listing_type_id': listing_type_id,
            'category_id': category_id,
        }

        connector = get_connector_for_conta(conta)
        sucesso, mensagem, dados_retorno, log = connector.publicar_anuncio(
            produto=produto,
            conta=conta,
            dados_extras=dados_extras,
            usuario=request.user
        )

        if sucesso:
            item_id_externo = dados_retorno.get('item_id_externo', f"MLB-{produto.sku}")
            link_anuncio = dados_retorno.get('link_anuncio', '')
            preco_sincronizado = dados_retorno.get('preco_sincronizado', preco)
            status_anuncio = dados_retorno.get('status_anuncio', 'ativo')

            # Cria ou atualiza o registro AnuncioMarketplace
            anuncio, created = AnuncioMarketplace.objects.update_or_create(
                produto=produto,
                conta_marketplace=conta,
                defaults={
                    'item_id_externo': item_id_externo,
                    'link_anuncio': link_anuncio,
                    'preco_sincronizado': preco_sincronizado,
                    'status_anuncio': status_anuncio,
                }
            )

            # Grava Log de Auditoria
            LogAuditoria.objects.create(
                loja=produto.loja,
                autor=request.user,
                evento=EventoAuditoriaEnum.PUBLICACAO_ANUNCIO,
                detalhes=(
                    f"Anúncio publicado com sucesso no canal {conta.get_canal_display()} "
                    f"para o produto '{produto.sku}'. ID Externo: {item_id_externo}."
                )
            )

            messages.success(
                request,
                f"Anúncio publicado com sucesso no {conta.get_canal_display()}! "
                f"Identificador: {item_id_externo} — Preço: R$ {preco_sincronizado:.2f}"
            )
            return redirect('produto_detail', pk=produto.pk)
        else:
            messages.error(request, f"Falha na publicação do anúncio: {mensagem}")
            context = {
                'produto': produto,
                'form': form,
                'is_dev': usuario_is_dev(request.user),
            }
            return render(request, self.template_name, context)
