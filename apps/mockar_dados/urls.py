# Os códigos foram gerados com auxilio de I.A.

# Importa a função path do módulo de roteamento de URLs do Django para mapeamento de rotas HTTP
from django.urls import path

# Importa o módulo de views do aplicativo mockar_dados contendo as Class-Based Views (CBVs)
from . import views

# Declara a lista padrão urlpatterns que define as rotas acessíveis no namespace deste aplicativo
urlpatterns = [
    # Rota raiz do aplicativo que renderiza o painel de controle e aciona as ações de geração e expurgo de dados sintéticos
    path('', views.MockarDadosDashboardView.as_view(), name='mockar_dados_dashboard'),

    # Rota acionada para alternar o estado da feature flag de simulação de rotas mock (modo HTTP 200 vs modo HTTP 401)
    path('alternar-simulacao/', views.AlternarSimulacaoMockView.as_view(), name='alternar_simulacao_mock'),
]
