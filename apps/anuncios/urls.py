# Os códigos foram gerados com auxilio de I.A.

# Importa a função utilitária 'path' do Django para mapeamento de rotas e padrões de URL
from django.urls import path

# Importa o módulo de views local do próprio aplicativo 'apps.anuncios'
from . import views

# Lista ordenada de rotas do submódulo de anúncios (prefixadas sob '/anuncios/' pelo urls.py raiz)
urlpatterns = [
    # Rota raiz do módulo: renderiza a listagem paginada e filtrada de anúncios vinculados ao tenant
    path('', views.AnuncioListView.as_view(), name='anuncio_list'),
    
    # Rota para renderizar e processar o formulário de cadastro manual de novo anúncio com formset de composição
    path('novo/', views.AnuncioCreateView.as_view(), name='anuncio_create'),
    
    # Rota de detalhamento: exibe a ficha técnica, composição física, cota vendável e histórico de auditoria do anúncio
    path('<int:pk>/', views.AnuncioDetailView.as_view(), name='anuncio_detail'),
    
    # Rota para carregar o formulário de alteração de preço, título e componentes da composição do anúncio
    path('<int:pk>/editar/', views.AnuncioUpdateView.as_view(), name='anuncio_update'),
    
    # Rota que aciona a importação/varredura de anúncios de uma ContaMarketplace específica informada pela PK
    path('importar/<int:pk>/', views.AnuncioImportarView.as_view(), name='anuncio_importar'),
    
    # Rota rápida (modal ou inline) para inclusão pontual de um produto físico na composição do anúncio informado
    path('<int:pk>/composicao/adicionar/', views.AnuncioComposicaoCreateView.as_view(), name='anuncio_composicao_add'),
    
    # Rota estruturada para exclusão de um item específico da composição garantindo o contexto do anúncio pai
    path('<int:anuncio_id>/composicao/<int:pk>/excluir/', views.AnuncioComposicaoDeleteView.as_view(), name='anuncio_composicao_delete'),
    
    # Rota legada de exclusão direta de item de composição pela sua PK, mantida para compatibilidade
    path('composicao/<int:pk>/excluir/', views.AnuncioComposicaoDeleteView.as_view(), name='anuncio_composicao_delete_legacy'),
    
    # Rota que força a sincronização manual de estoque e preço do anúncio diretamente para a API do marketplace
    path('<int:pk>/sincronizar/', views.AnuncioSincronizarView.as_view(), name='anuncio_sincronizar'),
    
    # Rota para alternar a flag de auditoria/ignorar anúncio (trocando entre estados CANCELADO e PENDENTE/ENVIADO)
    path('<int:pk>/toggle-ignorar/', views.AnuncioToggleIgnorarView.as_view(), name='anuncio_toggle_ignorar'),
]
