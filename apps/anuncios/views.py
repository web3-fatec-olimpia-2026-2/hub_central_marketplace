# Os códigos foram gerados com auxilio de I.A.
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, View, DetailView, CreateView, UpdateView
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
from apps.anuncios.models import Anuncio, AnuncioComposicao, HistoricoSincronizacaoAnuncio
from apps.anuncios.services import AnuncioImportacaoService
from apps.anuncios.forms import AnuncioForm, AnuncioComposicaoInlineFormSet, AnuncioComposicaoForm


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
        context['historicos_ciclo'] = self.object.historico_ciclo.select_related('usuario').order_by('-criado_em')[:30]
        return context


def _adicionar_mapa_lojas_e_produtos(context, loja_fixa=None):
    """
    O QUE FAZ: Constrói mapeamentos JSON de contas->lojas e lojas->produtos ativos.
    POR QUE FAZ: Permite ao frontend re-filtrar reativamente os selects de produto ao alternar contas em criação.
                 Quando loja_fixa é informada (ex: em edição ou para operador não-DEV), restringe estritamente
                 os dados à loja em questão, impedindo que dados de outros tenants apareçam no HTML ou no DOM.
    """
    import json
    from apps.catalogo.enums import StatusProdutoEnum
    from apps.catalogo.models import Produto
    from apps.marketplaces.models import ContaMarketplace
    from apps.tenancy.models import Loja

    if loja_fixa is not None:
        contas_qs = ContaMarketplace.objects.filter(loja=loja_fixa)
        lojas_qs = Loja.objects.filter(pk=loja_fixa.pk, ativo=True)
    else:
        contas_qs = ContaMarketplace.objects.all()
        lojas_qs = Loja.objects.filter(ativo=True)

    contas_map = {
        str(c.pk): str(c.loja_id)
        for c in contas_qs
    }
    produtos_map = {}
    for l in lojas_qs.prefetch_related('produtos'):
        produtos_map[str(l.pk)] = [
            {
                'id': p.pk,
                'label': f"[{p.sku}] {p.nome} — R$ {p.preco:.2f} (Estoque: {p.estoque})"
            }
            for p in l.produtos.filter(status=StatusProdutoEnum.ATIVO).order_by('nome')
        ]
    context['contas_lojas_json'] = json.dumps(contas_map)
    context['produtos_por_loja_json'] = json.dumps(produtos_map)


class AnuncioCreateView(LoginRequiredMixin, ModuloRequeridoMixin, CreateView):
    """
    O QUE FAZ: Criação manual direta de anúncios com suporte a múltiplos produtos na composição (Kits e Combos).
    POR QUE FAZ: Atende ao ADR-003, ADR-009 e expansão do catálogo comercial sem depender unicamente de importação externa.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO bloqueado com 403).
    MULTI-TENANCY: Garante isolamento estrito por Loja do usuário logado.
    """
    modulo_requerido = 'marketplaces'
    model = Anuncio
    form_class = AnuncioForm
    template_name = 'anuncios/anuncio_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para criar anúncios.")
        return super().dispatch(request, *args, **kwargs)

    def get_loja_alvo(self):
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            return getattr(perfil, 'loja', None) if perfil else None

        conta_id = self.request.POST.get('conta') or self.request.GET.get('conta')
        if conta_id:
            conta = ContaMarketplace.objects.filter(pk=conta_id).select_related('loja').first()
            if conta:
                return conta.loja

        primeira_conta = ContaMarketplace.objects.filter(ativo=True).select_related('loja').first()
        return primeira_conta.loja if primeira_conta else None

    def get_initial(self):
        initial = super().get_initial()
        if 'conta' in self.request.GET:
            initial['conta'] = self.request.GET.get('conta')
        elif usuario_is_dev(self.request.user):
            primeira_conta = ContaMarketplace.objects.filter(ativo=True).first()
            if primeira_conta:
                initial['conta'] = primeira_conta.pk
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        loja = self.get_loja_alvo()

        if 'formset' not in context:
            if self.request.POST:
                context['formset'] = AnuncioComposicaoInlineFormSet(
                    self.request.POST,
                    instance=self.object or Anuncio(),
                    loja=loja,
                    user=user
                )
            else:
                context['formset'] = AnuncioComposicaoInlineFormSet(
                    instance=self.object or Anuncio(),
                    loja=loja,
                    user=user
                )
        context['is_edicao'] = False
        loja_fixa = None if usuario_is_dev(user) else loja
        _adicionar_mapa_lojas_e_produtos(context, loja_fixa=loja_fixa)
        return context

    def form_valid(self, form):
        user = self.request.user
        self.object = form.save(commit=False)
        loja = self.object.conta.loja if getattr(self.object, 'conta', None) else self.get_loja_alvo()

        formset = AnuncioComposicaoInlineFormSet(
            self.request.POST,
            instance=self.object,
            loja=loja,
            user=user
        )

        if formset.is_valid():
            with transaction.atomic():
                self.object.save()
                formset.instance = self.object
                formset.save()

                cota = self.object.calcular_cota_disponivel()
                tem_composicao = self.object.itens_composicao.exists()
                if tem_composicao:
                    self.object.estoque_publicado = cota
                    self.object.save(update_fields=['estoque_publicado', 'atualizado_em'])

                HistoricoSincronizacaoAnuncio.objects.create(
                    anuncio=self.object,
                    status_resultante=self.object.status_sincronizacao,
                    preco_anterior=0,
                    preco_proposto=self.object.preco_venda,
                    estoque_anterior=0,
                    estoque_proposto=self.object.estoque_publicado,
                    usuario=self.request.user,
                    motivo=f"Criação manual do anúncio [{self.object.item_id_externo}] com composição ({self.object.tipo_composicao})"
                )

            messages.success(self.request, f"Anúncio [{self.object.item_id_externo}] criado com sucesso!")
            return redirect(reverse('anuncio_detail', kwargs={'pk': self.object.pk}))
        else:
            return self.render_to_response(self.get_context_data(form=form, formset=formset))


class AnuncioUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, UpdateView):
    """
    O QUE FAZ: Edição de dados do anúncio e gerenciamento completo de sua composição de produtos físicos (Kits e Combos).
    POR QUE FAZ: Permite ao operador ajustar preço, SKU, título e reestruturar os produtos do kit via formset unificado.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO bloqueado com 403).
    MULTI-TENANCY: Isolamento estrito por Loja do usuário logado (anúncio de outra loja bloqueado).
    RESTRIÇÃO DE COMPOSIÇÃO: Mesmo para usuário DEV, os produtos da composição são restritos rigorosamente à loja do anúncio.
    """
    modulo_requerido = 'marketplaces'
    model = Anuncio
    form_class = AnuncioForm
    template_name = 'anuncios/anuncio_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para editar anúncios.")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        anuncio = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")
        return anuncio

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # A composição do anúncio é restrita estritamente à loja da conta em questão (mesmo para DEV)
        loja = self.object.conta.loja

        if 'formset' not in context:
            if self.request.POST:
                context['formset'] = AnuncioComposicaoInlineFormSet(
                    self.request.POST,
                    instance=self.object,
                    loja=loja,
                    user=user
                )
            else:
                context['formset'] = AnuncioComposicaoInlineFormSet(
                    instance=self.object,
                    loja=loja,
                    user=user
                )
        context['is_edicao'] = True
        _adicionar_mapa_lojas_e_produtos(context, loja_fixa=loja)
        return context

    def form_valid(self, form):
        user = self.request.user
        # A composição do anúncio é restrita estritamente à loja da conta em questão (mesmo para DEV)
        loja = self.object.conta.loja

        formset = AnuncioComposicaoInlineFormSet(
            self.request.POST,
            instance=self.object,
            loja=loja,
            user=user
        )

        if formset.is_valid():
            with transaction.atomic():
                preco_ant = self.object.preco_venda
                estoque_ant = self.object.estoque_publicado

                self.object = form.save()
                formset.save()

                cota = self.object.calcular_cota_disponivel()
                tem_composicao = self.object.itens_composicao.exists()
                if tem_composicao:
                    self.object.estoque_publicado = cota
                    self.object.save(update_fields=['estoque_publicado', 'atualizado_em'])

                HistoricoSincronizacaoAnuncio.objects.create(
                    anuncio=self.object,
                    status_resultante=self.object.status_sincronizacao,
                    preco_anterior=preco_ant,
                    preco_proposto=self.object.preco_venda,
                    estoque_anterior=estoque_ant,
                    estoque_proposto=self.object.estoque_publicado,
                    usuario=self.request.user,
                    motivo=f"Edição manual do anúncio [{self.object.item_id_externo}] e composição ({self.object.tipo_composicao})"
                )

            messages.success(self.request, f"Anúncio [{self.object.item_id_externo}] atualizado com sucesso!")
            return redirect(reverse('anuncio_detail', kwargs={'pk': self.object.pk}))
        else:
            return self.render_to_response(self.get_context_data(form=form, formset=formset))


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
    O QUE FAZ: Remove um item da composição de um anúncio com blindagem transacional e snapshots de auditoria.
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado.")

        anuncio_id = self.kwargs.get('anuncio_id') or request.POST.get('anuncio_id')
        if anuncio_id:
            item = get_object_or_404(AnuncioComposicao, pk=self.kwargs['pk'], anuncio_id=anuncio_id)
        else:
            item = get_object_or_404(AnuncioComposicao, pk=self.kwargs['pk'])

        anuncio = item.anuncio
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        with transaction.atomic():
            snapshot_antes = [
                {
                    'composicao_id': comp.pk,
                    'produto_id': comp.produto_id,
                    'sku': comp.produto.sku,
                    'nome': comp.produto.nome,
                    'quantidade': comp.quantidade,
                    'estoque_fisico': comp.produto.estoque,
                }
                for comp in anuncio.itens_composicao.select_related('produto').all()
            ]
            cota_antes = anuncio.calcular_cota_disponivel()
            produto_nome = item.produto.nome
            produto_sku = item.produto.sku

            item.delete()

            snapshot_depois = [
                {
                    'composicao_id': comp.pk,
                    'produto_id': comp.produto_id,
                    'sku': comp.produto.sku,
                    'nome': comp.produto.nome,
                    'quantidade': comp.quantidade,
                    'estoque_fisico': comp.produto.estoque,
                }
                for comp in anuncio.itens_composicao.select_related('produto').all()
            ]
            cota_depois = anuncio.calcular_cota_disponivel()

            HistoricoSincronizacaoAnuncio.objects.create(
                anuncio=anuncio,
                status_resultante=anuncio.status_sincronizacao,
                preco_anterior=anuncio.preco_venda,
                preco_proposto=anuncio.preco_venda,
                estoque_anterior=cota_antes,
                estoque_proposto=cota_depois,
                usuario=request.user,
                motivo=f"Exclusão de componente da composição: [{produto_sku}] {produto_nome}",
                snapshot_antes=snapshot_antes,
                snapshot_depois=snapshot_depois,
            )

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
            preco_ant = anuncio.preco_venda
            cota_ant = anuncio.estoque_publicado
            anuncio.status_sincronizacao = 'ENVIADO'
            anuncio.save(update_fields=['status_sincronizacao', 'atualizado_em'])

            from apps.anuncios.models import HistoricoSincronizacaoAnuncio
            HistoricoSincronizacaoAnuncio.objects.create(
                anuncio=anuncio,
                status_resultante='ENVIADO',
                preco_anterior=preco_ant,
                preco_proposto=anuncio.preco_venda,
                estoque_anterior=cota_ant,
                estoque_proposto=res_est.get('estoque_sincronizado'),
                usuario=request.user,
                motivo="Sincronização manual unitária confirmada"
            )

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
    O QUE FAZ: Alterna a decisão do operador entre sincronizar ou cancelar/descartar alterações para o anúncio.
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

        from apps.anuncios.models import HistoricoSincronizacaoAnuncio
        preco_ant = anuncio.preco_venda
        cota_ant = anuncio.estoque_publicado
        cota_atual = anuncio.calcular_cota_disponivel()

        if anuncio.status_sincronizacao == 'CANCELADO':
            if anuncio.estoque_publicado != cota_atual:
                anuncio.status_sincronizacao = 'PENDENTE'
            else:
                anuncio.status_sincronizacao = 'ENVIADO'
            messages.success(request, f"Sincronização reativada para o anúncio [{anuncio.item_id_externo}] (Status: {anuncio.get_status_sincronizacao_display()}).")
            motivo = "Reativação da sincronização pelo operador"
        else:
            anuncio.status_sincronizacao = 'CANCELADO'
            messages.info(request, f"O anúncio [{anuncio.item_id_externo}] foi marcado como CANCELADO para sincronizações.")
            motivo = "Sincronização cancelada / descartada pelo operador"

        anuncio.save(update_fields=['status_sincronizacao', 'atualizado_em'])

        HistoricoSincronizacaoAnuncio.objects.create(
            anuncio=anuncio,
            status_resultante=anuncio.status_sincronizacao,
            preco_anterior=preco_ant,
            preco_proposto=preco_ant,
            estoque_anterior=cota_ant,
            estoque_proposto=cota_atual,
            usuario=request.user,
            motivo=motivo
        )

        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('anuncio_detail', pk=anuncio.pk)

