# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo json para decodificação de payloads serializados recebidos via HTTP POST
import json

# Importa a classe Decimal para manipulação precisa de somatórios financeiros e valores monetários
from decimal import Decimal

# Importa atalhos fundamentais do Django para renderização de páginas, redirecionamento e busca de instâncias
from django.shortcuts import render, redirect, get_object_or_404

# Importa utilitários para resolução dinâmica e lazy de URLs nomeadas
from django.urls import reverse_lazy, reverse

# Importa as Class-Based Views genéricas padrão para listagem (ListView), detalhes (DetailView) e despachador base (View)
from django.views.generic import ListView, DetailView, View

# Importa o decorador csrf_exempt para permitir recepção de requisições POST externas enviadas por servidores de marketplaces
from django.views.decorators.csrf import csrf_exempt

# Importa o método method_decorator para aplicar decoradores de funções diretamente em classes de views (CBVs)
from django.utils.decorators import method_decorator

# Importa classes de resposta HTTP padrão e formatada em JSON
from django.http import JsonResponse, HttpResponse

# Importa o mixin de autenticação para restringir telas administrativas apenas a operadores com sessão ativa
from django.contrib.auth.mixins import LoginRequiredMixin

# Importa Q para consultas lógicas complexas (OR) e Sum para agregação estatística de valores totais
from django.db.models import Q, Sum

# Importa o modelo Loja para contextualização e resolução da organização tenant
from apps.tenancy.models import Loja

# Importa mixin de validação de módulo habilitado e a função de inspeção do papel de desenvolvimento (DEV)
from apps.tenancy.permissions import ModuloRequeridoMixin, usuario_is_dev

# Importa os modelos de Conta integrada e Log de telemetria técnica de sincronização
from apps.marketplaces.models import ContaMarketplace, LogSincronizacao

# Importa enumerações de canais integrados suportados e tipos de eventos auditáveis
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum

# Importa os modelos de persistência de pedidos de venda e itens comercializados
from .models import PedidoVenda, ItemPedidoVenda

# Importa as opções canônicas de status operacional de pedidos do Hub
from .enums import StatusPedidoEnum

# Importa o serviço especialista responsável pela ingestão, baixa concorrente de estoque e broadcast
from .services import ProcessamentoPedidoService


# ==============================================================================
# WEBHOOKS DE MARKETPLACES (RECEBIMENTO ASSÍNCRONO DE VENDAS — RF-06)
# ==============================================================================

