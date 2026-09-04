# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    path('', views.MockarDadosDashboardView.as_view(), name='mockar_dados_dashboard'),
    path('alternar-simulacao/', views.AlternarSimulacaoMockView.as_view(), name='alternar_simulacao_mock'),
]
