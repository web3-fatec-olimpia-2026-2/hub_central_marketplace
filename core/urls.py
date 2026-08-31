from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.DashboardHomeView.as_view(), name='home'),

    # Gestão de Lojas (Tenants) — Exclusivo DEV (RF-01)
    path('lojas/', views.LojaListView.as_view(), name='loja_list'),
    path('lojas/nova/', views.LojaCreateView.as_view(), name='loja_create'),
    path('lojas/<slug:slug>/', views.LojaDetailView.as_view(), name='loja_detail'),
    path('lojas/<slug:slug>/editar/', views.LojaUpdateView.as_view(), name='loja_update'),

    # Gestão de Usuários com RBAC (RF-02)
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),
    path('usuarios/<int:pk>/status/', views.UsuarioToggleStatusView.as_view(), name='usuario_toggle_status'),
    path('usuarios/<int:pk>/redefinir-senha/', views.UsuarioPasswordResetAdminView.as_view(), name='usuario_password_reset'),

    # Gestão de Categorias (RF-03)
    path('categorias/', views.CategoriaListView.as_view(), name='categoria_list'),
    path('categorias/nova/', views.CategoriaCreateView.as_view(), name='categoria_create'),
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_update'),
    path('categorias/<int:pk>/excluir/', views.CategoriaDeleteView.as_view(), name='categoria_delete'),

    # Catálogo de Produtos e Gestão de Estoque (RF-03)
    path('produtos/', views.ProdutoListView.as_view(), name='produto_list'),
    path('produtos/novo/', views.ProdutoCreateView.as_view(), name='produto_create'),
    path('produtos/<int:pk>/', views.ProdutoDetailView.as_view(), name='produto_detail'),
    path('produtos/<int:pk>/editar/', views.ProdutoUpdateView.as_view(), name='produto_update'),
    path('produtos/<int:pk>/excluir/', views.ProdutoDeleteView.as_view(), name='produto_delete'),
    path('produtos/<int:pk>/baixa-estoque/', views.ProdutoBaixaEstoqueView.as_view(), name='produto_baixa_estoque'),
    path('produtos/<int:pk>/ajuste-estoque/', views.ProdutoAjusteEstoqueView.as_view(), name='produto_ajuste_estoque'),
]


