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

    # Rota para exibição detalhada dos dados cadastrais, endereço e status de um tenant identificado pelo slug ou public_id
    path('lojas/<slug:slug>/', views.LojaDetailView.as_view(), name='loja_detail'),
    path('lojas/<uuid:public_id>/', views.LojaDetailView.as_view(), name='loja_detail_uuid'),

    # Rota para edição e atualização cadastral dos dados estruturais de uma loja identificada pelo slug ou public_id
    path('lojas/<slug:slug>/editar/', views.LojaUpdateView.as_view(), name='loja_update'),
    path('lojas/<uuid:public_id>/editar/', views.LojaUpdateView.as_view(), name='loja_update_uuid'),

    # Rota para controle e alternância das feature flags de módulos contratados de uma loja específica
    path('lojas/<slug:slug>/modulos/', views.LojaModulosView.as_view(), name='loja_modulos'),
    path('lojas/<uuid:public_id>/modulos/', views.LojaModulosView.as_view(), name='loja_modulos_uuid'),

    # Gestão de Usuários com RBAC (RF-02)
    # Rota para listagem de contas de operadores filtradas pelo escopo da loja ou visão global (DEV)
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),

    # Rota para cadastro de novo usuário com atribuição de papel RBAC e vinculação de tenant
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario_create'),

    # Rota para atualização de dados cadastrais e papel hierárquico de um usuário identificado pelo public_id universal
    path('usuarios/<uuid:public_id>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),

    # Rota POST para alternar o status operacional (ativo/inativo) de uma conta de usuário pelo public_id
    path('usuarios/<uuid:public_id>/status/', views.UsuarioToggleStatusView.as_view(), name='usuario_toggle_status'),

    # Rota para redefinição administrativa da senha de um operador subordinado por gestores pelo public_id
    path('usuarios/<uuid:public_id>/redefinir-senha/', views.UsuarioPasswordResetAdminView.as_view(), name='usuario_password_reset'),

    # Matriz RBAC (Governança de Identidade e Acessos)
    path('usuarios/matriz/', __import__('apps.accounts.views', fromlist=['MatrizRBACView']).MatrizRBACView.as_view(), name='usuario_matriz'),
    path('usuarios/matriz/toggle/', __import__('apps.accounts.views', fromlist=['MatrizRBACToggleView']).MatrizRBACToggleView.as_view(), name='usuario_matriz_toggle'),
]
