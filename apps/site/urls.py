# Os códigos foram gerados com auxilio de I.A.

from django.urls import path
from . import views

app_name = 'site'

urlpatterns = [
    # Rota raiz dinâmica comutada por visibilidade pública e login (Doc ① §11.1)
    path('', views.RaizView.as_view(), name='home'),

    # Rota pública para a folha de estilos do tema dinâmico (Doc ① §11.12 item 6)
    path('tema.css', views.tema_css_view, name='tema_css'),

    # Rota pública institucional / landing page (Doc ① §11.1)
    path('apresentacao/', views.LandingPageView.as_view(), name='landing'),

    # Rota autenticada para alternância entre os 10 modelos canônicos e personalização (Doc ① §11.6 a §11.9)
    path('tema/alternar/', views.AlternarTemaView.as_view(), name='tema_alternar'),
]
