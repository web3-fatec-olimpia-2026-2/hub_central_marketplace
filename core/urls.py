from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.DashboardHomeView.as_view(), name='home'),

    # Gestão de Lojas (Tenants) — Exclusivo DEV
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
]

