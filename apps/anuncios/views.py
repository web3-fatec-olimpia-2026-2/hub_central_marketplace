# Os códigos foram gerados com auxilio de I.A.
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, View, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from apps.tenancy.models import Loja
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, usuario_is_dev, pode_disparar_sincronizacao
)
from apps.marketplaces.models import ContaMarketplace
from apps.catalogo.models import Produto
from apps.anuncios.models import Anuncio, AnuncioComposicao
from apps.anuncios.services import AnuncioImportacaoService
from apps.anuncios.forms import AnuncioComposicaoForm


class AnuncioListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Catálogo comercial multicanal com listagem de anúncios importados e seus respectivos kits.
    POR QUE FAZ: Permite ao lojista visualizar todos os anúncios nos marketplaces, status, preço,
                 estoque publicado vs cota física real calculada, e gerenciar composições/kits (Fase 1).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Isolamento restrito por Loja do usuário logado (ou todas se DEV).
    """
    modulo_requerido = 'marketplaces'
    model = Anuncio
    template_name = 'anuncios/anuncio_list.html'
    context_object_name = 'anuncios'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Anuncio.objects.select_related('conta', 'conta__loja')
            .prefetch_related('itens_composicao__produto')
            .order_by('-atualizado_em')
        )

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(conta__loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return Anuncio.objects.none()
            queryset = queryset.filter(conta__loja=perfil.loja)

        conta_id = self.request.GET.get('conta', '').strip()
        if conta_id:
            queryset = queryset.filter(conta_id=conta_id)

        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro:
            queryset = queryset.filter(status=status_filtro)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(item_id_externo__icontains=busca) |
                Q(titulo__icontains=busca) |
                Q(sku_vendedor__icontains=busca)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['pode_sincronizar'] = pode_disparar_sincronizacao(user)

        if context['is_dev']:
            context['contas_disponiveis'] = ContaMarketplace.objects.select_related('loja').filter(ativo=True)
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            perfil = getattr(user, 'perfil', None)
            loja = getattr(perfil, 'loja', None)
            context['contas_disponiveis'] = ContaMarketplace.objects.filter(loja=loja, ativo=True) if loja else []

        context['conta_filtro'] = self.request.GET.get('conta', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()
        return context


class AnuncioDetailView(LoginRequiredMixin, ModuloRequeridoMixin, DetailView):
    """
    O QUE FAZ: Exibe detalhes do anúncio e permite gerenciar os produtos da composição (Kit).
    """
    modulo_requerido = 'marketplaces'
    model = Anuncio
    template_name = 'anuncios/anuncio_detail.html'
    context_object_name = 'anuncio'

    def get_object(self, queryset=None):
        anuncio = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")
        return anuncio

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_composicao'] = AnuncioComposicaoForm(anuncio=self.object)
        context['cota_calculada'] = self.object.calcular_cota_disponivel()
        return context


class AnuncioImportarView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Dispara a importação e atualização de anúncios de uma ContaMarketplace específica via conector.
    POR QUE FAZ: Permite ao lojista puxar o catálogo existente do Mercado Livre diretamente para o Hub (Fase 1).
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO bloqueado com 403).
    MULTI-TENANCY: Garante que o lojista só dispare importação para contas da sua própria loja.
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para importar anúncios.")

        conta = get_object_or_404(ContaMarketplace, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta pertence a outra loja.")

        resultado = AnuncioImportacaoService.importar_anuncios_da_conta(
            conta=conta,
            associar_produtos_por_sku=True,
            usuario=request.user
        )

        if resultado.get('sucesso'):
            messages.success(request, f"[{conta.get_canal_display()}] {resultado.get('mensagem')}")
        else:
            messages.error(request, f"[{conta.get_canal_display()}] Falha na importação: {resultado.get('mensagem')}")

        # Redireciona para a lista filtrando pela conta importada
        return redirect(f"{reverse('anuncio_list')}?conta={conta.pk}")


class AnuncioComposicaoCreateView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Adiciona um produto à composição do anúncio (Kit).
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado.")

        anuncio = get_object_or_404(Anuncio, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        form = AnuncioComposicaoForm(request.POST, anuncio=anuncio)
        if form.is_valid():
            produto = form.cleaned_data['produto']
            quantidade = form.cleaned_data['quantidade']
            item_comp, created = AnuncioComposicao.objects.update_or_create(
                anuncio=anuncio,
                produto=produto,
                defaults={'quantidade': quantidade}
            )
            messages.success(
                request,
                f"Produto '{produto.sku}' vinculado à composição com multiplicador {quantidade}x com sucesso!"
            )
        else:
            messages.error(request, f"Erro ao adicionar produto à composição: {form.errors.as_text()}")

        return redirect('anuncio_detail', pk=anuncio.pk)


class AnuncioComposicaoDeleteView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Remove um item da composição de um anúncio.
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado.")

        item = get_object_or_404(AnuncioComposicao, pk=pk)
        anuncio = item.anuncio
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        produto_nome = item.produto.nome
        item.delete()
        messages.success(request, f"Vínculo com '{produto_nome}' removido da composição.")
        return redirect('anuncio_detail', pk=anuncio.pk)


class AnuncioSincronizarView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Dispara a sincronização manual e imediata de estoque e preço do anúncio no marketplace.
    POR QUE FAZ: Permite ao lojista/gestor sincronizar sob demanda com a API do canal (ex: Mercado Livre).
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Validação estrita por loja.
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para sincronizar anúncios.")

        anuncio = get_object_or_404(Anuncio, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")

        from apps.anuncios.services import AnuncioSincronizacaoService
        res_est = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(anuncio, usuario=request.user, forcar=True)
        res_prc = AnuncioSincronizacaoService.sincronizar_preco_anuncio(anuncio, anuncio.preco_venda, usuario=request.user, forcar=True)

        if res_est.get('sucesso'):
            anuncio.status_sincronizacao = 'SINCRONIZADO'
            anuncio.save(update_fields=['status_sincronizacao', 'atualizado_em'])
            messages.success(
                request,
                f"Anúncio [{anuncio.item_id_externo}] sincronizado com sucesso no canal {anuncio.conta.get_canal_display()}! "
                f"(Estoque: {res_est.get('estoque_sincronizado')} un., Preço: R$ {anuncio.preco_venda:.2f})"
            )
        else:
            messages.error(
                request,
                f"Falha ao sincronizar estoque do anúncio [{anuncio.item_id_externo}]: {res_est.get('mensagem')}"
            )

        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('anuncio_detail', pk=anuncio.pk)


class AnuncioToggleIgnorarView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    """
    O QUE FAZ: Alterna a decisão do operador entre sincronizar ou ignorar/descartar alterações para o anúncio.
    POR QUE FAZ: Permite ao operador proteger kits ou anúncios com estratégias de preço/estoque independentes.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para alterar anúncios.")

        anuncio = get_object_or_404(Anuncio, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")

        if anuncio.status_sincronizacao == 'IGNORADO':
            cota = anuncio.calcular_cota_disponivel()
            if anuncio.estoque_publicado != cota:
                anuncio.status_sincronizacao = 'PENDENTE'
            else:
                anuncio.status_sincronizacao = 'SINCRONIZADO'
            messages.success(request, f"Sincronização reativada para o anúncio [{anuncio.item_id_externo}].")
        else:
            anuncio.status_sincronizacao = 'IGNORADO'
            messages.info(request, f"O anúncio [{anuncio.item_id_externo}] foi marcado como IGNORADO/DESCARTADO para sincronizações.")

        anuncio.save(update_fields=['status_sincronizacao', 'atualizado_em'])

        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('anuncio_detail', pk=anuncio.pk)

