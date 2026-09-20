# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    path('', views.AnuncioListView.as_view(), name='anuncio_list'),
    path('novo/', views.AnuncioCreateView.as_view(), name='anuncio_create'),
    path('<int:pk>/', views.AnuncioDetailView.as_view(), name='anuncio_detail'),
    path('<int:pk>/editar/', views.AnuncioUpdateView.as_view(), name='anuncio_update'),
    path('importar/<int:pk>/', views.AnuncioImportarView.as_view(), name='anuncio_importar'),
    path('<int:pk>/composicao/adicionar/', views.AnuncioComposicaoCreateView.as_view(), name='anuncio_composicao_add'),
    path('<int:anuncio_id>/composicao/<int:pk>/excluir/', views.AnuncioComposicaoDeleteView.as_view(), name='anuncio_composicao_delete'),
    path('composicao/<int:pk>/excluir/', views.AnuncioComposicaoDeleteView.as_view(), name='anuncio_composicao_delete_legacy'),
    path('<int:pk>/sincronizar/', views.AnuncioSincronizarView.as_view(), name='anuncio_sincronizar'),
    path('<int:pk>/toggle-ignorar/', views.AnuncioToggleIgnorarView.as_view(), name='anuncio_toggle_ignorar'),
]