# Aplica isenção de verificação de token CSRF ao despachador da view para recepção de requisições máquina-a-máquina
@method_decorator(csrf_exempt, name='dispatch')
class WebhookMercadoLivreView(View):
    # Início do bloco de docstring estrutural documentando o endpoint de notificações, RBAC e multi-tenancy
    """
    O QUE FAZ: Endpoint HTTP para recebimento de notificações e Webhooks do Mercado Livre (topic: orders_v2).
    POR QUE FAZ: Processa vendas em tempo real disparando baixa atômica de inventário e broadcast multicanal (RF-06 / RN-05).
    PERMISSÕES RBAC: Aberto / Autenticado por assinatura de webhook ou seller_id.
    MULTI-TENANCY: Identifica a Loja (Tenant) via slug da URL ou seller_id externo.
    """
    # Fim do bloco descritivo da classe

    # Manipulador HTTP POST para recepção de notificações assíncronas do Mercado Livre
    def post(self, request, slug=None, *args, **kwargs):
        # Inicializa a referência da loja de contexto
        loja = None
        # Se o slug foi fornecido no caminho da URL, busca a organização tenant correspondente
        if slug:
            loja = Loja.objects.filter(slug=slug, ativo=True).first()

        # Tenta decodificar o corpo da requisição HTTP como objeto JSON
        try:
            payload = json.loads(request.body.decode('utf-8'))
        # Em caso de falha de parser ou conteúdo malformado, assume payload como dicionário vazio
        except Exception:
            payload = {}

        # Log do recebimento de webhook
        # Extrai o identificador do vendedor (user_id) enviado pelo Mercado Livre
        user_id = str(payload.get('user_id', ''))
        conta = None
        # Se o user_id estiver preenchido, localiza a ContaMarketplace correspondente associada à loja
        if user_id:
            conta = ContaMarketplace.objects.filter(
                canal=CanalMarketplaceEnum.MERCADOLIVRE, seller_id_externo=user_id
            ).select_related('loja').first()

        # Se a conta foi encontrada e a loja ainda não havia sido identificada pela URL, resolve a loja através da conta
        if conta and not loja:
            loja = conta.loja

        # Fallback de contingência: se ainda assim não identificar a loja, adota a primeira loja ativa do sistema
        if not loja:
            loja = Loja.objects.filter(ativo=True).first()

        # Se a loja foi resolvida mas a conta ainda não, busca a conta padrão do Mercado Livre da referida loja
        if not conta and loja:
            conta = ContaMarketplace.objects.filter(
                canal=CanalMarketplaceEnum.MERCADOLIVRE, loja=loja
            ).first()

        # Se nenhuma loja for localizada para assumir a titularidade do webhook, rejeita com HTTP 404
        if not loja:
            return JsonResponse({'status': 'ignored', 'reason': 'Loja não encontrada'}, status=404)

        # Grava registro de telemetria técnica auditando a recepção da notificação bruta
        LogSincronizacao.objects.create(
            loja=loja,
            conta_marketplace=conta,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            evento=EventoAuditoriaEnum.WEBHOOK_RECEBIDO,
            payload_enviado=payload,
            status_http=200,
            sucesso=True
        )

        # Extrai metadados de tópico e identificador de recurso notificado
        resource = payload.get('resource', '')
        topic = payload.get('topic', '')

        # Se o payload não contiver os itens diretamente, mas tiver resource e conta, busca na API
        # Tratamento para notificações padrão do Mercado Livre que enviam apenas o resource da ordem (ex: /orders/123)
        if resource and '/orders/' in resource and not payload.get('items') and not payload.get('order_items') and conta:
            try:
                # Obtém o conector instanciado da conta e consulta os dados detalhados da ordem de venda
                connector = conta.get_connector()
                sucesso_det, _, order_data = connector.obter_detalhes_pedido(resource)
                # Se a busca foi bem-sucedida, enriquece o payload local com os dados recuperados
                if sucesso_det and order_data:
                    payload.update(order_data)
            # Trata exceções de comunicação prevenindo falha no webhook
            except Exception:
                pass

        # Identifica ID do pedido
        # Extrai o identificador da ordem no payload ou faz fallback extraindo do sufixo do resource
        pedido_id = str(payload.get('id', payload.get('order_id', '')))
        if not pedido_id and resource and '/orders/' in resource:
            pedido_id = resource.split('/orders/')[-1]

        # Se um identificador de pedido foi determinado, dispara o serviço central de processamento atômico
        if pedido_id:
            ProcessamentoPedidoService.processar_pedido_venda(
                loja=loja,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                pedido_id_externo=pedido_id,
                dados_pedido=payload,
                conta=conta
            )

        # Retorna resposta JSON confirmando o recebimento para que o marketplace não efetue retentativas
        return JsonResponse({'status': 'ok', 'message': 'Webhook recebido com sucesso'})


