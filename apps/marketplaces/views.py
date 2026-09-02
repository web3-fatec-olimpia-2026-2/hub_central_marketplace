# Os códigos foram gerados com auxilio de I.A.
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from apps.tenancy.models import Loja
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, usuario_is_dev,
    pode_configurar_integracao
)
from .models import ContaMarketplace, LogSincronizacao, LogAuditoria
from .enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from .forms import ContaMarketplaceForm
from .connectors.factory import get_connector_for_conta


class CanalListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Dashboard central multicanal listando todas as contas e canais integrados da Loja.
    POR QUE FAZ: Ponto único de controle e monitoramento de conectores de marketplaces (Mercado Livre, Shopee, Magalu, Amazon).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (com módulo 'marketplaces' ativo).
    MULTI-TENANCY: Filtra as contas vinculadas à loja do usuário logado (ou todas se DEV).
    """
    modulo_requerido = 'marketplaces'
    model = ContaMarketplace
    template_name = 'marketplaces/canal_list.html'
    context_object_name = 'contas'

    def get_queryset(self):
        user = self.request.user
        queryset = ContaMarketplace.objects.select_related('loja').order_by('canal', 'apelido_conta')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return ContaMarketplace.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        canal_filtro = self.request.GET.get('canal', '').strip()
        if canal_filtro:
            queryset = queryset.filter(canal=canal_filtro)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['pode_configurar'] = pode_configurar_integracao(user)
        context['canais_disponiveis'] = CanalMarketplaceEnum.choices
        context['canal_filtro'] = self.request.GET.get('canal', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


class ContaMarketplaceCreateView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, CreateView):
    """
    O QUE FAZ: Conexão e cadastro de nova conta de marketplace para o tenant.
    POR QUE FAZ: Permite cadastrar credenciais API de múltiplos canais por loja.
    PERMISSÕES RBAC: DEV e ADMIN (RF-05).
    MULTI-TENANCY: Vínculo automático à loja do lojista.
    """
    modulo_requerido = 'marketplaces'
    model = ContaMarketplace
    form_class = ContaMarketplaceForm
    template_name = 'marketplaces/conta_form.html'
    success_url = reverse_lazy('canal_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.CRIACAO_CONTA,
                detalhes=f"Conta '{self.object.apelido_conta}' ({self.object.get_canal_display()}) conectada à loja '{self.object.loja.nome}'.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
        messages.success(self.request, f"Conta '{self.object.apelido_conta}' cadastrada com sucesso!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        return context


class ContaMarketplaceUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, UpdateView):
    """
    O QUE FAZ: Edição de credenciais e parâmetros de uma conta de marketplace existente.
    POR QUE FAZ: Manutenção de tokens e chaves de integração.
    PERMISSÕES RBAC: DEV e ADMIN (da respectiva loja).
    MULTI-TENANCY: Ownership check da conta com a loja do usuário.
    """
    modulo_requerido = 'marketplaces'
    model = ContaMarketplace
    form_class = ContaMarketplaceForm
    template_name = 'marketplaces/conta_form.html'
    success_url = reverse_lazy('canal_list')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta de marketplace pertence a outra loja.")
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EDICAO_CONTA,
                detalhes=f"Credenciais da conta '{self.object.apelido_conta}' ({self.object.get_canal_display()}) atualizadas.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
        messages.success(self.request, f"Conta '{self.object.apelido_conta}' atualizada com sucesso!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['conta'] = self.object
        return context


class ContaMarketplaceDeleteView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, DeleteView):
    """
    O QUE FAZ: Desconexão e exclusão de uma conta de marketplace.
    POR QUE FAZ: Permite revogar o vínculo de um canal.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Isolado por loja.
    """
    modulo_requerido = 'marketplaces'
    model = ContaMarketplace
    template_name = 'marketplaces/conta_confirm_delete.html'
    success_url = reverse_lazy('canal_list')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")
        return obj

    def form_valid(self, form):
        with transaction.atomic():
            apelido = self.object.apelido_conta
            loja = self.object.loja
            LogAuditoria.objects.create(
                loja=loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.EXCLUSAO_CONTA,
                detalhes=f"Conta '{apelido}' desconectada da loja '{loja.nome}'.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
            messages.success(self.request, f"Conta '{apelido}' removida com sucesso.")
            return super().form_valid(form)


class ContaMarketplaceTestarView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, View):
    """
    O QUE FAZ: Executa teste de conectividade e validação de credenciais em tempo real com a API do marketplace.
    POR QUE FAZ: Permite ao gestor confirmar se o token OAuth ou credenciais estão operacionais.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Restrito à conta da loja.
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, pk, *args, **kwargs):
        conta = get_object_or_404(ContaMarketplace, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        connector = get_connector_for_conta(conta)
        sucesso, msg, _ = connector.autenticar()

        if sucesso:
            messages.success(request, f"[{conta.get_canal_display()}] {msg}")
        else:
            messages.error(request, f"[{conta.get_canal_display()}] {msg}")

        return redirect('canal_list')


class LogSincronizacaoListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Relatório e visualização de telemetria e logs de chamadas externas de integração.
    POR QUE FAZ: Diagnóstico técnico de erros de precificação, estoque e requisições HTTP (RF-05 / RN-04).
    PERMISSÕES RBAC: DEV (todas as lojas); ADMIN, SUPERVISOR e USUARIO (leitura na própria loja).
    MULTI-TENANCY: Filtro obrigatório por loja para não-DEV.
    """
    modulo_requerido = 'marketplaces'
    model = LogSincronizacao
    template_name = 'marketplaces/log_sincronizacao_list.html'
    context_object_name = 'logs'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        queryset = LogSincronizacao.objects.select_related('loja', 'conta_marketplace').order_by('-criado_em')

        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return LogSincronizacao.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        canal_filtro = self.request.GET.get('canal', '').strip()
        if canal_filtro:
            queryset = queryset.filter(canal=canal_filtro)

        sucesso_filtro = self.request.GET.get('sucesso', '').strip()
        if sucesso_filtro == '1':
            queryset = queryset.filter(sucesso=True)
        elif sucesso_filtro == '0':
            queryset = queryset.filter(sucesso=False)

        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(item_id_externo__icontains=busca) |
                Q(mensagem_erro__icontains=busca) |
                Q(evento__icontains=busca)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dev'] = usuario_is_dev(user)
        context['canais_disponiveis'] = CanalMarketplaceEnum.choices
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['canal_filtro'] = self.request.GET.get('canal', '').strip()
        context['sucesso_filtro'] = self.request.GET.get('sucesso', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context
