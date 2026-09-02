# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    # Simulador Promocional e Formação de Preço
    path('simulador-promocional/', views.SimuladorPromocionalView.as_view(), name='simulador_promocional'),
]
