from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q, Count

from .models import Loja, PerfilUsuario
from .forms import LojaForm
from .permissions import DevRequiredMixin, usuario_is_dev


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    """
    Visão geral inicial da plataforma, adaptada dinamicamente conforme o papel do usuário.
    """
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        
        if context['is_dev']:
            context['total_lojas'] = Loja.objects.count()
            context['lojas_ativas'] = Loja.objects.filter(ativo=True).count()
            context['ultimas_lojas'] = Loja.objects.order_by('-criado_em')[:5]
        else:
            perfil = getattr(user, 'perfil', None)
            context['perfil'] = perfil
            context['minha_loja'] = perfil.loja if perfil else None

        return context


class LojaListView(DevRequiredMixin, ListView):
    """
    Listagem de todas as Lojas (Tenants) cadastradas. Exclusivo para perfil DEV.
    """
    model = Loja
    template_name = 'core/loja_list.html'
    context_object_name = 'lojas'
    paginate_by = 15

    def get_queryset(self):
        queryset = Loja.objects.annotate(total_usuarios=Count('usuarios')).order_by('-criado_em')
        termo_busca = self.request.GET.get('q', '').strip()
        status_filtro = self.request.GET.get('status', '').strip()

        if termo_busca:
            queryset = queryset.filter(
                Q(nome__icontains=termo_busca) |
                Q(cnpj__icontains=termo_busca) |
                Q(cidade__icontains=termo_busca) |
                Q(email__icontains=termo_busca)
            )

        if status_filtro == 'ativo':
            queryset = queryset.filter(ativo=True)
        elif status_filtro == 'inativo':
            queryset = queryset.filter(ativo=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['total_cadastradas'] = Loja.objects.count()
        context['total_ativas'] = Loja.objects.filter(ativo=True).count()
        return context


class LojaCreateView(DevRequiredMixin, CreateView):
    """
    Tela de provisionamento e cadastro de nova Loja (Tenant) no Hub.
    Restrita exclusivamente ao perfil DEV (RF-01 / RN-07).
    """
    model = Loja
    form_class = LojaForm
    template_name = 'core/loja_form.html'
    success_url = reverse_lazy('loja_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Loja '{self.object.nome}' cadastrada e provisionada com sucesso!"
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


class LojaUpdateView(DevRequiredMixin, UpdateView):
    """
    Tela de edição dos dados cadastrais e credenciais da Loja.
    Restrita exclusivamente ao perfil DEV.
    """
    model = Loja
    form_class = LojaForm
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'core/loja_form.html'
    success_url = reverse_lazy('loja_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Dados da loja '{self.object.nome}' atualizados com sucesso!"
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['loja'] = self.object
        return context


class LojaDetailView(DevRequiredMixin, DetailView):
    """
    Exibição completa das informações cadastrais, status e credenciais de uma Loja.
    """
    model = Loja
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'core/loja_detail.html'
    context_object_name = 'loja'

