# Os códigos foram gerados com auxilio de I.A.
from django.contrib import admin
from .models import PedidoVenda, ItemPedidoVenda


class ItemPedidoVendaInline(admin.TabularInline):
    """
    O QUE FAZ: Inline dos itens de um pedido de venda no Django Admin.
    """
    model = ItemPedidoVenda
    extra = 0
    readonly_fields = ('produto', 'anuncio_marketplace', 'item_id_externo', 'quantidade', 'preco_unitario', 'estoque_baixado', 'estoque_anterior', 'estoque_posterior', 'ruptura_estoque')
    can_delete = False


@admin.register(PedidoVenda)
class PedidoVendaAdmin(admin.ModelAdmin):
    list_display = ('pedido_id_externo', 'canal_origem', 'loja', 'comprador_nome', 'valor_total', 'status', 'teve_ruptura_estoque', 'criado_em')
    list_filter = ('canal_origem', 'status', 'teve_ruptura_estoque', 'loja', 'criado_em')
    search_fields = ('pedido_id_externo', 'comprador_nome', 'comprador_documento', 'loja__nome')
    readonly_fields = ('loja', 'conta_marketplace', 'canal_origem', 'pedido_id_externo', 'payload_original', 'criado_em', 'atualizado_em')
    inlines = [ItemPedidoVendaInline]


@admin.register(ItemPedidoVenda)
class ItemPedidoVendaAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'produto', 'item_id_externo', 'quantidade', 'preco_unitario', 'ruptura_estoque')
    list_filter = ('ruptura_estoque', 'estoque_baixado')
    search_fields = ('item_id_externo', 'titulo_anuncio', 'produto__sku')
