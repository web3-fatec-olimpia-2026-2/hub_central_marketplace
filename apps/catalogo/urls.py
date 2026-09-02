# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    # Catálogo de Produtos (RF-03)
    path('produtos/', views.ProdutoListView.as_view(), name='produto_list'),
    path('produtos/novo/', views.ProdutoCreateView.as_view(), name='produto_create'),
    path('produtos/<int:pk>/', views.ProdutoDetailView.as_view(), name='produto_detail'),
    path('produtos/<int:pk>/editar/', views.ProdutoUpdateView.as_view(), name='produto_update'),
    path('produtos/<int:pk>/excluir/', views.ProdutoDeleteView.as_view(), name='produto_delete'),

    # Movimentações de Estoque (RN-06 / RN-09)
    path('produtos/<int:pk>/baixa-avaria/', views.ProdutoBaixaEstoqueView.as_view(), name='produto_baixa_avaria'),
    path('produtos/<int:pk>/baixa-estoque/', views.ProdutoBaixaEstoqueView.as_view(), name='produto_baixa_estoque'),
    path('produtos/<int:pk>/ajuste-estoque/', views.ProdutoAjusteEstoqueView.as_view(), name='produto_ajuste_estoque'),

    # Sincronização de Preços com Canais
    path('produtos/<int:pk>/sincronizar-preco/', views.ProdutoSincronizarPrecoView.as_view(), name='produto_sincronizar_preco'),
    path('produtos/<int:pk>/sincronizar-meli/', views.ProdutoSincronizarPrecoView.as_view(), name='produto_sincronizar_preco_meli'),
    path('produtos/sincronizar-lote/', views.ProdutoSincronizarPrecoLoteView.as_view(), name='produto_sincronizar_lote'),
    path('produtos/sincronizar-lote-meli/', views.ProdutoSincronizarPrecoLoteView.as_view(), name='produto_sincronizar_lote_meli'),

    # Vínculo de Anúncios Multicanal
    path('produtos/<int:pk>/anuncios/novo/', views.AnuncioMarketplaceCreateView.as_view(), name='anuncio_marketplace_create'),
    path('anuncios/<int:pk>/excluir/', views.AnuncioMarketplaceDeleteView.as_view(), name='anuncio_marketplace_delete'),

    # Categorias de Produtos
    path('categorias/', views.CategoriaListView.as_view(), name='categoria_list'),
    path('categorias/nova/', views.CategoriaCreateView.as_view(), name='categoria_create'),
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_update'),
    path('categorias/<int:pk>/excluir/', views.CategoriaDeleteView.as_view(), name='categoria_delete'),
]
