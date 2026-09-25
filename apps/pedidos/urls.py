# Os códigos foram gerados com auxilio de I.A.

# Importa a função path do módulo de roteamento de URLs do Django para mapeamento de endpoints HTTP
from django.urls import path

# Importa o módulo views deste mesmo aplicativo contendo as Class-Based Views de pedidos e webhooks
from . import views

# Declaração da lista padrão urlpatterns contendo os mapeamentos de rotas do domínio de pedidos
urlpatterns = [
    # Listagem e Detalhes de Pedidos (RF-06)
    # Rota que renderiza a listagem paginada e filtrável de pedidos de venda da loja (tenant)
    path('pedidos/', views.PedidoVendaListView.as_view(), name='pedido_list'),

    # Rota que renderiza a visualização detalhada de um pedido de venda específico pelo seu ID (chave primária)
    path('pedidos/<int:pk>/', views.PedidoVendaDetailView.as_view(), name='pedido_detail'),

    # Endpoints de Webhooks Multicanal (RF-06 / RN-05)
    # Endpoint público genérico para recepção assíncrona de notificações de vendas do Mercado Livre
    path('marketplaces/webhook/mercadolivre/', views.WebhookMercadoLivreView.as_view(), name='webhook_mercadolivre'),

    # Endpoint público parametrizado por slug de loja para identificar o tenant de destino de notificações do Mercado Livre
    path('marketplaces/webhook/mercadolivre/<slug:slug>/', views.WebhookMercadoLivreView.as_view(), name='webhook_mercadolivre_slug'),

    # Endpoint público para recepção assíncrona de notificações de pedidos originados na plataforma Shopee
    path('marketplaces/webhook/shopee/', views.WebhookShopeeView.as_view(), name='webhook_shopee'),

    # Endpoint público para recepção assíncrona de notificações de pedidos originados no Magazine Luiza (Magalu)
    path('marketplaces/webhook/magalu/', views.WebhookMagaluView.as_view(), name='webhook_magalu'),
]