# Desabilita proteção CSRF para recepção dos webhooks da plataforma Shopee
@method_decorator(csrf_exempt, name='dispatch')
class WebhookShopeeView(View):
    # Início do bloco de docstring
    """
    O QUE FAZ: Endpoint HTTP para recebimento de webhooks de pedidos da Shopee.
    """
    # Fim da docstring explicativa

    # Trata requisição POST contendo notificações de pedidos originados na Shopee
    def post(self, request, slug=None, *args, **kwargs):
        # Resolve a loja via slug ou recorre à primeira loja ativa cadastrada
        loja = Loja.objects.filter(slug=slug).first() if slug else Loja.objects.filter(ativo=True).first()
        # Decodifica o payload JSON recebido
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = {}

        # Se a loja existir, extrai o número de série da ordem (order_sn) e encaminha para processamento
        if loja:
            pedido_id = str(payload.get('order_sn', payload.get('order_id', 'SHOPEE_ORDER_1')))
            ProcessamentoPedidoService.processar_pedido_venda(
                loja=loja,
                canal=CanalMarketplaceEnum.SHOPEE,
                pedido_id_externo=pedido_id,
                dados_pedido=payload
            )

        # Retorna confirmação de sucesso à API da Shopee
        return JsonResponse({'status': 'ok', 'canal': 'shopee'})


# Desabilita proteção CSRF para recepção dos webhooks do Magazine Luiza
@method_decorator(csrf_exempt, name='dispatch')
class WebhookMagaluView(View):
    # Início do bloco de docstring
    """
    O QUE FAZ: Endpoint HTTP para recebimento de webhooks de pedidos do Magazine Luiza.
    """
    # Fim da docstring explicativa

    # Trata requisição POST contendo notificações de pedidos originados no Magalu
    def post(self, request, slug=None, *args, **kwargs):
        # Resolve a loja via slug ou adota a primeira loja ativa
        loja = Loja.objects.filter(slug=slug).first() if slug else Loja.objects.filter(ativo=True).first()
        # Decodifica o corpo da requisição JSON
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = {}

        # Se a loja for localizada, extrai o código do pedido ('code') e encaminha para processamento atômico
        if loja:
            pedido_id = str(payload.get('code', payload.get('order_id', 'MAGALU_ORDER_1')))
            ProcessamentoPedidoService.processar_pedido_venda(
                loja=loja,
                canal=CanalMarketplaceEnum.MAGALU,
                pedido_id_externo=pedido_id,
                dados_pedido=payload
            )

        # Retorna resposta JSON confirmando o processamento
        return JsonResponse({'status': 'ok', 'canal': 'magalu'})


# ==============================================================================
# PAINEL DE PEDIDOS E VENDAS MULTICANAL
# ==============================================================================

