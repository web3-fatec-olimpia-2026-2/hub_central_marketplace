# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django.db import models

from apps.tenancy.models import Loja
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import CanalMarketplaceEnum
from apps.catalogo.models import Produto, AnuncioMarketplace
from .enums import StatusPedidoEnum


class PedidoVenda(models.Model):
    """
    O QUE FAZ: Representa o registro consolidado de uma Venda recebida via Webhook ou conciliação de marketplaces (RF-06).
    POR QUE FAZ: Desacopla as vendas por canal mantendo rastreabilidade de comprador, valor, origem e integridade de estoque (RN-05).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (leitura na própria loja).
    MULTI-TENANCY: FK obrigatória para Loja com unicidade composta ('loja', 'canal_origem', 'pedido_id_externo').
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='pedidos_venda', verbose_name="Loja (Tenant)"
    )
    conta_marketplace = models.ForeignKey(
        ContaMarketplace, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pedidos', verbose_name="Conta do Canal"
    )
    canal_origem = models.CharField(
        max_length=30, choices=CanalMarketplaceEnum.choices, default=CanalMarketplaceEnum.MERCADOLIVRE,
        verbose_name="Canal de Origem"
    )
    pedido_id_externo = models.CharField(
        max_length=100, db_index=True, verbose_name="ID do Pedido no Canal"
    )
    status_externo = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Status no Marketplace"
    )
    status = models.CharField(
        max_length=20, choices=StatusPedidoEnum.choices, default=StatusPedidoEnum.PAGO,
        verbose_name="Status no Hub"
    )
    comprador_nome = models.CharField(
        max_length=150, blank=True, null=True, verbose_name="Nome do Comprador"
    )
    comprador_documento = models.CharField(
        max_length=30, blank=True, null=True, verbose_name="Documento do Comprador"
    )
    valor_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor Total do Pedido (R$)"
    )
    valor_frete = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor do Frete (R$)"
    )
    data_criacao_externa = models.DateTimeField(
        null=True, blank=True, verbose_name="Data no Marketplace"
    )
    processado_com_sucesso = models.BooleanField(
        default=True, verbose_name="Processado com Sucesso"
    )
    teve_ruptura_estoque = models.BooleanField(
        default=False, verbose_name="Houve Ruptura de Estoque (RN-05)"
    )
    payload_original = models.JSONField(
        default=dict, blank=True, verbose_name="Payload Original do Webhook"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Recebido no Hub em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Pedido de Venda"
        verbose_name_plural = "Pedidos de Venda"
        unique_together = ('loja', 'canal_origem', 'pedido_id_externo')
        ordering = ['-criado_em']

    def __str__(self):
        return f"[{self.get_canal_origem_display()}] Pedido #{self.pedido_id_externo} — R$ {self.valor_total} ({self.loja.nome})"


class ItemPedidoVenda(models.Model):
    """
    O QUE FAZ: Itens e produtos associados a um Pedido de Venda.
    POR QUE FAZ: Registra a dedução atômica de estoque e rastreia saldos anteriores e posteriores (RN-05).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Herda o tenant do pedido pai.
    """
    pedido = models.ForeignKey(
        PedidoVenda, on_delete=models.CASCADE, related_name='itens', verbose_name="Pedido"
    )
    produto = models.ForeignKey(
        Produto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_vendidos', verbose_name="Produto no Hub"
    )
    anuncio_marketplace = models.ForeignKey(
        AnuncioMarketplace, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_vendidos', verbose_name="Anúncio Vinculado"
    )
    item_id_externo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="ID Externo do Item"
    )
    titulo_anuncio = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Título no Marketplace"
    )
    quantidade = models.IntegerField(
        default=1, verbose_name="Quantidade Vendida"
    )
    preco_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Preço Unitário (R$)"
    )
    estoque_baixado = models.BooleanField(
        default=False, verbose_name="Estoque Baixado Automaticamente"
    )
    estoque_anterior = models.IntegerField(
        null=True, blank=True, verbose_name="Saldo de Estoque Anterior"
    )
    estoque_posterior = models.IntegerField(
        null=True, blank=True, verbose_name="Saldo de Estoque Posterior"
    )
    ruptura_estoque = models.BooleanField(
        default=False, verbose_name="Alerta de Ruptura (Saldo Negativo)"
    )

    class Meta:
        verbose_name = "Item do Pedido de Venda"
        verbose_name_plural = "Itens dos Pedidos de Venda"

    def __str__(self):
        return f"{self.quantidade}x {self.titulo_anuncio or self.item_id_externo} (R$ {self.preco_unitario})"
