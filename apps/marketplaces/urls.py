# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard Central Multicanal
    path('marketplaces/', views.CanalListView.as_view(), name='canal_list'),
    path('loja/integracao-mercadolivre/', views.CanalListView.as_view(), name='loja_integracao_meli'),

    # Gestão de Contas e Credenciais por Canal
    path('marketplaces/contas/nova/', views.ContaMarketplaceCreateView.as_view(), name='conta_marketplace_create'),
    path('marketplaces/contas/<int:pk>/editar/', views.ContaMarketplaceUpdateView.as_view(), name='conta_marketplace_update'),
    path('marketplaces/contas/<int:pk>/excluir/', views.ContaMarketplaceDeleteView.as_view(), name='conta_marketplace_delete'),
    path('marketplaces/contas/<int:pk>/testar/', views.ContaMarketplaceTestarView.as_view(), name='conta_marketplace_testar'),

    # Logs e Telemetria de Sincronização
    path('logs/sincronizacao/', views.LogSincronizacaoListView.as_view(), name='log_sincronizacao_list'),
]
