# Os códigos foram gerados com auxilio de I.A.
# Importa o módulo administrativo padrão do Django para registro e customização de interfaces no painel admin
from django.contrib import admin

# Importa as entidades de modelo gerenciadas pelo app catalogo: Categoria, Produto, AnuncioMarketplace e HistoricoPreco
from .models import Categoria, Produto, AnuncioMarketplace, HistoricoPreco


# Classe inline tabular para renderizar os anúncios de marketplaces diretamente no formulário de edição do Produto
class AnuncioMarketplaceInline(admin.TabularInline):
    # Início do bloco de docstring que documenta o propósito, escopo de RBAC e multi-tenancy do inline
    """
    O QUE FAZ: Inline de Anúncios Multicanal no Produto.
    POR QUE FAZ: Permite gerenciar múltiplos canais e IDs externos diretamente no produto.
    PERMISSÕES RBAC: DEV e Superuser.
    MULTI-TENANCY: Escopo da loja do produto.
    """
    # Fim do bloco de documentação do inline de anúncios

    # Associa a tabela inline ao modelo AnuncioMarketplace
    model = AnuncioMarketplace

    # Define que não serão exibidas linhas vazias extras além das instâncias já cadastradas no banco
    extra = 0


# Classe inline tabular para visualização da trilha histórica de preços na página de detalhes do Produto
class HistoricoPrecoInline(admin.TabularInline):
    # Início do bloco de docstring documentando a finalidade de auditoria e imutabilidade dos registros de preço
    """
    O QUE FAZ: Inline de Histórico de Preços no Produto.
    POR QUE FAZ: Rastreabilidade de preços passados (RN-04).
    PERMISSÕES RBAC: DEV e Superuser (somente leitura).
    MULTI-TENANCY: Escopo da loja.
    """
    # Fim do bloco de documentação do inline de histórico

    # Associa o inline ao modelo HistoricoPreco
    model = HistoricoPreco

    # Não exibe formulários vazios complementares
    extra = 0

    # Define os campos de auditoria estritamente como somente leitura para impedir fraudes ou alterações manuais
    readonly_fields = ('preco_anterior', 'preco_novo', 'usuario', 'motivo', 'criado_em')

    # Desabilita o botão de remoção de registros para garantir imutabilidade da trilha de auditoria
    can_delete = False


# Decorador que registra o modelo Categoria no Django Admin utilizando as configurações da classe CategoriaAdmin
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    # Define as colunas visíveis na tabela de listagem de categorias
    list_display = ('nome', 'loja', 'slug', 'ativo', 'criado_em')

    # Adiciona filtros laterais rápidos pelo status de ativação e pela Loja (tenant)
    list_filter = ('ativo', 'loja')

    # Configura barra de busca textual por nome da categoria, slug e nome da loja vinculada
    search_fields = ('nome', 'slug', 'loja__nome')

    # Preenche automaticamente o campo slug com base no texto digitado no campo nome durante o cadastro
    prepopulated_fields = {'slug': ('nome',)}


# Decorador que registra o modelo mestre Produto no Django Admin utilizando a classe ProdutoAdmin
@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    # Define as colunas de listagem do inventário (identificação, tenant, categoria, preço, saldo e status)
    list_display = ('sku', 'nome', 'loja', 'categoria', 'preco', 'estoque', 'status', 'status_sincronizacao')

    # Adiciona filtros laterais por status comercial, sincronização, envio Full, Loja e Categoria
    list_filter = ('status', 'status_sincronizacao', 'modalidade_full', 'loja', 'categoria')

    # Habilita pesquisa por código SKU, nome do produto e nome da loja proprietária
    search_fields = ('sku', 'nome', 'loja__nome')

    # Acopla os inlines de anúncios em marketplaces e histórico de alterações de preço no rodapé do produto
    inlines = [AnuncioMarketplaceInline, HistoricoPrecoInline]


# Decorador que registra o modelo AnuncioMarketplace isoladamente para consulta administrativa direta
@admin.register(AnuncioMarketplace)
class AnuncioMarketplaceAdmin(admin.ModelAdmin):
    # Colunas visíveis: produto pai, conta do canal, ID externo remoto, preço enviado e status no canal
    list_display = ('produto', 'conta_marketplace', 'item_id_externo', 'preco_sincronizado', 'status_anuncio')

    # Filtros laterais para segmentar por canal de marketplace (Mercado Livre, etc.) e status da oferta
    list_filter = ('conta_marketplace__canal', 'status_anuncio')

    # Barra de busca por identificador externo (ex: MLB...), SKU do produto pai e título do produto
    search_fields = ('item_id_externo', 'produto__sku', 'produto__nome')


# Decorador que registra a tabela de auditoria HistoricoPreco para consultas de conformidade e fiscalização
@admin.register(HistoricoPreco)
class HistoricoPrecoAdmin(admin.ModelAdmin):
    # Colunas exibidas para rastreamento de oscilações de preço, operador responsável e data
    list_display = ('produto', 'loja', 'preco_anterior', 'preco_novo', 'usuario', 'criado_em')

    # Filtros por loja do lojista e período de criação do registro
    list_filter = ('loja', 'criado_em')

    # Pesquisa por SKU/nome do produto envolvido e username do usuário responsável pelo ajuste
    search_fields = ('produto__sku', 'produto__nome', 'usuario__username')

    # Bloqueia qualquer tentativa de edição manual em todos os campos, preservando o histórico original
    readonly_fields = ('produto', 'loja', 'preco_anterior', 'preco_novo', 'usuario', 'motivo', 'criado_em')
