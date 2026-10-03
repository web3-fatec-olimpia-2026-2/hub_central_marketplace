# Os códigos foram gerados com auxilio de I.A.
"""
Rotas para o app accounts (Matriz RBAC e governança de acessos).
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('matriz/', views.MatrizRBACView.as_view(), name='matriz'),
    path('matriz/toggle/', views.MatrizRBACToggleView.as_view(), name='matriz_toggle'),
]
