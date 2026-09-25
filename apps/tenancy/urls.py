# Os códigos foram gerados com auxilio de I.A.

# Importa a função path do módulo de roteamento de URLs do framework Django
from django.urls import path

# Importa o módulo de views do aplicativo apps.tenancy contendo as CBVs de tenancy, RBAC e dashboard
from . import views

# Declaração da lista padrão urlpatterns que define as rotas deste módulo
urlpatterns = [
    # Dashboard Inicial
    # Rota raiz do aplicativo que renderiza o painel principal consolidado do sistema para usuários autenticados
    path('', views.DashboardHomeView.as_view(), name='home'),

    # Gestão de Lojas (Tenants) & Feature Flags — Exclusivo DEV (RF-01)
    # Rota para listagem global de todas as lojas e tenants cadastrados na plataforma
    path('lojas/', views.LojaListView.as_view(), name='loja_list'),

    # Rota para criação e provisionamento de uma nova organização tenant (loja)
    path('lojas/nova/', views.LojaCreateView.as_view(), name='loja_create'),

    # Rota para exibição detalhada dos dados cadastrais, endereço e status de um tenant identificado pelo slug
    path('lojas/<slug:slug>/', views.LojaDetailView.as_view(), name='loja_detail'),

    # Rota para edição e atualização cadastral dos dados estruturais de uma loja identificada pelo slug
    path('lojas/<slug:slug>/editar/', views.LojaUpdateView.as_view(), name='loja_update'),

    # Rota para controle e alternância das feature flags de módulos contratados de uma loja específica
    path('lojas/<slug:slug>/modulos/', views.LojaModulosView.as_view(), name='loja_modulos'),

    # Gestão de Usuários com RBAC (RF-02)
    # Rota para listagem de contas de operadores filtradas pelo escopo da loja ou visão global (DEV)
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),

    # Rota para cadastro de novo usuário com atribuição de papel RBAC e vinculação de tenant
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario_create'),

    # Rota para atualização de dados cadastrais e papel hierárquico de um usuário identificado pela chave primária (pk)
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),

    # Rota POST para alternar o status operacional (ativo/inativo) de uma conta de usuário
    path('usuarios/<int:pk>/status/', views.UsuarioToggleStatusView.as_view(), name='usuario_toggle_status'),

    # Rota para redefinição administrativa da senha de um operador subordinado por gestores
    path('usuarios/<int:pk>/redefinir-senha/', views.UsuarioPasswordResetAdminView.as_view(), name='usuario_password_reset'),
]
