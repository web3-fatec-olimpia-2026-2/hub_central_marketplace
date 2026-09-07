# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard Central Multicanal
    path('marketplaces/', views.CanalListView.as_view(), name='canal_list'),
    path('loja/integracao-mercadolivre/', views.CanalListView.as_view(), name='loja_integracao_meli'),

    # Gestão de Contas e Conexões por Canal
    path('marketplaces/contas/nova/', views.ContaMarketplaceCreateView.as_view(), name='conta_marketplace_create'),
    path('marketplaces/contas/<int:pk>/editar/', views.ContaMarketplaceUpdateView.as_view(), name='conta_marketplace_update'),
    path('marketplaces/contas/<int:pk>/excluir/', views.ContaMarketplaceDeleteView.as_view(), name='conta_marketplace_delete'),
    path('marketplaces/contas/<int:pk>/testar/', views.ContaMarketplaceTestarView.as_view(), name='conta_marketplace_testar'),
    path('marketplaces/contas/<int:pk>/desconectar/', views.ContaMarketplaceDesconectarView.as_view(), name='conta_marketplace_desconectar'),

    # Fluxo OAuth 2.0 Mercado Livre
    path('marketplaces/contas/<int:pk>/conectar-meli/', views.MercadoLivreAutorizarView.as_view(), name='mercadolivre_autorizar'),
    path('marketplaces/mercadolivre/callback/', views.MercadoLivreCallbackView.as_view(), name='mercadolivre_callback'),
    path('v1/callback/', views.MercadoLivreCallbackView.as_view(), name='mercadolivre_callback_v1'),
    path('oauth/v1/callback/', views.MercadoLivreCallbackView.as_view(), name='mercadolivre_callback_pstmn'),

    # Logs e Telemetria de Sincronização
    path('logs/sincronizacao/', views.LogSincronizacaoListView.as_view(), name='log_sincronizacao_list'),

    # Webhooks Nativos Mercado Livre
    path('marketplaces/webhooks/mercadolivre/', views.MercadoLivreWebhookView.as_view(), name='mercadolivre_webhook'),
]
