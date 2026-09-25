# Os códigos foram gerados com auxilio de I.A.

# Importa a função path do submódulo django.urls para declaração de rotas HTTP do framework
from django.urls import path

# Importa o módulo de views do aplicativo marketplaces com as Class-Based Views (CBVs)
from . import views

# Declara a lista padrão urlpatterns que mapeia os endpoints HTTP do módulo marketplaces
urlpatterns = [
    # Dashboard Central Multicanal
    # Rota que apresenta o painel central com todos os canais e integrações ativas da loja
    path('marketplaces/', views.CanalListView.as_view(), name='canal_list'),

    # Rota de compatibilidade legada que direciona para a mesma tela de gerenciamento de canais
    path('loja/integracao-mercadolivre/', views.CanalListView.as_view(), name='loja_integracao_meli'),

    # Gestão de Contas e Conexões por Canal
    # Rota com formulário para cadastro e conexão de uma nova conta de marketplace
    path('marketplaces/contas/nova/', views.ContaMarketplaceCreateView.as_view(), name='conta_marketplace_create'),

    # Rota com formulário de edição de parâmetros e credenciais de uma conta existente pelo ID primário
    path('marketplaces/contas/<int:pk>/editar/', views.ContaMarketplaceUpdateView.as_view(), name='conta_marketplace_update'),

    # Rota de confirmação e exclusão de uma conta de marketplace vinculada à loja
    path('marketplaces/contas/<int:pk>/excluir/', views.ContaMarketplaceDeleteView.as_view(), name='conta_marketplace_delete'),

    # Endpoint acionado via POST para executar ping/teste de conectividade com a API externa do canal
    path('marketplaces/contas/<int:pk>/testar/', views.ContaMarketplaceTestarView.as_view(), name='conta_marketplace_testar'),

    # Endpoint acionado via POST para revogar ou limpar tokens OAuth da conta mantendo o cadastro intacto
    path('marketplaces/contas/<int:pk>/desconectar/', views.ContaMarketplaceDesconectarView.as_view(), name='conta_marketplace_desconectar'),

    # Fluxo OAuth 2.0 Mercado Livre
    # Rota que inicia o redirecionamento para o portal de login e consentimento da API do Mercado Livre
    path('marketplaces/contas/<int:pk>/conectar-meli/', views.MercadoLivreAutorizarView.as_view(), name='mercadolivre_autorizar'),

    # Rota oficial de callback que recebe o 'code' de autorização temporário retornado pelo Mercado Livre
    path('marketplaces/mercadolivre/callback/', views.MercadoLivreCallbackView.as_view(), name='mercadolivre_callback'),

    # Rota alternativa legada (v1) para recepção do redirect do fluxo de consentimento OAuth
    path('v1/callback/', views.MercadoLivreCallbackView.as_view(), name='mercadolivre_callback_v1'),

    # Rota alternativa configurada para testes de integração via Postman ou clientes de API externos
    path('oauth/v1/callback/', views.MercadoLivreCallbackView.as_view(), name='mercadolivre_callback_pstmn'),

    # Logs e Telemetria de Sincronização
    # Rota da interface que lista as chamadas de API externas, latências de rede e eventos auditados
    path('logs/sincronizacao/', views.LogSincronizacaoListView.as_view(), name='log_sincronizacao_list'),

    # Endpoint administrativo restrito para reprocessar manualmente um evento de webhook que tenha falhado
    path('logs/webhooks/<int:pk>/replay/', views.WebhookEventReplayView.as_view(), name='webhook_event_replay'),

    # Webhook Unificado com Suporte Híbrido (Global e Individual com UUID)
    # Endpoint central de ingestão de webhooks multi-tenant parametrizado pelo nome do canal (ex.: mercadolivre, shopee)
    path('api/v1/webhooks/<str:canal>/', views.WebhookIngestionView.as_view(), name='webhook_global'),

    # Endpoint dedicado por conta, segmentado por UUID para autenticação HMAC simétrica estrita
    path('api/v1/webhooks/<str:canal>/<uuid:webhook_uuid>/', views.WebhookIngestionView.as_view(), name='webhook_individual'),

    # Webhooks Nativos Mercado Livre (Legado / Compatibilidade)
    # Rota de compatibilidade retroativa para receber webhooks diretos da API legada do Mercado Livre
    path('marketplaces/webhooks/mercadolivre/', views.MercadoLivreWebhookView.as_view(), name='mercadolivre_webhook'),
]