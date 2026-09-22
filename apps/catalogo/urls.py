# Os códigos foram gerados com auxilio de I.A.

# Importa a função utilitária path do framework Django para declaração de rotas e padrões de URL
from django.urls import path

# Importa o módulo de views do aplicativo apps.catalogo contendo os controladores baseados em classe
from . import views

# Lista de padrões de URL do módulo de catálogo (geralmente prefixados na raiz do projeto)
urlpatterns = [
    # Catálogo de Produtos (RF-03)
    # Rota que renderiza a listagem paginada e filtrada dos produtos físicos da loja (tenant)
    path('produtos/', views.ProdutoListView.as_view(), name='produto_list'),

    # Rota para renderizar e processar o formulário de cadastro de um novo produto físico
    path('produtos/novo/', views.ProdutoCreateView.as_view(), name='produto_create'),

    # Rota de detalhamento do produto: exibe custos, saldo físico, anúncios vinculados e histórico de auditoria
    path('produtos/<int:pk>/', views.ProdutoDetailView.as_view(), name='produto_detail'),

    # Rota de edição de dados cadastrais, preço e estoque do produto (respeitando as regras de perfil RN-09)
    path('produtos/<int:pk>/editar/', views.ProdutoUpdateView.as_view(), name='produto_update'),

    # Rota para exclusão de produto físico (bloqueada para o papel USUARIO conforme RN-09)
    path('produtos/<int:pk>/excluir/', views.ProdutoDeleteView.as_view(), name='produto_delete'),

    # Movimentações de Estoque (RN-06 / RN-09)
    # Rota de registro de baixa pontual por avaria ou defeito físico (liberada para todos os operadores com justificativa)
    path('produtos/<int:pk>/baixa-avaria/', views.ProdutoBaixaEstoqueView.as_view(), name='produto_baixa_avaria'),

    # Alias da rota de baixa pontual de estoque por perda/avaria para consistência semântica de chamadas
    path('produtos/<int:pk>/baixa-estoque/', views.ProdutoBaixaEstoqueView.as_view(), name='produto_baixa_estoque'),

    # Rota para contagem de inventário ou ajuste geral do saldo físico de estoque (restrita a gestores/ADMIN/DEV)
    path('produtos/<int:pk>/ajuste-estoque/', views.ProdutoAjusteEstoqueView.as_view(), name='produto_ajuste_estoque'),

    # Sincronização de Preços com Canais
    # Rota para confirmar o envio manual do novo preço aos anúncios vinculados ou descartar alterações no modal
    path('produtos/<int:pk>/sincronizar-preco/', views.ProdutoSincronizarPrecoView.as_view(), name='produto_sincronizar_preco'),

    # Alias legado da rota de sincronização unitária de preço mantido para compatibilidade com templates antigos
    path('produtos/<int:pk>/sincronizar-meli/', views.ProdutoSincronizarPrecoView.as_view(), name='produto_sincronizar_preco_meli'),

    # Rota para disparo de sincronização em massa dos produtos selecionados via checkboxes na listagem
    path('produtos/sincronizar-lote/', views.ProdutoSincronizarPrecoLoteView.as_view(), name='produto_sincronizar_lote'),

    # Alias legado para a sincronização em lote mantido para rotinas prévias
    path('produtos/sincronizar-lote-meli/', views.ProdutoSincronizarPrecoLoteView.as_view(), name='produto_sincronizar_lote_meli'),

    # Vínculo e Publicação de Anúncios Multicanal (RF-04)
    # Rota para criação de uma nova publicação remota no marketplace a partir do produto do catálogo
    path('produtos/<int:pk>/publicar-anuncio/', views.PublicarAnuncioView.as_view(), name='anuncio_marketplace_publicar'),

    # Rota para vinculação manual direta de um anúncio remoto existente (MLB...) a um produto local
    path('produtos/<int:pk>/anuncios/novo/', views.AnuncioMarketplaceCreateView.as_view(), name='anuncio_marketplace_create'),

    # Rota para exclusão/desvinculação de um anúncio direto vinculado ao produto
    path('anuncios/<int:pk>/excluir/', views.AnuncioMarketplaceDeleteView.as_view(), name='anuncio_marketplace_delete'),

    # Categorias de Produtos
    # Rota para listar todas as categorias taxonômicas cadastradas sob o tenant do lojista
    path('categorias/', views.CategoriaListView.as_view(), name='categoria_list'),

    # Rota para carregar e processar o formulário de inclusão de uma nova categoria
    path('categorias/nova/', views.CategoriaCreateView.as_view(), name='categoria_create'),

    # Rota para edição de nome, slug e status de ativação de uma categoria existente
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_update'),

    # Rota para exclusão de categoria (bloqueada caso existam produtos vinculados a ela via PROTECT)
    path('categorias/<int:pk>/excluir/', views.CategoriaDeleteView.as_view(), name='categoria_delete'),
]
