# Os códigos foram gerados com auxilio de I.A.

# Importa atalhos do Django para renderização de páginas, redirecionamento e recuperação de instâncias com 404 automático
from django.shortcuts import render, redirect, get_object_or_404

# Importa utilitários de resolução reversa de URLs (síncrona e preguiçosa/lazy)
from django.urls import reverse_lazy, reverse

# Importa as classes base genéricas de visualização (CBVs) do Django para listagem, exibição, criação e edição
from django.views.generic import ListView, View, DetailView, CreateView, UpdateView

# Importa mixin nativo do Django que restringe o acesso exclusivamente a usuários autenticados
from django.contrib.auth.mixins import LoginRequiredMixin

# Importa o framework de mensagens do Django para exibição de feedbacks temporários (sucesso, aviso, erro)
from django.contrib import messages

# Importa o gerenciador de transações atômicas para garantir rollback completo em caso de falha no banco
from django.db import transaction

# Importa o encapsulador Q para construção de consultas complexas com operadores lógicos OR (|)
from django.db.models import Q

# Importa a exceção de segurança que aborta requisições não autorizadas disparando resposta HTTP 403 Forbidden
from django.core.exceptions import PermissionDenied

# Importa a entidade Loja representativa da organização/tenant do lojista
from apps.tenancy.models import Loja

# Importa funções e mixins customizados de controle de acesso (RBAC) e verificação de contratos
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, usuario_is_dev, pode_disparar_sincronizacao
)

# Importa a entidade representativa da credencial e canal de integração do marketplace
from apps.marketplaces.models import ContaMarketplace

# Importa o modelo de produtos físicos do catálogo mestre
from apps.catalogo.models import Produto

# Importa os modelos de Anúncio, de composição/ficha técnica e do log de histórico de auditoria
from apps.anuncios.models import Anuncio, AnuncioComposicao, HistoricoSincronizacaoAnuncio

# Importa o serviço encarregado da ingestão e conciliação de anúncios remotos
from apps.anuncios.services import AnuncioImportacaoService

# Importa os formulários e o formset inline para validação da ficha técnica do anúncio
from apps.anuncios.forms import AnuncioForm, AnuncioComposicaoInlineFormSet, AnuncioComposicaoForm


