# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    # Listagem e Detalhes de Pedidos (RF-06)
    path('pedidos/', views.PedidoVendaListView.as_view(), name='pedido_list'),
    path('pedidos/<int:pk>/', views.PedidoVendaDetailView.as_view(), name='pedido_detail'),

    # Endpoints de Webhooks Multicanal (RF-06 / RN-05)
    path('marketplaces/webhook/mercadolivre/', views.WebhookMercadoLivreView.as_view(), name='webhook_mercadolivre'),
    path('marketplaces/webhook/mercadolivre/<slug:slug>/', views.WebhookMercadoLivreView.as_view(), name='webhook_mercadolivre_slug'),
    path('marketplaces/webhook/shopee/', views.WebhookShopeeView.as_view(), name='webhook_shopee'),
    path('marketplaces/webhook/magalu/', views.WebhookMagaluView.as_view(), name='webhook_magalu'),
]
