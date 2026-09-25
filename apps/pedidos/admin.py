# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo administrativo padrão do Django para customização e registro de interfaces no Django Admin
from django.contrib import admin

# Importa as entidades de modelo PedidoVenda e ItemPedidoVenda deste mesmo pacote
from .models import PedidoVenda, ItemPedidoVenda


# Declaração do inline tabular para visualização dos itens vinculados dentro da tela do pedido
class ItemPedidoVendaInline(admin.TabularInline):
    # Início do bloco de docstring que contextualiza a responsabilidade da classe inline
    """
    O QUE FAZ: Inline dos itens de um pedido de venda no Django Admin.
    """
    # Fim do bloco de docstring explicativo

    # Define o modelo dependente que será exibido em linhas tabulares
    model = ItemPedidoVenda

    # Desativa a exibição de linhas vazias adicionais para inserção manual no admin
    extra = 0

    # Torna todos os campos de auditoria e valores dos itens somente leitura para preservar a integridade histórica da venda
    readonly_fields = ('produto', 'anuncio_marketplace', 'item_id_externo', 'quantidade', 'preco_unitario', 'estoque_baixado', 'estoque_anterior', 'estoque_posterior', 'ruptura_estoque')

    # Desabilita a exclusão de itens de pedido diretamente pelo Django Admin
    can_delete = False


# Registra o modelo PedidoVenda no painel administrativo aplicando as customizações de PedidoVendaAdmin
@admin.register(PedidoVenda)
class PedidoVendaAdmin(admin.ModelAdmin):
    # Colunas visíveis na listagem principal de pedidos de venda
    list_display = ('pedido_id_externo', 'canal_origem', 'loja', 'comprador_nome', 'valor_total', 'status', 'teve_ruptura_estoque', 'criado_em')

    # Filtros laterais para segmentação por marketplace, status do pedido, ruptura de estoque, loja e data de criação
    list_filter = ('canal_origem', 'status', 'teve_ruptura_estoque', 'loja', 'criado_em')

    # Campos indexados para a barra de pesquisa textual (código externo, nome/documento do cliente e nome da loja)
    search_fields = ('pedido_id_externo', 'comprador_nome', 'comprador_documento', 'loja__nome')

    # Campos imutáveis na edição para garantir rastreabilidade e evitar manipulações indevidas de payloads e vínculos
    readonly_fields = ('loja', 'conta_marketplace', 'canal_origem', 'pedido_id_externo', 'payload_original', 'criado_em', 'atualizado_em')

    # Associa o inline dos itens vendidos para exibição na mesma página do pedido
    inlines = [ItemPedidoVendaInline]


# Registra o modelo ItemPedidoVenda isoladamente para consultas analíticas detalhadas
@admin.register(ItemPedidoVenda)
class ItemPedidoVendaAdmin(admin.ModelAdmin):
    # Colunas visíveis na listagem de itens de pedido
    list_display = ('pedido', 'produto', 'item_id_externo', 'quantidade', 'preco_unitario', 'ruptura_estoque')

    # Filtros laterais para diagnóstico rápido de rupturas de estoque e status da baixa
    list_filter = ('ruptura_estoque', 'estoque_baixado')

    # Campos pesquisáveis por ID do item no canal parceiro, título do anúncio ou SKU do catálogo
    search_fields = ('item_id_externo', 'titulo_anuncio', 'produto__sku')