# Visualização baseada em classe que lista os anúncios com isolamento multi-tenant e paginação
class AnuncioListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    # Docstring documentando a responsabilidade, filtros e barreiras de permissão da tela de listagem
    """
    O QUE FAZ: Catálogo comercial multicanal com listagem de anúncios importados e seus respectivos kits.
    POR QUE FAZ: Permite ao lojista visualizar todos os anúncios nos marketplaces, status, preço,
                 estoque publicado vs cota física real calculada, e gerenciar composições/kits (Fase 1).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Isolamento restrito por Loja do usuário logado (ou todas se DEV).
    """

    # Define o módulo funcional exigido pelo tenant ('marketplaces') para autorizar o acesso à view
    modulo_requerido = 'marketplaces'

    # Aponta o modelo mestre que alimenta a consulta
    model = Anuncio

    # Caminho do template HTML responsável por renderizar a tabela de anúncios
    template_name = 'anuncios/anuncio_list.html'

    # Nome da variável disponibilizada no contexto do template contendo a lista de anúncios
    context_object_name = 'anuncios'

    # Define a quebra de paginação em 20 registros por página
    paginate_by = 20

    # Método que monta e filtra o QuerySet de acordo com as permissões e parâmetros de busca informados
    def get_queryset(self):
        # Obtém a referência do usuário autenticado a partir do objeto da requisição HTTP
        user = self.request.user

        # Constrói o QuerySet inicial otimizando consultas através de joins reversos (select_related e prefetch_related)
        queryset = (
            Anuncio.objects.select_related('conta', 'conta__loja')
            .prefetch_related('itens_composicao__produto')
            .order_by('-atualizado_em')
        )

        # Regra de privilégio: avalia se o usuário logado possui papel de desenvolvedor global (DEV)
        if usuario_is_dev(user):
            # Permite ao desenvolvedor alternar a visualização passando o parâmetro GET 'loja'
            loja_id = self.request.GET.get('loja', '').strip()
            # Se o ID da loja foi fornecido na query string, aplica o filtro da loja
            if loja_id:
                queryset = queryset.filter(conta__loja_id=loja_id)
        # Regra para usuários comuns e operadores regulares da plataforma
        else:
            # Recupera o perfil vinculado ao usuário
            perfil = getattr(user, 'perfil', None)
            # Se o usuário não possuir perfil ou loja atrelada, bloqueia o retorno entregando QuerySet vazio
            if not perfil or not perfil.loja:
                return Anuncio.objects.none()
            # Filtra estritamente os anúncios pertencentes à loja vinculada ao perfil do usuário
            queryset = queryset.filter(conta__loja=perfil.loja)

        # Filtro opcional por conta de marketplace específica
        conta_id = self.request.GET.get('conta', '').strip()
        if conta_id:
            queryset = queryset.filter(conta_id=conta_id)

        # Filtro opcional pelo status da publicação externa (active, paused, closed)
        status_filtro = self.request.GET.get('status', '').strip()
        if status_filtro:
            queryset = queryset.filter(status=status_filtro)

        # Filtro de busca textual abrangente (termo de busca)
        busca = self.request.GET.get('q', '').strip()
        if busca:
            # Aplica busca case-insensitive por ID externo, título do anúncio ou SKU do lojista
            queryset = queryset.filter(
                Q(item_id_externo__icontains=busca) |
                Q(titulo__icontains=busca) |
                Q(sku_vendedor__icontains=busca)
            )

        # Retorna o QuerySet refinado para consumo pelo motor de paginação
        return queryset

    # Método que enriquece os dados injetados no contexto do template de listagem
    def get_context_data(self, **kwargs):
        # Executa a geração original do dicionário de contexto da classe-mãe
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Injeta flag booleana indicando se o operador é DEV
        context['is_dev'] = usuario_is_dev(user)
        # Injeta permissão indicando se o operador pode acionar botões de sincronização manual
        context['pode_sincronizar'] = pode_disparar_sincronizacao(user)

        # Se for desenvolvedor, carrega todas as contas e lojas ativas para alimentar os dropdowns de filtro
        if context['is_dev']:
            context['contas_disponiveis'] = ContaMarketplace.objects.select_related('loja').filter(ativo=True)
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        # Se for lojista comum, restringe o filtro apenas às contas da sua própria empresa
        else:
            perfil = getattr(user, 'perfil', None)
            loja = getattr(perfil, 'loja', None)
            context['contas_disponiveis'] = ContaMarketplace.objects.filter(loja=loja, ativo=True) if loja else []

        # Preserva os valores dos filtros ativos para manter os inputs e selects preenchidos na interface
        context['conta_filtro'] = self.request.GET.get('conta', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()
        # Retorna o contexto final consolidado
        return context


# Visualização para detalhamento individual do anúncio, exibindo componentes físicos e histórico
class AnuncioDetailView(LoginRequiredMixin, ModuloRequeridoMixin, DetailView):
    # Docstring descritiva do escopo de visualização dos detalhes do anúncio
    """
    O QUE FAZ: Exibe detalhes do anúncio e permite gerenciar os produtos da composição (Kit).
    """

    # Módulo requerido para verificação de permissão contratual
    modulo_requerido = 'marketplaces'
    model = Anuncio
    template_name = 'anuncios/anuncio_detail.html'
    context_object_name = 'anuncio'

    # Sobrescreve a recuperação do objeto para aplicar barreira estrita de isolamento multi-tenant
    def get_object(self, queryset=None):
        # Obtém o anúncio via método padrão do Django
        anuncio = super().get_object(queryset=queryset)
        user = self.request.user

        # Se não for usuário DEV global, valida a compatibilidade de tenant
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            # Se o usuário não tiver perfil ou se a loja da conta do anúncio for diferente da loja do lojista
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                # Dispara HTTP 403 Forbidden impedindo a inspeção de ofertas de terceiros
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")

        # Retorna o anúncio autorizado
        return anuncio

    # Injeta formulários auxiliares e dados calculados na tela de detalhe
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Instancia formulário rápido para adicionar componente à composição
        context['form_composicao'] = AnuncioComposicaoForm(anuncio=self.object)
        # Calcula a cota física disponível a partir do inventário atual
        context['cota_calculada'] = self.object.calcular_cota_disponivel()
        # Carrega os últimos 30 registros da trilha de auditoria do ciclo de sincronização
        context['historicos_ciclo'] = self.object.historico_ciclo.select_related('usuario').order_by('-criado_em')[:30]
        return context


# Função utilitária privada para montar mapeamentos JSON de contas e produtos usados pelo JavaScript do front-end
def _adicionar_mapa_lojas_e_produtos(context, loja_fixa=None):
    # Docstring explicando a finalidade de isolamento no DOM e dinamismo reativo da interface
    """
    O QUE FAZ: Constrói mapeamentos JSON de contas->lojas e lojas->produtos ativos.
    POR QUE FAZ: Permite ao frontend re-filtrar reativamente os selects de produto ao alternar contas em criação.
                 Quando loja_fixa é informada (ex: em edição ou para operador não-DEV), restringe estritamente
                 os dados à loja em questão, impedindo que dados de outros tenants apareçam no HTML ou no DOM.
    """
    # Importações pontuais de dependências necessárias para geração do mapa JSON
    import json
    from apps.catalogo.enums import StatusProdutoEnum
    from apps.catalogo.models import Produto
    from apps.marketplaces.models import ContaMarketplace
    from apps.tenancy.models import Loja

    # Se a loja for fixa (usuário comum ou edição de anúncio existente), limita as consultas à loja
    if loja_fixa is not None:
        contas_qs = ContaMarketplace.objects.filter(loja=loja_fixa)
        lojas_qs = Loja.objects.filter(pk=loja_fixa.pk, ativo=True)
    # Se for desenvolvedor criando novo anúncio, carrega todas as lojas e contas ativas
    else:
        contas_qs = ContaMarketplace.objects.all()
        lojas_qs = Loja.objects.filter(ativo=True)

    # Dicionário relacionando o ID da conta ao ID da respectiva loja
    contas_map = {
        str(c.pk): str(c.loja_id)
        for c in contas_qs
    }

    # Dicionário agrupando produtos ativos por loja com rótulos formatados para preenchimento via JS
    produtos_map = {}
    for l in lojas_qs.prefetch_related('produtos'):
        produtos_map[str(l.pk)] = [
            {
                'id': p.pk,
                'label': f"[{p.sku}] {p.nome} — R$ {p.preco:.2f} (Estoque: {p.estoque})"
            }
            for p in l.produtos.filter(status=StatusProdutoEnum.ATIVO).order_by('nome')
        ]

    # Serializa os dicionários em formato string JSON para consumo seguro no template
    context['contas_lojas_json'] = json.dumps(contas_map)
    context['produtos_por_loja_json'] = json.dumps(produtos_map)


# Visualização para criação manual de anúncios com submissão de formset inline para kits
class AnuncioCreateView(LoginRequiredMixin, ModuloRequeridoMixin, CreateView):
    # Docstring que resume os pilares arquiteturais de criação direta de anúncios e conformidade com ADRs
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

    # Interceptador inicial de requisições que bloqueia perfis sem privilégios de sincronização/criação
    def dispatch(self, request, *args, **kwargs):
        # Se o usuário não possuir papel administrativo/supervisão nem for desenvolvedor
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            # Rejeita o acesso imediatamente com código HTTP 403
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para criar anúncios.")
        # Segue com o ciclo padrão da requisição
        return super().dispatch(request, *args, **kwargs)

    # Identifica a loja de destino da operação para balizar o queryset do formset
    def get_loja_alvo(self):
        user = self.request.user
        # Para usuários comuns, a loja alvo é sempre a loja associada ao seu perfil
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            return getattr(perfil, 'loja', None) if perfil else None

        # Para DEV, busca a conta enviada no formulário (POST ou GET) para inferir a loja correspondente
        conta_id = self.request.POST.get('conta') or self.request.GET.get('conta')
        if conta_id:
            conta = ContaMarketplace.objects.filter(pk=conta_id).select_related('loja').first()
            if conta:
                return conta.loja

        # Fallback de desenvolvedor: recupera a loja da primeira conta ativa do sistema
        primeira_conta = ContaMarketplace.objects.filter(ativo=True).select_related('loja').first()
        return primeira_conta.loja if primeira_conta else None

    # Preenche valores padrão nos inputs ao carregar o formulário vazio
    def get_initial(self):
        initial = super().get_initial()
        # Se a conta veio na query string, pré-seleciona seu valor no select
        if 'conta' in self.request.GET:
            initial['conta'] = self.request.GET.get('conta')
        # Para DEV, pré-seleciona a primeira conta ativa encontrada
        elif usuario_is_dev(self.request.user):
            primeira_conta = ContaMarketplace.objects.filter(ativo=True).first()
            if primeira_conta:
                initial['conta'] = primeira_conta.pk
        return initial

    # Injeta a referência do usuário autenticado no construtor do formulário principal
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    # Adiciona o formset inline e dados auxiliares ao template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        loja = self.get_loja_alvo()

        # Instancia o formset inline para gerenciar os itens da composição
        if 'formset' not in context:
            # Se for requisição POST, vincula os dados submetidos
            if self.request.POST:
                context['formset'] = AnuncioComposicaoInlineFormSet(
                    self.request.POST,
                    instance=self.object or Anuncio(),
                    loja=loja,
                    user=user
                )
            # Se for requisição GET, instancia o formset vazio
            else:
                context['formset'] = AnuncioComposicaoInlineFormSet(
                    instance=self.object or Anuncio(),
                    loja=loja,
                    user=user
                )
        # Sinaliza para a interface que se trata de uma inclusão e não edição
        context['is_edicao'] = False
        # Determina o escopo de dados JSON repassados ao JavaScript
        loja_fixa = None if usuario_is_dev(user) else loja
        _adicionar_mapa_lojas_e_produtos(context, loja_fixa=loja_fixa)
        return context

    # Executado quando os dados do formulário principal passam nas validações básicas
    def form_valid(self, form):
        user = self.request.user
        # Cria a instância do anúncio em memória sem persistir de imediato no banco
        self.object = form.save(commit=False)
        # Determina a loja a partir da conta selecionada
        loja = self.object.conta.loja if getattr(self.object, 'conta', None) else self.get_loja_alvo()

        # Instancia o formset inline associado ao formulário submetido para validação cruzada
        formset = AnuncioComposicaoInlineFormSet(
            self.request.POST,
            instance=self.object,
            loja=loja,
            user=user
        )

        # Se todas as linhas da composição do formset forem válidas (sem duplicidades e no mesmo tenant)
        if formset.is_valid():
            # Inicia transação atômica no banco de dados
            with transaction.atomic():
                # Grava o registro principal do anúncio
                self.object.save()
                # Associa a chave estrangeira do anúncio persistido ao formset
                formset.instance = self.object
                # Persiste fisicamente as linhas de composição no banco
                formset.save()

                # Calcula a cota vendável física com base nos componentes gravados
                cota = self.object.calcular_cota_disponivel()
                tem_composicao = self.object.itens_composicao.exists()
                # Se o anúncio possui ficha técnica definida, atualiza o snapshot local da cota
                if tem_composicao:
                    self.object.estoque_publicado = cota
                    self.object.save(update_fields=['estoque_publicado', 'atualizado_em'])

                # Registra o evento de criação na tabela de auditoria e ciclo de sincronização
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

            # Notifica mensagem de sucesso na interface
            messages.success(self.request, f"Anúncio [{self.object.item_id_externo}] criado com sucesso!")
            # Redireciona o usuário para a visualização detalhada do anúncio criado
            return redirect(reverse('anuncio_detail', kwargs={'pk': self.object.pk}))
        # Se houver erro de validação nas linhas da composição, reapresenta o formulário com as mensagens de erro
        else:
            return self.render_to_response(self.get_context_data(form=form, formset=formset))


# Visualização para alteração cadastral e gerenciamento dos componentes físicos de um anúncio
class AnuncioUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, UpdateView):
    # Docstring documentando a edição integrada de anúncio e ficha técnica
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

    # Bloqueia operadores sem privilégios antes de carregar o fluxo
    def dispatch(self, request, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para editar anúncios.")
        return super().dispatch(request, *args, **kwargs)

    # Recupera o anúncio aplicando validação de tenant rigorosa
    def get_object(self, queryset=None):
        anuncio = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")
        return anuncio

    # Repassa a referência do usuário autenticado para o formulário
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    # Constrói o contexto da tela de edição associando o formset com as linhas preexistentes
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # A composição do anúncio é restrita estritamente à loja da conta em questão (mesmo para DEV)
        loja = self.object.conta.loja

        # Conecta o formset às instâncias existentes de AnuncioComposicao associadas ao anúncio
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
        # Restringe o mapa dinâmico de produtos à loja da conta editada
        _adicionar_mapa_lojas_e_produtos(context, loja_fixa=loja)
        return context

    # Processa e persiste as alterações cadastrais e as modificações nos itens do kit
    def form_valid(self, form):
        user = self.request.user
        # A composição do anúncio é restrita estritamente à loja da conta em questão (mesmo para DEV)
        loja = self.object.conta.loja

        # Instancia o formset com os dados de mutação enviados
        formset = AnuncioComposicaoInlineFormSet(
            self.request.POST,
            instance=self.object,
            loja=loja,
            user=user
        )

        # Se as alterações no anúncio e em todos os componentes forem válidas
        if formset.is_valid():
            with transaction.atomic():
                # Salva o estado numérico anterior para fins de auditoria
                preco_ant = self.object.preco_venda
                estoque_ant = self.object.estoque_publicado

                # Salva as alterações nos campos do anúncio
                self.object = form.save()
                # Salva as adições, atualizações ou exclusões de itens da composição
                formset.save()

                # Recalcula a nova cota física vendável resultante
                cota = self.object.calcular_cota_disponivel()
                tem_composicao = self.object.itens_composicao.exists()
                if tem_composicao:
                    self.object.estoque_publicado = cota
                    self.object.save(update_fields=['estoque_publicado', 'atualizado_em'])

                # Registra a trilha de modificação no histórico de sincronização
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

            # Notifica mensagem de atualização bem-sucedida
            messages.success(self.request, f"Anúncio [{self.object.item_id_externo}] atualizado com sucesso!")
            return redirect(reverse('anuncio_detail', kwargs={'pk': self.object.pk}))
        # Re-renderiza a tela em caso de falha de validação no formset
        else:
            return self.render_to_response(self.get_context_data(form=form, formset=formset))


# Visualização que processa o comando de importação de anúncios remotos de uma conta integrada
class AnuncioImportarView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    # Docstring documentando a funcionalidade de carga sob demanda de anúncios
    """
    O QUE FAZ: Dispara a importação e atualização de anúncios de uma ContaMarketplace específica via conector.
    POR QUE FAZ: Permite ao lojista puxar o catálogo existente do Mercado Livre diretamente para o Hub (Fase 1).
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO bloqueado com 403).
    MULTI-TENANCY: Garante que o lojista só dispare importação para contas da sua própria loja.
    """

    modulo_requerido = 'marketplaces'

    # Processa requisições do tipo POST disparadas pelo botão de importação
    def post(self, request, pk, *args, **kwargs):
        # Validação de permissões de sincronização
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para importar anúncios.")

        # Obtém a conta alvo pela chave primária ou dispara 404
        conta = get_object_or_404(ContaMarketplace, pk=pk)

        # Checagem de tenant: impede que um operador dispare importação em contas de outras empresas
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta pertence a outra loja.")

        # Dispara a rotina de importação via camada de serviço
        resultado = AnuncioImportacaoService.importar_anuncios_da_conta(
            conta=conta,
            associar_produtos_por_sku=True,
            usuario=request.user
        )

        # Notifica feedback de acordo com o resultado da importação
        if resultado.get('sucesso'):
            messages.success(request, f"[{conta.get_canal_display()}] {resultado.get('mensagem')}")
        else:
            messages.error(request, f"[{conta.get_canal_display()}] Falha na importação: {resultado.get('mensagem')}")

        # Redireciona para a lista filtrando pela conta importada
        # Redireciona para a listagem de anúncios mantendo o filtro ativo na conta importada
        return redirect(f"{reverse('anuncio_list')}?conta={conta.pk}")


# Visualização para adição pontual de produto na composição (usada geralmente em janelas modais)
class AnuncioComposicaoCreateView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    # Docstring explicativa
    """
    O QUE FAZ: Adiciona um produto à composição do anúncio (Kit).
    """

    modulo_requerido = 'marketplaces'

    # Processa a inclusão via requisição POST
    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado.")

        anuncio = get_object_or_404(Anuncio, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        # Instancia e valida o formulário pontual de composição
        form = AnuncioComposicaoForm(request.POST, anuncio=anuncio)
        if form.is_valid():
            produto = form.cleaned_data['produto']
            quantidade = form.cleaned_data['quantidade']
            # Cria o vínculo ou atualiza o fator multiplicador caso o produto já conste na composição
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

        # Retorna para a visualização de detalhe do anúncio
        return redirect('anuncio_detail', pk=anuncio.pk)


# Visualização para exclusão de um componente físico da ficha técnica de um anúncio
class AnuncioComposicaoDeleteView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    # Docstring detalhando a blindagem transacional e a captura de snapshots de auditoria
    """
    O QUE FAZ: Remove um item da composição de um anúncio com blindagem transacional e snapshots de auditoria.
    """

    modulo_requerido = 'marketplaces'

    # Executa a remoção do vínculo em resposta a um comando POST
    def post(self, request, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado.")

        # Localiza o registro de composição considerando o anúncio_id caso presente na rota
        anuncio_id = self.kwargs.get('anuncio_id') or request.POST.get('anuncio_id')
        if anuncio_id:
            item = get_object_or_404(AnuncioComposicao, pk=self.kwargs['pk'], anuncio_id=anuncio_id)
        else:
            item = get_object_or_404(AnuncioComposicao, pk=self.kwargs['pk'])

        # Valida tenant entre a loja do usuário e a loja dona do anúncio
        anuncio = item.anuncio
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        # Inicia transação atômica para registro dos snapshots de auditoria antes e depois da exclusão
        with transaction.atomic():
            # Serializa a composição completa antes da operação
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

            # Executa a exclusão física do item de composição (sem remover o produto do catálogo)
            item.delete()

            # Serializa a composição restante após a exclusão do componente
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

            # Grava registro na trilha de auditoria contendo os dois snapshots para histórico
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


# Visualização para disparar a sincronização imediata do estoque e preço com a API externa
class AnuncioSincronizarView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    # Docstring detalhando o disparo forçado de atualização no marketplace
    """
    O QUE FAZ: Dispara a sincronização manual e imediata de estoque e preço do anúncio no marketplace.
    POR QUE FAZ: Permite ao lojista/gestor sincronizar sob demanda com a API do canal (ex: Mercado Livre).
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Validação estrita por loja.
    """

    modulo_requerido = 'marketplaces'

    # Processa o disparo da sincronização
    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para sincronizar anúncios.")

        anuncio = get_object_or_404(Anuncio, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")

        # Importa e executa os métodos do serviço de sincronização com forcar=True para ignorar regras de idempotência
        from apps.anuncios.services import AnuncioSincronizacaoService
        res_est = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(anuncio, usuario=request.user, forcar=True)
        res_prc = AnuncioSincronizacaoService.sincronizar_preco_anuncio(anuncio, anuncio.preco_venda, usuario=request.user, forcar=True)

        # Se a sincronização do estoque no conector obteve sucesso
        if res_est.get('sucesso'):
            preco_ant = anuncio.preco_venda
            cota_ant = anuncio.estoque_publicado
            # Atualiza o status local para 'ENVIADO'
            anuncio.status_sincronizacao = 'ENVIADO'
            anuncio.save(update_fields=['status_sincronizacao', 'atualizado_em'])

            # Registra no histórico de auditoria
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

            # Notifica mensagem de sucesso
            messages.success(
                request,
                f"Anúncio [{anuncio.item_id_externo}] sincronizado com sucesso no canal {anuncio.conta.get_canal_display()}! "
                f"(Estoque: {res_est.get('estoque_sincronizado')} un., Preço: R$ {anuncio.preco_venda:.2f})"
            )
        # Em caso de recusa da API remota
        else:
            messages.error(
                request,
                f"Falha ao sincronizar estoque do anúncio [{anuncio.item_id_externo}]: {res_est.get('mensagem')}"
            )

        # Retorna o operador para a página de origem (HTTP Referer) ou para a tela de detalhes
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('anuncio_detail', pk=anuncio.pk)


# Visualização para alternar o status de cancelamento/ignorar sincronização do anúncio
class AnuncioToggleIgnorarView(LoginRequiredMixin, ModuloRequeridoMixin, View):
    # Docstring explicando a alternância entre ignorar ou reativar a sincronização
    """
    O QUE FAZ: Alterna a decisão do operador entre sincronizar ou cancelar/descartar alterações para o anúncio.
    POR QUE FAZ: Permite ao operador proteger kits ou anúncios com estratégias de preço/estoque independentes.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    """

    modulo_requerido = 'marketplaces'

    # Processa a alteração de status
    def post(self, request, pk, *args, **kwargs):
        if not pode_disparar_sincronizacao(request.user) and not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: seu perfil não tem permissão para alterar anúncios.")

        anuncio = get_object_or_404(Anuncio, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or anuncio.conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este anúncio pertence a outra loja.")

        # Guarda valores correntes para auditoria
        from apps.anuncios.models import HistoricoSincronizacaoAnuncio
        preco_ant = anuncio.preco_venda
        cota_ant = anuncio.estoque_publicado
        cota_atual = anuncio.calcular_cota_disponivel()

        # Se o anúncio já estiver como CANCELADO, reativa a sincronização
        if anuncio.status_sincronizacao == 'CANCELADO':
            # Se houver divergência entre o estoque anunciado e a cota atual, define como PENDENTE
            if anuncio.estoque_publicado != cota_atual:
                anuncio.status_sincronizacao = 'PENDENTE'
            # Se os números forem idênticos, define diretamente como ENVIADO
            else:
                anuncio.status_sincronizacao = 'ENVIADO'
            messages.success(request, f"Sincronização reativada para o anúncio [{anuncio.item_id_externo}] (Status: {anuncio.get_status_sincronizacao_display()}).")
            motivo = "Reativação da sincronização pelo operador"
        # Se o anúncio estiver ativo/pendente, altera para CANCELADO
        else:
            anuncio.status_sincronizacao = 'CANCELADO'
            messages.info(request, f"O anúncio [{anuncio.item_id_externo}] foi marcado como CANCELADO para sincronizações.")
            motivo = "Sincronização cancelada / descartada pelo operador"

        # Salva o novo status da sincronização
        anuncio.save(update_fields=['status_sincronizacao', 'atualizado_em'])

        # Registra a decisão do operador no histórico do ciclo
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

        # Redireciona para o referer ou para os detalhes do anúncio
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('anuncio_detail', pk=anuncio.pk)
