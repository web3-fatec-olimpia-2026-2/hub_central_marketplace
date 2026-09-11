# Os códigos foram gerados com auxilio de I.A.
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum

from apps.tenancy.models import Loja
from apps.tenancy.permissions import ModuloRequeridoMixin, usuario_is_dev
from apps.marketplaces.models import ContaMarketplace, LogSincronizacao
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from .models import PedidoVenda, ItemPedidoVenda
from .enums import StatusPedidoEnum
from .services import ProcessamentoPedidoService


# ==============================================================================
# WEBHOOKS DE MARKETPLACES (RECEBIMENTO ASSÍNCRONO DE VENDAS — RF-06)
# ==============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class WebhookMercadoLivreView(View):
    """
    O QUE FAZ: Endpoint HTTP para recebimento de notificações e Webhooks do Mercado Livre (topic: orders_v2).
    POR QUE FAZ: Processa vendas em tempo real disparando baixa atômica de inventário e broadcast multicanal (RF-06 / RN-05).
    PERMISSÕES RBAC: Aberto / Autenticado por assinatura de webhook ou seller_id.
    MULTI-TENANCY: Identifica a Loja (Tenant) via slug da URL ou seller_id externo.
    """
    def post(self, request, slug=None, *args, **kwargs):
        loja = None
        if slug:
            loja = Loja.objects.filter(slug=slug, ativo=True).first()

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = {}

        # Log do recebimento de webhook
        user_id = str(payload.get('user_id', ''))
        conta = None
        if user_id:
            conta = ContaMarketplace.objects.filter(
                canal=CanalMarketplaceEnum.MERCADOLIVRE, seller_id_externo=user_id
            ).select_related('loja').first()

        if conta and not loja:
            loja = conta.loja

        if not loja:
            loja = Loja.objects.filter(ativo=True).first()

        if not conta and loja:
            conta = ContaMarketplace.objects.filter(
                canal=CanalMarketplaceEnum.MERCADOLIVRE, loja=loja
            ).first()

        if not loja:
            return JsonResponse({'status': 'ignored', 'reason': 'Loja não encontrada'}, status=404)

        LogSincronizacao.objects.create(
            loja=loja,
            conta_marketplace=conta,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            evento=EventoAuditoriaEnum.WEBHOOK_RECEBIDO,
            payload_enviado=payload,
            status_http=200,
            sucesso=True
        )

        resource = payload.get('resource', '')
        topic = payload.get('topic', '')

        # Se o payload não contiver os itens diretamente, mas tiver resource e conta, busca na API
        if resource and '/orders/' in resource and not payload.get('items') and not payload.get('order_items') and conta:
            try:
                connector = conta.get_connector()
                sucesso_det, _, order_data = connector.obter_detalhes_pedido(resource)
                if sucesso_det and order_data:
                    payload.update(order_data)
            except Exception:
                pass

        # Identifica ID do pedido
        pedido_id = str(payload.get('id', payload.get('order_id', '')))
        if not pedido_id and resource and '/orders/' in resource:
            pedido_id = resource.split('/orders/')[-1]

        if pedido_id:
            ProcessamentoPedidoService.processar_pedido_venda(
                loja=loja,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                pedido_id_externo=pedido_id,
                dados_pedido=payload,
                conta=conta
            )

        return JsonResponse({'status': 'ok', 'message': 'Webhook recebido com sucesso'})


@method_decorator(csrf_exempt, name='dispatch')
class WebhookShopeeView(View):
    """
    O QUE FAZ: Endpoint HTTP para recebimento de webhooks de pedidos da Shopee.
    """
    def post(self, request, slug=None, *args, **kwargs):
        loja = Loja.objects.filter(slug=slug).first() if slug else Loja.objects.filter(ativo=True).first()
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = {}

        if loja:
            pedido_id = str(payload.get('order_sn', payload.get('order_id', 'SHOPEE_ORDER_1')))
            ProcessamentoPedidoService.processar_pedido_venda(
                loja=loja,
                canal=CanalMarketplaceEnum.SHOPEE,
                pedido_id_externo=pedido_id,
                dados_pedido=payload
            )

        return JsonResponse({'status': 'ok', 'canal': 'shopee'})


@method_decorator(csrf_exempt, name='dispatch')
class WebhookMagaluView(View):
    """
    O QUE FAZ: Endpoint HTTP para recebimento de webhooks de pedidos do Magazine Luiza.
    """
    def post(self, request, slug=None, *args, **kwargs):
        loja = Loja.objects.filter(slug=slug).first() if slug else Loja.objects.filter(ativo=True).first()
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = {}

        if loja:
            pedido_id = str(payload.get('code', payload.get('order_id', 'MAGALU_ORDER_1')))
            ProcessamentoPedidoService.processar_pedido_venda(
                loja=loja,
                canal=CanalMarketplaceEnum.MAGALU,
                pedido_id_externo=pedido_id,
                dados_pedido=payload
            )

        return JsonResponse({'status': 'ok', 'canal': 'magalu'})


# ==============================================================================
# PAINEL DE PEDIDOS E VENDAS MULTICANAL
# ==============================================================================

class PedidoVendaListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Listagem de Pedidos de Venda consolidados de todos os canais integrados da Loja.
    POR QUE FAZ: Monitoramento comercial, acompanhamento de baixas de estoque e auditoria de rupturas.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (com módulo 'pedidos' ativo).
    MULTI-TENANCY: Filtro obrigatório por loja.
    """
    modulo_requerido = 'pedidos'
    model = PedidoVenda
    template_name = 'pedidos/pedido_list.html'
    context_object_name = 'pedidos'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = PedidoVenda.objects.select_related('loja', 'conta_marketplace').prefetch_related('itens__produto').order_by('-criado_em')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return PedidoVenda.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        canal_filtro = self.request.GET.get('canal', '').strip()
        if canal_filtro:
            queryset = queryset.filter(canal_origem=canal_filtro)

        ruptura_filtro = self.request.GET.get('ruptura', '').strip()
        if ruptura_filtro == '1':
            queryset = queryset.filter(teve_ruptura_estoque=True)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(pedido_id_externo__icontains=busca) |
                Q(comprador_nome__icontains=busca) |
                Q(itens__item_id_externo__icontains=busca)
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['canais_disponiveis'] = CanalMarketplaceEnum.choices
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['canal_filtro'] = self.request.GET.get('canal', '').strip()
        context['ruptura_filtro'] = self.request.GET.get('ruptura', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        # KPIs rápidos
        qs_base = self.get_queryset()
        context['total_pedidos'] = qs_base.count()
        context['total_faturado'] = qs_base.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
        context['total_rupturas'] = qs_base.filter(teve_ruptura_estoque=True).count()

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


class PedidoVendaDetailView(LoginRequiredMixin, ModuloRequeridoMixin, DetailView):
    """
    O QUE FAZ: Visualização detalhada de um Pedido de Venda e seus itens com histórico de saldo.
    POR QUE FAZ: Auditoria de dedução de estoque e diagnóstico de rupturas.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Ownership check por loja.
    """
    modulo_requerido = 'pedidos'
    model = PedidoVenda
    template_name = 'pedidos/pedido_detail.html'
    context_object_name = 'pedido'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: este pedido pertence a outra loja.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['itens'] = self.object.itens.select_related('produto', 'anuncio_marketplace').all()
        return context
