# Os códigos foram gerados com auxilio de I.A.

# Importa a função utilitária path do framework Django para declaração de rotas e padrões de URL
from django.urls import path

# Importa o módulo de views do aplicativo financeiro contendo os controladores baseados em classe
from . import views

# Lista de padrões de rotas da aplicação financeira vinculadas ao roteador principal do Django
urlpatterns = [
    # Simulador Promocional e Formação de Preço
    # Rota que atende à interface e às requisições AJAX do simulador promocional e inteligência financeira
    path('simulador-promocional/', views.SimuladorPromocionalView.as_view(), name='simulador_promocional'),
]