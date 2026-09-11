# Os códigos foram gerados com auxilio de I.A.
import logging
import traceback
from decimal import Decimal
from typing import Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone

from apps.tenancy.models import Loja
from apps.marketplaces.models import ContaMarketplace, WebhookEventLog, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum, WebhookStatusEnum
from apps.anuncios.models import Anuncio
from apps.catalogo.models import Produto, AnuncioMarketplace
from apps.pedidos.models import PedidoVenda, ItemPedidoVenda
from apps.pedidos.enums import StatusPedidoEnum

logger = logging.getLogger(__name__)


class MercadoLivreWebhookService:
    """
    O QUE FAZ: Serviço central de recepção, validação, idempotência estrita e baixa de estoque para webhooks do Mercado Livre.
    POR QUE FAZ:
      1. Garante que notificações duplicadas (retentativas de rede, atualizações intermediárias de status) sejam registradas como IGNORADO e NÃO debitem estoque mais de uma vez.
      2. Executa a baixa atômica de estoque físico em Produto com lock pessimista (select_for_update), cobrindo anúncios unitários e kits com multiplicadores via AnuncioComposicao.
      3. Dispara automaticamente recálculo e broadcast de cotas através dos sinais post_save da Fase 2.
    """

    @classmethod
    def processar_notificacao(cls, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """
        O QUE FAZ: Ponto de entrada de processamento da notificação do webhook.
        RETORNO: (status_code_http: int, resposta_json: dict)
        """
        if not isinstance(payload, dict) or not payload:
            return 400, {"error": "Payload JSON inválido ou vazio."}

        topic = str(payload.get('topic', '')).strip()
        resource = str(payload.get('resource', '')).strip()
        user_id = str(payload.get('user_id', '')).strip()

        if not topic or not resource:
            return 400, {"error": "Campos obrigatórios 'topic' e 'resource' não informados no payload."}

        # 1. Tópicos não relacionados a pedidos (ex: items, questions, etc.)
        if topic != 'orders_v2':
            WebhookEventLog.objects.create(
                marketplace='mercadolivre',
                topic=topic,
                resource=resource,
                user_id=user_id,
                payload_raw=payload,
                status=WebhookStatusEnum.IGNORADO,
                error_log=f"Tópico '{topic}' ignorado. Apenas 'orders_v2' dispara movimentação de estoque.",
                processed_at=timezone.now()
            )
            return 200, {
                "status": "ignored",
                "message": f"Tópico '{topic}' recebido e ignorado com sucesso (sem impacto em estoque)."
            }

        # 2. Idempotência Estrita para 'orders_v2':
        # Verifica atomicamente se já existe evento com status PROCESSADO ou PROCESSANDO
        with transaction.atomic():
            logs_existentes = WebhookEventLog.objects.select_for_update().filter(
                marketplace='mercadolivre',
                resource=resource
            )

            if logs_existentes.filter(status=WebhookStatusEnum.PROCESSADO).exists():
                # Pedido já processado com sucesso anteriormente (duplicidade)
                WebhookEventLog.objects.create(
                    marketplace='mercadolivre',
                    topic=topic,
                    resource=resource,
                    user_id=user_id,
                    payload_raw=payload,
                    status=WebhookStatusEnum.IGNORADO,
                    error_log="Notificação duplicada ignorada: pedido já processado anteriormente.",
                    processed_at=timezone.now()
                )
                logger.info(f"[Webhook Meli] Pedido '{resource}' duplicado recebido e ignorado.")
                return 200, {
                    "status": "ignored",
                    "message": f"Notificação duplicada para '{resource}'. Nenhuma baixa adicional de estoque foi executada."
                }

            if logs_existentes.filter(status=WebhookStatusEnum.PROCESSANDO).exists():
                # Pedido já está sendo processado por uma requisição simultânea no mesmo milissegundo
                WebhookEventLog.objects.create(
                    marketplace='mercadolivre',
                    topic=topic,
                    resource=resource,
                    user_id=user_id,
                    payload_raw=payload,
                    status=WebhookStatusEnum.IGNORADO,
                    error_log="Notificação concorrente ignorada: pedido já está em processamento.",
                    processed_at=timezone.now()
                )
                logger.info(f"[Webhook Meli] Pedido '{resource}' em processamento concorrente ignorado.")
                return 200, {
                    "status": "ignored",
                    "message": f"Pedido '{resource}' já em processamento por outra requisição concorrente."
                }

            # Reivindica o processamento registrando o log inicial como PROCESSANDO
            event_log = WebhookEventLog.objects.create(
                marketplace='mercadolivre',
                topic=topic,
                resource=resource,
                user_id=user_id,
                payload_raw=payload,
                status=WebhookStatusEnum.PROCESSANDO
            )

        # 3. Execução da busca dos dados do pedido e baixa atômica
        try:
            conta = None
            if user_id:
                conta = ContaMarketplace.objects.filter(
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    seller_id_externo=user_id,
                    ativo=True
                ).select_related('loja').first()

            if not conta:
                conta = ContaMarketplace.objects.filter(
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    ativo=True
                ).select_related('loja').first()

            # Obtém os detalhes do pedido
            order_data = payload.get('order_data')
            if not order_data:
                if not conta:
                    raise ValueError(f"Nenhuma ContaMarketplace do Mercado Livre encontrada para o seller_id '{user_id}'.")

                connector = conta.get_connector()
                sucesso, msg_ped, order_data = connector.obter_detalhes_pedido(resource)
                if not sucesso:
                    raise RuntimeError(f"Falha ao obter detalhes do pedido na API: {msg_ped}")

            order_items = order_data.get('order_items', order_data.get('items', []))
            if not order_items:
                raise ValueError(f"Pedido '{resource}' retornado sem itens em 'order_items'.")

            # Identificação da Loja
            loja_pedido = conta.loja if conta else None
            if not loja_pedido:
                loja_pedido = Loja.objects.filter(ativo=True).first()

            # Baixa atômica de estoque por produto e persistência do Pedido (RF-06 / RN-05)
            with transaction.atomic():
                pedido_id_ext = str(
                    order_data.get('id')
                    or (resource.split('/orders/')[-1] if '/orders/' in resource else resource)
                ).strip()

                buyer = order_data.get('buyer') or {}
                comprador_nome = (
                    f"{buyer.get('first_name', '')} {buyer.get('last_name', '')}".strip()
                    or buyer.get('nickname')
                    or buyer.get('name')
                    or "Comprador Mercado Livre"
                )
                comprador_doc = (
                    (buyer.get('billing_info') or {}).get('doc_number')
                    or buyer.get('document')
                    or ""
                )
                valor_total = Decimal(str(order_data.get('total_amount', order_data.get('valor_total', '0.00'))))
                valor_frete = Decimal(str(order_data.get('shipping_cost', (order_data.get('shipping') or {}).get('cost', '0.00'))))

                pedido, _ = PedidoVenda.objects.update_or_create(
                    loja=loja_pedido,
                    canal_origem=CanalMarketplaceEnum.MERCADOLIVRE,
                    pedido_id_externo=pedido_id_ext,
                    defaults={
                        'conta_marketplace': conta,
                        'status_externo': str(order_data.get('status', 'paid')),
                        'status': StatusPedidoEnum.PAGO,
                        'comprador_nome': comprador_nome,
                        'comprador_documento': comprador_doc,
                        'valor_total': valor_total,
                        'valor_frete': valor_frete,
                        'payload_original': order_data,
                        'processado_com_sucesso': True,
                    }
                )

                # Limpa itens pré-existentes se for reprocessamento
                pedido.itens.all().delete()
                houve_ruptura = False

                for order_item in order_items:
                    item_info = order_item.get('item', {}) if isinstance(order_item.get('item'), dict) else order_item
                    item_id = item_info.get('id') or order_item.get('item_id') or order_item.get('id')
                    item_id_externo = str(item_id or '').strip()
                    qtd_vendida = int(order_item.get('quantity', 1))
                    unit_price = Decimal(str(order_item.get('unit_price') or order_item.get('full_unit_price') or '0.00'))
                    titulo_item = item_info.get('title') or order_item.get('title', '')

                    # Localiza o Anuncio no sistema
                    anuncio = None
                    if conta:
                        anuncio = Anuncio.objects.filter(
                            conta=conta, item_id_externo=item_id_externo
                        ).prefetch_related('itens_composicao__produto').first()

                    if not anuncio:
                        anuncio = Anuncio.objects.filter(
                            item_id_externo=item_id_externo
                        ).prefetch_related('itens_composicao__produto').first()

                    anuncio_mkt = None
                    if conta:
                        anuncio_mkt = AnuncioMarketplace.objects.filter(
                            conta_marketplace=conta, item_id_externo=item_id_externo
                        ).first()

                    prod_vinculado = None
                    saldo_ant_item = None
                    novo_saldo_item = None
                    item_ruptura = False

                    if anuncio:
                        if not titulo_item:
                            titulo_item = anuncio.titulo
                        composicoes = anuncio.itens_composicao.all()
                        if composicoes.exists():
                            for comp in composicoes:
                                prod_locked = Produto.objects.select_for_update().get(pk=comp.produto_id)
                                prod_vinculado = prod_locked
                                qtd_baixa = qtd_vendida * comp.quantidade
                                saldo_ant = prod_locked.estoque
                                novo_saldo = max(0, saldo_ant - qtd_baixa)
                                saldo_ant_item = saldo_ant
                                novo_saldo_item = novo_saldo

                                if saldo_ant < qtd_baixa:
                                    item_ruptura = True
                                    houve_ruptura = True

                                prod_locked._motivo_alteracao = 'VENDA_MARKETPLACE'
                                prod_locked.estoque = novo_saldo
                                prod_locked.save(update_fields=['estoque', 'atualizado_em'])

                                LogAuditoria.objects.create(
                                    loja=prod_locked.loja,
                                    evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
                                    detalhes=(
                                        f"Baixa automática de estoque por venda: Pedido {resource}. "
                                        f"Anúncio: {anuncio.item_id_externo} ({anuncio.titulo[:30]}). "
                                        f"Qtd vendida: {qtd_vendida} un. Multiplicador: {comp.quantidade}x. "
                                        f"Total baixado do SKU '{prod_locked.sku}': {qtd_baixa} un. "
                                        f"Saldo anterior: {saldo_ant} -> Novo saldo: {novo_saldo} un."
                                    )
                                )
                        else:
                            # Anúncio sem composição direta: tenta por sku_vendedor
                            sku = anuncio.sku_vendedor or item_info.get('seller_sku')
                            if sku:
                                prod_locked = Produto.objects.select_for_update().filter(
                                    loja=anuncio.conta.loja, sku=sku
                                ).first()
                                if prod_locked:
                                    prod_vinculado = prod_locked
                                    qtd_baixa = qtd_vendida
                                    saldo_ant = prod_locked.estoque
                                    novo_saldo = max(0, saldo_ant - qtd_baixa)
                                    saldo_ant_item = saldo_ant
                                    novo_saldo_item = novo_saldo

                                    if saldo_ant < qtd_baixa:
                                        item_ruptura = True
                                        houve_ruptura = True

                                    prod_locked._motivo_alteracao = 'VENDA_MARKETPLACE'
                                    prod_locked.estoque = novo_saldo
                                    prod_locked.save(update_fields=['estoque', 'atualizado_em'])

                                    anuncio.status_sincronizacao = 'ENVIADO'
                                    anuncio.estoque_publicado = novo_saldo
                                    anuncio.save(update_fields=['status_sincronizacao', 'estoque_publicado', 'atualizado_em'])

                                    LogAuditoria.objects.create(
                                        loja=prod_locked.loja,
                                        evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
                                        detalhes=(
                                            f"Baixa automática de estoque por venda (via SKU {sku}): Pedido {resource}. "
                                            f"Total baixado do SKU '{prod_locked.sku}': {qtd_baixa} un. "
                                            f"Saldo anterior: {saldo_ant} -> Novo saldo: {novo_saldo} un."
                                        )
                                    )
                    else:
                        # Fallback: tenta localizar produto diretamente por SKU do seller
                        sku = item_info.get('seller_sku', item_info.get('seller_custom_field'))
                        loja = conta.loja if conta else loja_pedido
                        if sku and loja:
                            prod_locked = Produto.objects.select_for_update().filter(
                                loja=loja, sku=sku
                            ).first()
                            if prod_locked:
                                prod_vinculado = prod_locked
                                qtd_baixa = qtd_vendida
                                saldo_ant = prod_locked.estoque
                                novo_saldo = max(0, saldo_ant - qtd_baixa)
                                saldo_ant_item = saldo_ant
                                novo_saldo_item = novo_saldo

                                if saldo_ant < qtd_baixa:
                                    item_ruptura = True
                                    houve_ruptura = True

                                prod_locked._motivo_alteracao = 'VENDA_MARKETPLACE'
                                prod_locked.estoque = novo_saldo
                                prod_locked.save(update_fields=['estoque', 'atualizado_em'])

                                LogAuditoria.objects.create(
                                    loja=prod_locked.loja,
                                    evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
                                    detalhes=(
                                        f"Baixa automática de estoque por venda (via SKU {sku}): Pedido {resource}. "
                                        f"Total baixado do SKU '{prod_locked.sku}': {qtd_baixa} un. "
                                        f"Saldo anterior: {saldo_ant} -> Novo saldo: {novo_saldo} un."
                                    )
                                )

                    # Registra ItemPedidoVenda
                    ItemPedidoVenda.objects.create(
                        pedido=pedido,
                        produto=prod_vinculado,
                        anuncio_marketplace=anuncio_mkt,
                        item_id_externo=item_id_externo,
                        titulo_anuncio=titulo_item or f"Item {item_id_externo}",
                        quantidade=qtd_vendida,
                        preco_unitario=unit_price,
                        estoque_baixado=True if prod_vinculado else False,
                        estoque_anterior=saldo_ant_item,
                        estoque_posterior=novo_saldo_item,
                        ruptura_estoque=item_ruptura
                    )

                if houve_ruptura:
                    pedido.teve_ruptura_estoque = True
                    pedido.save(update_fields=['teve_ruptura_estoque', 'atualizado_em'])

                # Sucesso: atualiza log para PROCESSADO
                event_log.status = WebhookStatusEnum.PROCESSADO
                event_log.processed_at = timezone.now()
                event_log.save(update_fields=['status', 'processed_at'])

            logger.info(f"[Webhook Meli] Pedido '{resource}' processado com sucesso!")
            return 200, {
                "status": "ok",
                "message": f"Pedido '{resource}' processado com sucesso com baixa atômica de estoque."
            }

        except Exception as exc:
            erro_str = f"{str(exc)}\n{traceback.format_exc()}"
            logger.error(f"[Webhook Meli] Erro ao processar pedido '{resource}': {erro_str}")
            event_log.status = WebhookStatusEnum.ERRO
            event_log.error_log = erro_str
            event_log.processed_at = timezone.now()
            event_log.save(update_fields=['status', 'error_log', 'processed_at'])

            # Retorna 200 OK para o Mercado Livre não reenviar em loop caso seja erro lógico,
            # com payload indicando erro registrado internamente para reprocessamento
            return 200, {
                "status": "error",
                "message": f"Falha no processamento interno do pedido '{resource}'. Evento registrado como ERRO."
            }
