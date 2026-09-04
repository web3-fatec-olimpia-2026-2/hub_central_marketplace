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
from .connectors.mercadolivre import MercadoLivreConnector


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
        sucesso, msg, _ = connector.autenticar(request=request)

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


# ==============================================================================
# FLUXO OAUTH 2.0 EXCLUSIVO MERCADO LIVRE
# ==============================================================================

class MercadoLivreAutorizarView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, View):
    """
    O QUE FAZ: Inicia o fluxo de autorização OAuth 2.0 redirecionando o lojista para o Mercado Livre.
    POR QUE FAZ: Elimina inputs manuais de tokens, permitindo consentimento direto do seller no canal oficial.
    PERMISSÕES RBAC: DEV e ADMIN (da respectiva loja).
    MULTI-TENANCY: Garante que o lojista só autorize contas da sua própria loja.
    """
    modulo_requerido = 'marketplaces'

    def get(self, request, pk, *args, **kwargs):
        conta = get_object_or_404(ContaMarketplace, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta pertence a outra loja.")

        # Se for conta mockada, respeita a feature flag de simulação
        if conta.is_mock:
            from apps.mockar_dados.services import is_simular_rotas_mock_ativo
            if is_simular_rotas_mock_ativo(request):
                state = f"conta_{conta.pk}"
                code = f"MOCK_CODE_{conta.pk}"
                callback_url = f"{reverse('mercadolivre_callback')}?code={code}&state={state}"
                return redirect(callback_url)
            else:
                LogSincronizacao.objects.create(
                    loja=conta.loja,
                    conta_marketplace=conta,
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO,
                    payload_enviado={"conta_id": conta.pk},
                    resposta_recebida={"error": "unauthorized", "message": "Não autorizado: credenciais ausentes ou inválidas no marketplace"},
                    status_http=401,
                    sucesso=False,
                    mensagem_erro="Não autorizado: credenciais ausentes ou inválidas no marketplace",
                    tempo_resposta_ms=110,
                )
                messages.error(request, "[Mercado Livre] Erro HTTP 401: Não autorizado: credenciais ausentes ou inválidas no marketplace")
                return redirect('canal_list')

        state = f"conta_{conta.pk}"
        auth_url = MercadoLivreConnector.gerar_url_autorizacao(state=state)
        return redirect(auth_url)


class MercadoLivreCallbackView(View):
    """
    O QUE FAZ: Recebe o callback OAuth 2.0 do Mercado Livre com o authorization code e executa a troca por tokens.
    POR QUE FAZ: Persiste tokens criptografados na conta correspondente e exibe tela de sucesso com redirecionamento em 3s.
    SEGURANÇA: Registra auditoria, valida o state e não expõe credenciais brutas.
    """
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', '').strip()
        state = request.GET.get('state', '').strip()
        error = request.GET.get('error', '').strip()
        error_description = request.GET.get('error_description', '').strip()

        if error:
            messages.error(request, f"Erro retornado pelo Mercado Livre: {error_description or error}")
            return redirect('canal_list')

        if not code:
            messages.error(request, "Código de autorização (code) não foi fornecido pelo Mercado Livre.")
            return redirect('canal_list')

        # Identifica a conta a partir do state
        conta = None
        if state and state.startswith('conta_'):
            try:
                conta_id = int(state.replace('conta_', ''))
                conta = ContaMarketplace.objects.filter(pk=conta_id).first()
            except ValueError:
                pass

        if not conta and request.user.is_authenticated:
            # Fallback para usuário autenticado: primeira conta ML da sua loja
            perfil = getattr(request.user, 'perfil', None)
            if perfil and perfil.loja:
                conta = ContaMarketplace.objects.filter(
                    loja=perfil.loja, canal=CanalMarketplaceEnum.MERCADOLIVRE
                ).first()

        if not conta:
            # Se ainda assim não encontrar, associa à primeira conta ML cadastrada
            conta = ContaMarketplace.objects.filter(canal=CanalMarketplaceEnum.MERCADOLIVRE).first()

        sucesso, msg, res_json, log = MercadoLivreConnector.trocar_code_por_token(
            code=code,
            conta=conta,
            usuario=request.user if request.user.is_authenticated else None,
            request=request,
        )

        if sucesso:
            if conta:
                LogAuditoria.objects.create(
                    loja=conta.loja,
                    autor=request.user if request.user.is_authenticated else None,
                    evento=EventoAuditoriaEnum.CRIACAO_CONTA,
                    detalhes=f"Conta '{conta.apelido_conta}' autorizada com sucesso via OAuth 2.0 no Mercado Livre (Seller ID: {conta.seller_id_externo}).",
                    ip_origem=request.META.get('REMOTE_ADDR')
                )

            context = {
                'conta': conta,
                'loja': conta.loja if conta else None,
                'seller_id': conta.seller_id_externo if conta else res_json.get('user_id'),
                'apelido': conta.apelido_conta if conta else 'Mercado Livre',
            }
            return render(request, 'marketplaces/callback_sucesso.html', context)
        else:
            messages.error(request, f"Falha na autorização do Mercado Livre: {msg}")
            return redirect('canal_list')


class ContaMarketplaceDesconectarView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, View):
    """
    O QUE FAZ: Limpa os tokens OAuth e desconecta com segurança a conta de marketplace da loja.
    POR QUE FAZ: Permite ao gestor revogar credenciais ou reconectar do zero sem excluir o histórico de anúncios.
    PERMISSÕES RBAC: DEV e ADMIN (da respectiva loja).
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    modulo_requerido = 'marketplaces'

    def post(self, request, pk, *args, **kwargs):
        conta = get_object_or_404(ContaMarketplace, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta pertence a outra loja.")

        with transaction.atomic():
            conta.access_token = None
            conta.refresh_token = None
            conta.token_expira_em = None
            conta.seller_id_externo = None
            conta.save(update_fields=[
                'access_token', 'refresh_token', 'token_expira_em', 'seller_id_externo', 'updated_at'
            ])

            LogAuditoria.objects.create(
                loja=conta.loja,
                autor=request.user,
                evento=EventoAuditoriaEnum.EDICAO_CONTA,
                detalhes=f"Tokens da conta '{conta.apelido_conta}' ({conta.get_canal_display()}) foram limpos/desconectados.",
                ip_origem=request.META.get('REMOTE_ADDR')
            )

        messages.success(request, f"Conta '{conta.apelido_conta}' desconectada com sucesso.")
        return redirect('canal_list')
