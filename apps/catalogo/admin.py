# Os códigos foram gerados com auxilio de I.A.
from django.contrib import admin
from .models import Categoria, Produto, AnuncioMarketplace, HistoricoPreco


class AnuncioMarketplaceInline(admin.TabularInline):
    """
    O QUE FAZ: Inline de Anúncios Multicanal no Produto.
    POR QUE FAZ: Permite gerenciar múltiplos canais e IDs externos diretamente no produto.
    PERMISSÕES RBAC: DEV e Superuser.
    MULTI-TENANCY: Escopo da loja do produto.
    """
    model = AnuncioMarketplace
    extra = 0


class HistoricoPrecoInline(admin.TabularInline):
    """
    O QUE FAZ: Inline de Histórico de Preços no Produto.
    POR QUE FAZ: Rastreabilidade de preços passados (RN-04).
    PERMISSÕES RBAC: DEV e Superuser (somente leitura).
    MULTI-TENANCY: Escopo da loja.
    """
    model = HistoricoPreco
    extra = 0
    readonly_fields = ('preco_anterior', 'preco_novo', 'usuario', 'motivo', 'criado_em')
    can_delete = False


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'loja', 'slug', 'ativo', 'criado_em')
    list_filter = ('ativo', 'loja')
    search_fields = ('nome', 'slug', 'loja__nome')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nome', 'loja', 'categoria', 'preco', 'estoque', 'status', 'status_sincronizacao')
    list_filter = ('status', 'status_sincronizacao', 'modalidade_full', 'loja', 'categoria')
    search_fields = ('sku', 'nome', 'loja__nome')
    inlines = [AnuncioMarketplaceInline, HistoricoPrecoInline]


@admin.register(AnuncioMarketplace)
class AnuncioMarketplaceAdmin(admin.ModelAdmin):
    list_display = ('produto', 'conta_marketplace', 'item_id_externo', 'preco_sincronizado', 'status_anuncio')
    list_filter = ('conta_marketplace__canal', 'status_anuncio')
    search_fields = ('item_id_externo', 'produto__sku', 'produto__nome')


@admin.register(HistoricoPreco)
class HistoricoPrecoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'loja', 'preco_anterior', 'preco_novo', 'usuario', 'criado_em')
    list_filter = ('loja', 'criado_em')
    search_fields = ('produto__sku', 'produto__nome', 'usuario__username')
    readonly_fields = ('produto', 'loja', 'preco_anterior', 'preco_novo', 'usuario', 'motivo', 'criado_em')
