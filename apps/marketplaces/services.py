# Os códigos foram gerados com auxilio de I.A.
import logging
import traceback
from decimal import Decimal
from typing import Dict, Any, Tuple
from django.db import transaction, IntegrityError
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

        # 2. Idempotência Estrita e Concorrência para 'orders_v2':
        pedido_id_ext = str(
            payload.get('id')
            or (payload.get('order_data') or {}).get('id')
            or (resource.split('/orders/')[-1] if '/orders/' in resource else resource)
        ).strip()

        with transaction.atomic():
            # A. Idempotência por PedidoVenda: se já persistido com sucesso, bloqueia reprocessamento
            if pedido_id_ext:
                pedido_existente = PedidoVenda.objects.select_for_update().filter(
                    canal_origem=CanalMarketplaceEnum.MERCADOLIVRE,
                    pedido_id_externo=pedido_id_ext
                ).first()

                if pedido_existente:
                    WebhookEventLog.objects.create(
                        marketplace='mercadolivre',
                        topic=topic,
                        resource=resource,
                        user_id=user_id,
                        payload_raw=payload,
                        status=WebhookStatusEnum.IGNORADO,
                        error_log=f"Notificação duplicada ignorada: PedidoVenda #{pedido_id_ext} já persistido anteriormente no Hub.",
                        processed_at=timezone.now()
                    )
                    logger.info(f"[Webhook Meli] Pedido '{pedido_id_ext}' duplicado recebido e ignorado.")
                    return 200, {
                        "status": "ignored",
                        "message": f"Notificação duplicada para '{resource}'. Pedido #{pedido_id_ext} já existente no Hub."
                    }

            # B. Concorrência: Verifica se há requisição simultânea ATIVAMENTE em processamento
            log_processando = WebhookEventLog.objects.select_for_update().filter(
                marketplace='mercadolivre',
                resource=resource,
                status=WebhookStatusEnum.PROCESSANDO
            ).first()

            if log_processando:
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
            # Tarefa 0 / Ajuste 1: Busca estrita sem fallbacks para primeira conta
            conta = None
            if user_id:
                conta = ContaMarketplace.objects.filter(
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    seller_id_externo=user_id
                ).select_related('loja').first()

            if not conta:
                msg_erro = f"ContaMarketplace não localizada para o seller_id {user_id}"
                logger.error(f"[Webhook Meli] {msg_erro} (resource: {resource})")
                event_log.status = WebhookStatusEnum.ERRO
                event_log.error_log = msg_erro
                event_log.processed_at = timezone.now()
                event_log.save(update_fields=['status', 'error_log', 'processed_at'])
                return 200, {
                    "status": "error",
                    "message": msg_erro
                }

            if not conta.ativo:
                msg_erro = f"ContaMarketplace encontrada para o seller_id {user_id}, mas está inativa"
                logger.error(f"[Webhook Meli] {msg_erro} (resource: {resource})")
                event_log.status = WebhookStatusEnum.ERRO
                event_log.error_log = msg_erro
                event_log.processed_at = timezone.now()
                event_log.save(update_fields=['status', 'error_log', 'processed_at'])
                return 200, {
                    "status": "error",
                    "message": msg_erro
                }

            # Obtém os detalhes do pedido
            order_data = payload.get('order_data')
            if not order_data:
                connector = conta.get_connector()
                sucesso, msg_ped, order_data = connector.obter_detalhes_pedido(resource)
                if not sucesso:
                    raise RuntimeError(f"Falha ao obter detalhes do pedido na API: {msg_ped}")

            order_items = order_data.get('order_items', order_data.get('items', []))
            if not order_items:
                raise ValueError(f"Pedido '{resource}' retornado sem itens em 'order_items'.")

            # Identificação da Loja rigorosamente a partir da ContaMarketplace
            loja_pedido = conta.loja

            # Baixa atômica de estoque por produto e persistência do Pedido (RF-06 / RN-05 / Tarefa 2)
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

                # Ajuste 2: Proteção de concorrência com captura de IntegrityError no banco
                try:
                    pedido, _ = PedidoVenda.objects.update_or_create(
                        canal_origem=CanalMarketplaceEnum.MERCADOLIVRE,
                        pedido_id_externo=pedido_id_ext,
                        defaults={
                            'loja': loja_pedido,
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
                except IntegrityError as ie:
                    logger.warning(f"[Webhook Meli] Colisão concorrente capturada por constraint de banco para pedido #{pedido_id_ext}: {ie}")
                    event_log.status = WebhookStatusEnum.IGNORADO
                    event_log.error_log = f"Notificação concorrente bloqueada por constraint de banco: Pedido #{pedido_id_ext} gravado simultaneamente."
                    event_log.processed_at = timezone.now()
                    event_log.save(update_fields=['status', 'error_log', 'processed_at'])
                    return 200, {
                        "status": "ignored",
                        "message": f"Notificação duplicada/concorrente para '{resource}'. Pedido #{pedido_id_ext} já gravado por transação concorrente."
                    }

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

                    # Localiza o Anuncio no sistema estritamente no escopo da conta
                    anuncio = Anuncio.objects.filter(
                        conta=conta, item_id_externo=item_id_externo
                    ).prefetch_related('itens_composicao__produto').first()

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
                    elif anuncio_mkt and anuncio_mkt.produto:
                        prod_locked = Produto.objects.select_for_update().get(pk=anuncio_mkt.produto_id)
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
                    else:
                        # Fallback por SKU do seller dentro da loja identificada
                        sku = item_info.get('seller_sku', item_info.get('seller_custom_field'))
                        if sku:
                            prod_locked = Produto.objects.select_for_update().filter(
                                loja=loja_pedido, sku=sku
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

                    # Tarefa 2: Se o produto não foi localizado no catálogo da loja, registra com status pendente de vínculo
                    if prod_vinculado:
                        status_integracao_item = 'vinculado'
                        estoque_baixado_item = True
                    else:
                        status_integracao_item = 'pendente_vinculo'
                        estoque_baixado_item = False
                        LogAuditoria.objects.create(
                            loja=loja_pedido,
                            evento=EventoAuditoriaEnum.ALERTA_RUPTURA_ESTOQUE,
                            detalhes=(
                                f"AVISO DE RECONCILIAÇÃO: Item '{item_id_externo}' ({titulo_item}) do pedido #{pedido_id_ext} "
                                f"não possui anúncio ou produto vinculado no catálogo da loja '{loja_pedido.nome}'. "
                                f"Item gravado com status 'pendente_vinculo' para reconciliação manual posterior."
                            )
                        )
                        logger.warning(
                            f"[Webhook Meli] Item '{item_id_externo}' sem produto vinculado na loja '{loja_pedido.nome}'. "
                            f"Gravado com status_integracao='pendente_vinculo'."
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
                        status_integracao=status_integracao_item,
                        estoque_baixado=estoque_baixado_item,
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
            logger.exception(f"[Webhook Meli] Erro ao processar pedido '{resource}': {exc}")
            erro_str = f"{str(exc)}\n\nTraceback completo:\n{traceback.format_exc()}"
            event_log.status = WebhookStatusEnum.ERRO
            event_log.error_log = erro_str
            event_log.processed_at = timezone.now()
            event_log.save(update_fields=['status', 'error_log', 'processed_at'])

            return 200, {
                "status": "error",
                "message": f"Falha no processamento interno do pedido '{resource}'. Evento registrado como ERRO."
            }
