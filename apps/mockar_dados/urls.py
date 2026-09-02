# Os códigos foram gerados com auxilio de I.A.
from django.urls import path
from . import views

urlpatterns = [
    path('', views.MockarDadosDashboardView.as_view(), name='mockar_dados_dashboard'),
]