# View baseada em classe para exibição e filtragem da lista consolidada de pedidos de venda
class PedidoVendaListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    # Início do bloco de docstring documentando objetivos operacionais, RBAC e isolamento multi-tenant
    """
    O QUE FAZ: Listagem de Pedidos de Venda consolidados de todos os canais integrados da Loja.
    POR QUE FAZ: Monitoramento comercial, acompanhamento de baixas de estoque e auditoria de rupturas.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (com módulo 'pedidos' ativo).
    MULTI-TENANCY: Filtro obrigatório por loja.
    """
    # Fim da docstring explicativa

    # Define o módulo do sistema exigido pelo ModuloRequeridoMixin
    modulo_requerido = 'pedidos'

    # Modelo ORM alvo da consulta
    model = PedidoVenda

    # Template HTML a ser renderizado
    template_name = 'pedidos/pedido_list.html'

    # Nome da variável que conterá a lista de pedidos no contexto do template
    context_object_name = 'pedidos'

    # Quantidade de pedidos exibidos por página para evitar sobrecarga de memória
    paginate_by = 20

    # Monta a consulta de pedidos aplicando filtros de tenant, canal, ruptura e busca textual
    def get_queryset(self):
        # Obtém o usuário conectado
        user = self.request.user
        # Inicia a consulta otimizando relacionamentos com select_related e prefetch_related para evitar problemas N+1
        queryset = PedidoVenda.objects.select_related('loja', 'conta_marketplace').prefetch_related('itens__produto').order_by('-criado_em')

        # Se o usuário for DEV, permite visualizar pedidos de qualquer tenant ou filtrar por uma loja específica
        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        # Se for usuário padrão do tenant, isola rigorosamente os pedidos pertencentes à sua própria loja
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return PedidoVenda.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        # Filtro opcional por canal de venda (ex.: mercadolivre, shopee)
        canal_filtro = self.request.GET.get('canal', '').strip()
        if canal_filtro:
            queryset = queryset.filter(canal_origem=canal_filtro)

        # Filtro específico para pedidos que sofreram ruptura de estoque (saldo negativo)
        ruptura_filtro = self.request.GET.get('ruptura', '').strip()
        if ruptura_filtro == '1':
            queryset = queryset.filter(teve_ruptura_estoque=True)

        # Filtro de busca textual abrangendo ID externo do pedido, nome do comprador e ID do item vendido
        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(pedido_id_externo__icontains=busca) |
                Q(comprador_nome__icontains=busca) |
                Q(itens__item_id_externo__icontains=busca)
            ).distinct()

        # Retorna o queryset devidamente filtrado
        return queryset

    # Complementa o contexto de dados para exibição de métricas (KPIs), filtros e controles visuais
    def get_context_data(self, **kwargs):
        # Obtém o contexto original da classe ancestral
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Injeta variáveis de controle e parâmetros de busca para manutenção do estado nos formulários
        context['is_dev'] = usuario_is_dev(user)
        context['canais_disponiveis'] = CanalMarketplaceEnum.choices
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['canal_filtro'] = self.request.GET.get('canal', '').strip()
        context['ruptura_filtro'] = self.request.GET.get('ruptura', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        # KPIs rápidos
        # Calcula contadores agregados sobre o conjunto filtrado de pedidos
        qs_base = self.get_queryset()
        context['total_pedidos'] = qs_base.count()
        context['total_faturado'] = qs_base.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
        context['total_rupturas'] = qs_base.filter(teve_ruptura_estoque=True).count()

        # Disponibiliza a lista de lojas para filtros globais de DEV ou injeta a loja do usuário autenticado
        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        # Retorna o contexto consolidado para renderização
        return context


# View baseada em classe para detalhamento e auditoria aprofundada de um pedido de venda individual
class PedidoVendaDetailView(LoginRequiredMixin, ModuloRequeridoMixin, DetailView):
    # Início do bloco de docstring estrutural documentando os objetivos e a validação de ownership
    """
    O QUE FAZ: Visualização detalhada de um Pedido de Venda e seus itens com histórico de saldo.
    POR QUE FAZ: Auditoria de dedução de estoque e diagnóstico de rupturas.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Ownership check por loja.
    """
    # Fim da docstring explicativa

    # Exige que a loja possua o módulo 'pedidos' ativo
    modulo_requerido = 'pedidos'

    # Modelo ORM alvo
    model = PedidoVenda

    # Template HTML correspondente à tela de detalhes
    template_name = 'pedidos/pedido_detail.html'

    # Nome da variável que conterá a instância do pedido no template
    context_object_name = 'pedido'

    # Sobrescreve o método get_object para impor validação estrita de posse (multi-tenancy ownership)
    def get_object(self, queryset=None):
        # Obtém o objeto solicitado via chave primária na URL
        obj = super().get_object(queryset=queryset)
        user = self.request.user

        # Se o usuário não for DEV, valida se o pedido pertence à mesma loja do perfil autenticado
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            # Levanta exceção de permissão caso o pedido pertença a outro tenant
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("Acesso negado: este pedido pertence a outra loja.")
        # Retorna o pedido autorizado
        return obj

    # Injeta a lista de itens vendidos do pedido com pré-carregamento dos produtos físicos e anúncios
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Otimiza a consulta dos itens do pedido evitando queries repetidas no template
        context['itens'] = self.object.itens.select_related('produto', 'anuncio_marketplace').all()
        return context
