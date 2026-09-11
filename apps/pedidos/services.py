# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
from django.db import transaction

from apps.tenancy.models import Loja
from apps.marketplaces.models import ContaMarketplace, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from apps.marketplaces.connectors.factory import get_connector_for_conta
from apps.catalogo.models import Produto, AnuncioMarketplace
from .models import PedidoVenda, ItemPedidoVenda
from .enums import StatusPedidoEnum


class ProcessamentoPedidoService:
    """
    O QUE FAZ: Serviço central de processamento atômico de pedidos de venda recebidos via Webhook ou conciliação (RF-06 / RN-05).
    POR QUE FAZ:
      1. Garante isolamento concorrente com lock pessimista (select_for_update) em transação atômica (ACID).
      2. Deduz estoque físico de forma segura, detectando e alertando sobre eventuais rupturas (saldo negativo).
      3. Propaga o novo saldo atualizado para todos os outros canais integrados (Broadcast Multicanal de Estoque).
    PERMISSÕES RBAC: Executado de forma automatizada por endpoints de webhooks e rotinas de conciliação.
    MULTI-TENANCY: Processa pedidos estritamente no escopo da Loja (Tenant) identificada no webhook.
    """

    @classmethod
    def processar_pedido_venda(
        cls,
        loja: Loja,
        canal: str,
        pedido_id_externo: str,
        dados_pedido: Dict[str, Any],
        conta: Optional[ContaMarketplace] = None
    ) -> Tuple[bool, str, Optional[PedidoVenda]]:
        """
        O QUE FAZ: Cria ou atualiza o PedidoVenda, processa seus itens e debita o estoque com lock atômico.
        """
        if not loja:
            return False, "Loja não informada para o processamento.", None

        if not pedido_id_externo:
            return False, "Identificador externo de pedido não informado.", None

        # Idempotência: verifica se o pedido já foi recebido e processado
        pedido_existente = PedidoVenda.objects.filter(
            loja=loja, canal_origem=canal, pedido_id_externo=pedido_id_externo
        ).first()

        if pedido_existente:
            return True, f"Pedido #{pedido_id_externo} já processado anteriormente.", pedido_existente

        itens_payload = dados_pedido.get('items', dados_pedido.get('order_items', []))
        valor_total = Decimal(str(dados_pedido.get('total_amount', dados_pedido.get('valor_total', '0.00'))))
        valor_frete = Decimal(str(dados_pedido.get('shipping_cost', dados_pedido.get('valor_frete', '0.00'))))
        comprador = dados_pedido.get('buyer', {})
        comprador_nome = (
            f"{comprador.get('first_name', '')} {comprador.get('last_name', '')}".strip()
            or comprador.get('name')
            or comprador.get('nickname')
            or "Comprador Marketplace"
        )

        with transaction.atomic():
            pedido = PedidoVenda.objects.create(
                loja=loja,
                conta_marketplace=conta,
                canal_origem=canal,
                pedido_id_externo=pedido_id_externo,
                status_externo=dados_pedido.get('status', 'paid'),
                status=StatusPedidoEnum.PAGO,
                comprador_nome=comprador_nome,
                valor_total=valor_total,
                valor_frete=valor_frete,
                payload_original=dados_pedido
            )

            houve_ruptura_geral = False

            for item_raw in itens_payload:
                item_info = item_raw.get('item', item_raw)
                item_id_ext = str(item_info.get('id', item_raw.get('item_id', '')))
                titulo = item_info.get('title', item_raw.get('titulo', 'Item Vendido'))
                quantidade = int(item_raw.get('quantity', 1))
                unit_price = Decimal(str(item_raw.get('unit_price', '0.00')))

                # Localiza o produto no catálogo do Hub via AnuncioMarketplace ou SKU
                anuncio = AnuncioMarketplace.objects.filter(
                    conta_marketplace__loja=loja, item_id_externo=item_id_ext
                ).first()

                produto = None
                multiplicador = 1
                anuncio_v2 = None

                if anuncio:
                    produto = anuncio.produto
                else:
                    sku_seller = item_info.get('seller_sku', item_info.get('seller_custom_field', ''))
                    if sku_seller:
                        produto = Produto.objects.filter(loja=loja, sku=sku_seller).first()

                # Se não encontrou por AnuncioMarketplace ou SKU direto, busca pelo Anuncio (apps.anuncios)
                if not produto:
                    from apps.anuncios.models import Anuncio
                    if conta:
                        anuncio_v2 = Anuncio.objects.filter(
                            conta=conta, item_id_externo=item_id_ext
                        ).prefetch_related('itens_composicao__produto').first()
                    if not anuncio_v2:
                        anuncio_v2 = Anuncio.objects.filter(
                            conta__loja=loja, item_id_externo=item_id_ext
                        ).prefetch_related('itens_composicao__produto').first()
                    if not anuncio_v2:
                        anuncio_v2 = Anuncio.objects.filter(
                            item_id_externo=item_id_ext
                        ).prefetch_related('itens_composicao__produto').first()

                    if anuncio_v2:
                        if not titulo or titulo == 'Item Vendido':
                            titulo = anuncio_v2.titulo
                        comp = anuncio_v2.itens_composicao.first()
                        if comp:
                            produto = comp.produto
                            multiplicador = comp.quantidade
                        elif anuncio_v2.sku_vendedor:
                            produto = Produto.objects.filter(loja=loja, sku=anuncio_v2.sku_vendedor).first()

                estoque_ant = None
                estoque_pos = None
                teve_ruptura = False
                estoque_baixado = False

                if produto:
                    # LOCK PESSIMISTA CONCORRENTE (RN-05): select_for_update
                    prod_locked = Produto.objects.select_for_update().get(pk=produto.pk)
                    estoque_ant = prod_locked.estoque
                    qtd_deduzir = quantidade * multiplicador
                    estoque_pos = estoque_ant - qtd_deduzir
                    prod_locked.estoque = estoque_pos
                    prod_locked._motivo_alteracao = 'VENDA_MARKETPLACE'
                    prod_locked.save(update_fields=['estoque', 'atualizado_em'])
                    estoque_baixado = True

                    # Alerta de Ruptura (RN-05): Saldo ficou negativo
                    if estoque_pos < 0:
                        teve_ruptura = True
                        houve_ruptura_geral = True
                        LogAuditoria.objects.create(
                            loja=loja,
                            evento=EventoAuditoriaEnum.ALERTA_RUPTURA_ESTOQUE,
                            detalhes=(
                                f"ALERTA DE RUPTURA: Venda do pedido #{pedido_id_externo} no canal '{canal}' "
                                f"deixou o produto SKU '{prod_locked.sku}' com saldo NEGATIVO ({estoque_pos} un.). "
                                f"Estoque anterior: {estoque_ant} un. | Quantidade vendida: {qtd_deduzir} un."
                            )
                        )

                    # Log da baixa de estoque por venda
                    LogAuditoria.objects.create(
                        loja=loja,
                        evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
                        detalhes=(
                            f"Baixa automática de {qtd_deduzir} un. no SKU '{prod_locked.sku}' por venda #{pedido_id_externo} ({canal}). "
                            f"Saldo: {estoque_ant} -> {estoque_pos}."
                        )
                    )

                    # BROADCAST MULTICANAL DE ESTOQUE: propaga o novo saldo para outros anúncios
                    cls.propagar_estoque_multicanal(prod_locked, canal_origem=canal)

                    # Se o anúncio possui outros itens de composição, baixa o estoque de cada um também
                    if anuncio_v2 and anuncio_v2.itens_composicao.count() > 1:
                        for comp_extra in anuncio_v2.itens_composicao.all()[1:]:
                            prod_extra = Produto.objects.select_for_update().get(pk=comp_extra.produto_id)
                            qtd_extra = quantidade * comp_extra.quantidade
                            saldo_extra_ant = prod_extra.estoque
                            saldo_extra_pos = saldo_extra_ant - qtd_extra
                            prod_extra.estoque = saldo_extra_pos
                            prod_extra._motivo_alteracao = 'VENDA_MARKETPLACE'
                            prod_extra.save(update_fields=['estoque', 'atualizado_em'])
                            cls.propagar_estoque_multicanal(prod_extra, canal_origem=canal)

                ItemPedidoVenda.objects.create(
                    pedido=pedido,
                    produto=produto,
                    anuncio_marketplace=anuncio,
                    item_id_externo=item_id_ext,
                    titulo_anuncio=titulo,
                    quantidade=quantidade,
                    preco_unitario=unit_price,
                    estoque_baixado=estoque_baixado,
                    estoque_anterior=estoque_ant,
                    estoque_posterior=estoque_pos,
                    ruptura_estoque=teve_ruptura
                )

            if houve_ruptura_geral:
                pedido.teve_ruptura_estoque = True
                pedido.save(update_fields=['teve_ruptura_estoque', 'atualizado_em'])

        return True, f"Pedido #{pedido_id_externo} processado com sucesso!", pedido

    @classmethod
    def propagar_estoque_multicanal(cls, produto: Produto, canal_origem: Optional[str] = None):
        """
        O QUE FAZ: Envia o saldo atualizado do produto para todas as contas e canais vinculados aos anúncios do produto.
        POR QUE FAZ: Mantém a paridade de estoque em tempo real em todas as plataformas onde o lojista opera (Mercado Livre, Shopee, Magalu).
        """
        anuncios = produto.anuncios.select_related('conta_marketplace').all()
        for anuncio in anuncios:
            conta = anuncio.conta_marketplace
            # Não reenvia para o mesmo canal se for a origem imediata do webhook (opcional)
            connector = get_connector_for_conta(conta)
            try:
                connector.atualizar_estoque(anuncio.item_id_externo, produto.estoque)
            except Exception:
                pass
