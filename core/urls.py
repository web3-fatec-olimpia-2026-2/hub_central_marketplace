from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardHomeView.as_view(), name='home'),
    path('lojas/', views.LojaListView.as_view(), name='loja_list'),
    path('lojas/nova/', views.LojaCreateView.as_view(), name='loja_create'),
    path('lojas/<slug:slug>/', views.LojaDetailView.as_view(), name='loja_detail'),
    path('lojas/<slug:slug>/editar/', views.LojaUpdateView.as_view(), name='loja_update'),
]
