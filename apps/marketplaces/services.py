# Os códigos foram gerados com auxilio de I.A.
import logging
import traceback
from typing import Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone

from apps.marketplaces.models import ContaMarketplace, WebhookEventLog, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum, WebhookStatusEnum
from apps.anuncios.models import Anuncio
from apps.catalogo.models import Produto

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

            # Baixa atômica de estoque por produto
            with transaction.atomic():
                for item_raw in order_items:
                    item_info = item_raw.get('item', item_raw)
                    item_id_externo = str(item_info.get('id', item_raw.get('item_id', ''))).strip()
                    qtd_vendida = int(item_raw.get('quantity', 1))

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

                    if anuncio:
                        composicoes = anuncio.itens_composicao.all()
                        if composicoes.exists():
                            for comp in composicoes:
                                prod_locked = Produto.objects.select_for_update().get(pk=comp.produto_id)
                                qtd_baixa = qtd_vendida * comp.quantidade
                                saldo_ant = prod_locked.estoque
                                novo_saldo = max(0, saldo_ant - qtd_baixa)
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
                                    qtd_baixa = qtd_vendida
                                    saldo_ant = prod_locked.estoque
                                    novo_saldo = max(0, saldo_ant - qtd_baixa)
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
                    else:
                        # Fallback: tenta localizar produto diretamente por SKU do seller
                        sku = item_info.get('seller_sku', item_info.get('seller_custom_field'))
                        loja = conta.loja if conta else None
                        if sku and loja:
                            prod_locked = Produto.objects.select_for_update().filter(
                                loja=loja, sku=sku
                            ).first()
                            if prod_locked:
                                qtd_baixa = qtd_vendida
                                saldo_ant = prod_locked.estoque
                                novo_saldo = max(0, saldo_ant - qtd_baixa)
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
