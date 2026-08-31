# Os códigos foram gerados com auxilio de I.A.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Loja, PerfilUsuario, LogAuditoria, Categoria, Produto, HistoricoPreco,
    LogSincronizacao, PedidoVenda, ItemPedidoVenda,
    ConfiguracaoTaxasLoja, ParametroCanalMarketplace
)


class ConfiguracaoTaxasLojaInline(admin.StackedInline):
    model = ConfiguracaoTaxasLoja
    can_delete = False
    extra = 0
    verbose_name_plural = 'Parâmetros Tributários e Margem de Segurança'


class ParametroCanalMarketplaceInline(admin.TabularInline):
    model = ParametroCanalMarketplace
    extra = 0
    verbose_name_plural = 'Tarifas e Comissões por Canal de Marketplace'


@admin.register(ConfiguracaoTaxasLoja)
class ConfiguracaoTaxasLojaAdmin(admin.ModelAdmin):
    list_display = ('loja', 'aliquota_imposto', 'custo_embalagem_padrao', 'margem_minima_seguranca', 'custos_fixos_mensais', 'atualizado_em')
    search_fields = ('loja__nome', 'loja__cnpj')


@admin.register(ParametroCanalMarketplace)
class ParametroCanalMarketplaceAdmin(admin.ModelAdmin):
    list_display = ('marketplace', 'loja', 'comissao_padrao', 'frete_gratis_piso', 'taxa_frete_acima_limite', 'taxa_fixa_abaixo_limite', 'ativo')
    list_filter = ('marketplace', 'ativo', 'loja')
    search_fields = ('loja__nome',)


class PerfilUsuarioInline(admin.StackedInline):


    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil de Acesso (RBAC & Tenant)'
    fk_name = 'usuario'
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_papel', 'get_loja', 'is_staff')
    list_select_related = ('perfil', 'perfil__loja')

    def get_papel(self, instance):
        if hasattr(instance, 'perfil'):
            return instance.perfil.get_papel_display()
        return "Sem Perfil"
    get_papel.short_description = 'Papel RBAC'

    def get_loja(self, instance):
        if hasattr(instance, 'perfil') and instance.perfil.loja:
            return instance.perfil.loja.nome
        return "Global / Nenhuma"
    get_loja.short_description = 'Loja (Tenant)'


@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj', 'cidade', 'estado', 'telefone', 'ativo', 'criado_em')
    list_filter = ('ativo', 'estado', 'criado_em')
    search_fields = ('nome', 'cnpj', 'slug', 'cidade', 'email')
    prepopulated_fields = {'slug': ('nome',)}
    fieldsets = (
        ('Identificação e Status', {
            'fields': ('nome', 'slug', 'cnpj', 'inscricao_estadual', 'ativo')
        }),
        ('Contato', {
            'fields': ('telefone', 'email')
        }),
        ('Endereço', {
            'fields': ('cep', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'pais')
        }),
        ('Integração Mercado Livre (Provisionamento DEV)', {
            'classes': ('collapse',),
            'fields': ('meli_client_id', 'meli_client_secret', 'meli_access_token', 'meli_refresh_token')
        }),
    )


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'papel', 'loja', 'criado_em')
    list_filter = ('papel', 'loja')
    search_fields = ('usuario__username', 'usuario__email', 'loja__nome')


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('evento', 'autor', 'usuario_afetado', 'loja', 'criado_em')
    list_filter = ('evento', 'loja', 'criado_em')
    search_fields = ('detalhes', 'autor__username', 'usuario_afetado__username', 'loja__nome')
    readonly_fields = ('loja', 'autor', 'usuario_afetado', 'evento', 'detalhes', 'ip_origem', 'criado_em')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'loja', 'ativo', 'criado_em')
    list_filter = ('loja', 'ativo', 'criado_em')
    search_fields = ('nome', 'slug', 'loja__nome')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nome', 'categoria', 'loja', 'preco', 'estoque', 'status', 'status_sincronizacao')
    list_filter = ('status', 'status_sincronizacao', 'loja', 'categoria')
    search_fields = ('sku', 'nome', 'meli_item_id', 'loja__nome')


@admin.register(HistoricoPreco)
class HistoricoPrecoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'loja', 'preco_anterior', 'preco_novo', 'usuario', 'criado_em')
    list_filter = ('loja', 'criado_em')
    search_fields = ('produto__sku', 'produto__nome', 'usuario__username')
    readonly_fields = ('produto', 'loja', 'preco_anterior', 'preco_novo', 'usuario', 'motivo', 'criado_em')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogSincronizacao)
class LogSincronizacaoAdmin(admin.ModelAdmin):
    list_display = ('marketplace', 'evento', 'loja', 'produto', 'status_http', 'sucesso', 'tempo_resposta_ms', 'criado_em')
    list_filter = ('marketplace', 'evento', 'sucesso', 'status_http', 'loja', 'criado_em')
    search_fields = ('item_id_externo', 'produto__sku', 'produto__nome', 'mensagem_erro', 'loja__nome')
    readonly_fields = (
        'loja', 'produto', 'marketplace', 'evento', 'item_id_externo',
        'payload_enviado', 'resposta_recebida', 'status_http', 'sucesso',
        'mensagem_erro', 'tempo_resposta_ms', 'criado_em'
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ItemPedidoVendaInline(admin.TabularInline):
    model = ItemPedidoVenda
    extra = 0
    readonly_fields = (
        'produto', 'item_id_externo', 'sku_informado', 'titulo_anuncio',
        'quantidade', 'preco_unitario', 'estoque_baixado',
        'estoque_anterior', 'estoque_posterior', 'ruptura_estoque'
    )
    can_delete = False


@admin.register(PedidoVenda)
class PedidoVendaAdmin(admin.ModelAdmin):
    list_display = (
        'pedido_id_externo', 'marketplace', 'loja', 'comprador_nome',
        'valor_total', 'status', 'teve_ruptura_estoque', 'processado_com_sucesso', 'criado_em'
    )
    list_filter = ('marketplace', 'status', 'teve_ruptura_estoque', 'processado_com_sucesso', 'loja', 'criado_em')
    search_fields = ('pedido_id_externo', 'comprador_nome', 'comprador_documento', 'loja__nome')
    readonly_fields = (
        'loja', 'marketplace', 'pedido_id_externo', 'status_externo',
        'status', 'comprador_nome', 'comprador_documento', 'valor_total',
        'valor_frete', 'data_criacao_externa', 'processado_com_sucesso',
        'teve_ruptura_estoque', 'observacoes', 'payload_original',
        'criado_em', 'atualizado_em'
    )
    inlines = [ItemPedidoVendaInline]

    def has_add_permission(self, request):
        return False


# Re-registra o modelo User com o inline de Perfil
admin.site.unregister(User)
admin.site.register(User, UserAdmin)





