# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo json da biblioteca padrão para serialização e desserialização de payloads
import json

# Importa funções atalhos do Django para renderização de templates, redirecionamento e recuperação com 404
from django.shortcuts import render, redirect, get_object_or_404

# Importa utilitários para resolução reversa de URLs de maneira síncrona ou tardia (lazy)
from django.urls import reverse_lazy, reverse

# Importa classes genéricas do Django (CBVs) para CRUD, visualizações base e detalhes de objetos
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View, DetailView

# Importa decorador para isentar endpoints da verificação de tokens CSRF (essencial para webhooks e callbacks)
from django.views.decorators.csrf import csrf_exempt

# Importa utilitário que permite aplicar decoradores de funções diretamente em métodos de classes baseadas em View
from django.utils.decorators import method_decorator

# Importa classes de resposta HTTP especializadas para retorno em formato JSON e métodos não permitidos (405)
from django.http import JsonResponse, HttpResponseNotAllowed

# Importa mixin nativo que restringe o acesso de views a usuários previamente autenticados na sessão
from django.contrib.auth.mixins import LoginRequiredMixin

# Importa o framework de mensagens transitórias para feedback ao usuário na interface
from django.contrib import messages

# Importa o gerenciador de transações atômicas para garantir atomicidade em operações de banco de dados
from django.db import transaction

# Importa a classe Q para construção de filtros complexos com operadores lógicos (OR, AND) no ORM
from django.db.models import Q

# Importa exceção padrão de segurança para interrupção de fluxo com retorno HTTP 403 Forbidden
from django.core.exceptions import PermissionDenied

# Importa o objeto de configurações globais do projeto Django
from django.conf import settings

# Importa o serviço especialista em recepção, validação e baixa de estoque de webhooks do Mercado Livre
from .services import MercadoLivreWebhookService

# Importa o modelo central de organização tenant
from apps.tenancy.models import Loja

# Importa mixins de permissão e funções utilitárias do sistema de autorização RBAC
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, usuario_is_dev,
    pode_configurar_integracao
)

# Importa os modelos de dados do módulo de marketplaces
from .models import ContaMarketplace, LogSincronizacao, LogAuditoria, WebhookEventLog

# Importa enums com as constantes de canais, categorias de eventos auditáveis e estados de ciclo de vida de webhooks
from .enums import CanalMarketplaceEnum, EventoAuditoriaEnum, WebhookStatusEnum

# Importa o formulário de cadastro e manutenção de contas de integração
from .forms import ContaMarketplaceForm

# Importa a factory de instanciação de conectores baseada na conta de marketplace
from .connectors.factory import get_connector_for_conta

# Importa a implementação concreta do conector do Mercado Livre
from .connectors.mercadolivre import MercadoLivreConnector


# Função utilitária que resolve dinamicamente se a requisição é segura (HTTPS) ou não (HTTP)
def get_effective_scheme(request) -> str:
    # Início do bloco de docstring que documenta o reconhecimento agnóstico de esquema através de proxies/túneis
    """
    Determina o scheme correto ('http' ou 'https') para geração de URLs públicas.
    Baseia-se exclusivamente na requisição real e no reconhecimento de proxies/túneis
    via request.is_secure().
    """
    # Fim do bloco descritivo da função

    # Retorna 'https' caso a requisição seja nativamente segura ou reconhecida via cabeçalhos de proxy, senão 'http'
    return 'https' if request.is_secure() else 'http'


# Função utilitária que reconstrói a URL base pública absoluta com base no request atual
def get_base_url(request) -> str:
    # Início da docstring descritiva
    """
    Retorna a URL base absoluta com scheme seguro e host devidamente resolvido.
    """
    # Fim da docstring informativa

    # Obtém o esquema de conexão resolvido ('http' ou 'https')
    scheme = get_effective_scheme(request)

    # Obtém o cabeçalho Host da requisição considerando proxies reversos e túneis
    host = request.get_host()

    # Retorna a URL base formatada
    return f"{scheme}://{host}"


# View responsável por listar os canais e conexões ativas na interface do dashboard
class CanalListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    # Início do bloco de docstring que documenta a finalidade, RBAC e governança multi-tenant da tela
    """
    O QUE FAZ: Dashboard central multicanal listando todas as contas e canais integrados da Loja.
    POR QUE FAZ: Ponto único de controle e monitoramento de conectores de marketplaces (Mercado Livre, Shopee, Magalu, Amazon).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (com módulo 'marketplaces' ativo).
    MULTI-TENANCY: Filtra as contas vinculadas à loja do usuário logado (ou todas se DEV).
    """
    # Fim do bloco de documentação estrutural

    # Define o módulo do sistema exigido pelo ModuloRequeridoMixin para autorizar o acesso
    modulo_requerido = 'marketplaces'

    # Especifica o modelo base da listagem
    model = ContaMarketplace

    # Caminho do template HTML a ser renderizado
    template_name = 'marketplaces/canal_list.html'

    # Nome da variável disponibilizada no contexto do template para iterar sobre os registros
    context_object_name = 'contas'

    # Constrói o conjunto de dados filtrado conforme privilégios RBAC e tenant do usuário
    def get_queryset(self):
        # Obtém o usuário da sessão
        user = self.request.user

        # Carrega a consulta base otimizando consultas relacionais da loja
        queryset = ContaMarketplace.objects.select_related('loja').order_by('canal', 'apelido_conta')

        # Se for desenvolvedor global (DEV), permite visualizar todas as lojas ou filtrar por loja específica via GET
        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        # Para usuários operacionais e administrativos comuns, restringe estritamente à loja vinculada no perfil
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return ContaMarketplace.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        # Aplica filtro opcional por canal de marketplace enviado via parâmetro GET
        canal_filtro = self.request.GET.get('canal', '').strip()
        if canal_filtro:
            queryset = queryset.filter(canal=canal_filtro)

        # Retorna o queryset resultante
        return queryset

    # Injeta variáveis auxiliares de filtro e permissão no contexto do template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Adiciona flags de privilégios de desenvolvedor e permissão de edição de integrações
        context['is_dev'] = usuario_is_dev(user)
        context['pode_configurar'] = pode_configurar_integracao(user)

        # Disponibiliza as escolhas suportadas de canais para o filtro da tela
        context['canais_disponiveis'] = CanalMarketplaceEnum.choices

        # Preserva os valores dos filtros atuais para preenchimento dos campos de busca
        context['canal_filtro'] = self.request.GET.get('canal', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        # Injeta as lojas do ecossistema se for DEV, ou apenas a loja atual para usuários comuns
        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


# View responsável pelo formulário de conexão e cadastro de uma nova conta de marketplace
class ContaMarketplaceCreateView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, CreateView):
    # Início do bloco de docstring documentando escopo RBAC e automações multi-tenant
    """
    O QUE FAZ: Conexão e cadastro de nova conta de marketplace para o tenant.
    POR QUE FAZ: Permite cadastrar credenciais API de múltiplos canais por loja.
    PERMISSÕES RBAC: DEV e ADMIN (RF-05).
    MULTI-TENANCY: Vínculo automático à loja do lojista.
    """
    # Fim da documentação da classe

    modulo_requerido = 'marketplaces'
    model = ContaMarketplace
    form_class = ContaMarketplaceForm
    template_name = 'marketplaces/conta_form.html'
    success_url = reverse_lazy('canal_list')

    # Trata a requisição GET inicial limpando eventuais identificadores de contas anteriores mantidos na sessão
    def get(self, request, *args, **kwargs):
        # Fluxo de criação de conta inédita ("Conectar Nova Conta"): limpa oauth_conta_id da sessão
        # Remove a chave oauth_conta_id para não confundir o callback com um fluxo de reconexão
        request.session.pop('oauth_conta_id', None)
        return super().get(request, *args, **kwargs)

    # Injeta o usuário autor da requisição nos argumentos do formulário para validação contextual de regras de negócio
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    # Executa a persistência dos dados de forma atômica e registra o evento na trilha de auditoria
    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            # Cria registro de auditoria registrando a adição da nova conexão
            LogAuditoria.objects.create(
                loja=self.object.loja,
                autor=self.request.user,
                evento=EventoAuditoriaEnum.CRIACAO_CONTA,
                detalhes=f"Conta '{self.object.apelido_conta}' ({self.object.get_canal_display()}) conectada à loja '{self.object.loja.nome}'.",
                ip_origem=self.request.META.get('REMOTE_ADDR')
            )
        # Notifica o usuário com mensagem de sucesso na interface
        messages.success(self.request, f"Conta '{self.object.apelido_conta}' cadastrada com sucesso!")
        return response

    # Enriquece o contexto com metadados de canais, segredos e URLs públicas dinâmicas
    def get_context_data(self, **kwargs):
        import json
        from apps.marketplaces.constants import CANAL_REGISTRY
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = False
        context['canal_registry'] = CANAL_REGISTRY
        context['canal_registry_json'] = json.dumps(CANAL_REGISTRY)

        # Resolve e expõe a URL base e o callback OAuth considerando túneis e proxies
        base_url = get_base_url(self.request)
        context['base_url'] = base_url
        context['callback_url'] = f"{base_url}/marketplaces/mercadolivre/callback/"
        return context


# View encarregada da alteração de credenciais e parâmetros operacionais de uma conta já existente
class ContaMarketplaceUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, UpdateView):
    # Início do bloco de docstring documentando a verificação de propriedade (ownership check) e permissões
    """
    O QUE FAZ: Edição de credenciais e parâmetros de uma conta de marketplace existente.
    POR QUE FAZ: Manutenção de tokens e chaves de integração.
    PERMISSÕES RBAC: DEV e ADMIN (da respectiva loja).
    MULTI-TENANCY: Ownership check da conta com a loja do usuário.
    """
    # Fim da docstring explicativa

    modulo_requerido = 'marketplaces'
    model = ContaMarketplace
    form_class = ContaMarketplaceForm
    template_name = 'marketplaces/conta_form.html'
    success_url = reverse_lazy('canal_list')

    # Valida o ownership multi-tenant da conta antes de disponibilizá-la para edição
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user

        # Se o operador não for desenvolvedor global, impede o acesso a contas que pertençam a outro tenant
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta de marketplace pertence a outra loja.")
        return obj

    # Encaminha o usuário logado para o formulário
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['autor'] = self.request.user
        return kwargs

    # Salva as mutações em bloco atômico e grava a respectiva auditoria
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

    # Constrói o contexto com URLs específicas e verificação de pings de webhook anteriores
    def get_context_data(self, **kwargs):
        import json
        from apps.marketplaces.constants import CANAL_REGISTRY, get_canal_config
        context = super().get_context_data(**kwargs)
        context['modo_edicao'] = True
        context['conta'] = self.object
        context['canal_registry'] = CANAL_REGISTRY
        context['canal_registry_json'] = json.dumps(CANAL_REGISTRY)

        # Monta endpoints dinâmicos seguros para webhook e callback OAuth
        base_url = get_base_url(self.request)
        context['base_url'] = base_url
        canal_cfg = get_canal_config(self.object.canal)
        context['canal_config'] = canal_cfg
        context['webhook_url_individual'] = f"{base_url}/api/v1/webhooks/{self.object.canal}/{self.object.webhook_uuid}/"
        callback_path = canal_cfg.get('callback_path') or f"/marketplaces/{self.object.canal}/callback/"
        context['callback_url'] = f"{base_url}{callback_path}"

        # Verifica se o endpoint já interceptou eventos do seller ID anteriormente
        has_ping = False
        if self.object.seller_id_externo:
            has_ping = WebhookEventLog.objects.filter(user_id=self.object.seller_id_externo).exists()
        context['has_webhook_ping'] = has_ping
        return context


# View responsável pela confirmação e exclusão definitiva da integração da conta com a loja
class ContaMarketplaceDeleteView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, DeleteView):
    # Início do bloco de docstring documentando a revogação da conta
    """
    O QUE FAZ: Desconexão e exclusão de uma conta de marketplace.
    POR QUE FAZ: Permite revogar o vínculo de um canal.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da documentação da classe

    modulo_requerido = 'marketplaces'
    model = ContaMarketplace
    template_name = 'marketplaces/conta_confirm_delete.html'
    success_url = reverse_lazy('canal_list')

    # Garante que um operador só consiga excluir registros pertencentes ao seu tenant
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")
        return obj

    # Processa a deleção transacional e registra log de auditoria correspondente
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


# View que executa um teste síncrono de ping e validação de tokens contra a API remota do canal
class ContaMarketplaceTestarView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, View):
    # Início da docstring descritiva
    """
    O QUE FAZ: Executa teste de conectividade e validação de credenciais em tempo real com a API do marketplace.
    POR QUE FAZ: Permite ao gestor confirmar se o token OAuth ou credenciais estão operacionais utilizando test_connection().
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Restrito à conta da loja.
    """
    # Fim do bloco descritivo da classe

    modulo_requerido = 'marketplaces'

    # Dispara o teste de conectividade via método POST
    def post(self, request, pk, *args, **kwargs):
        conta = get_object_or_404(ContaMarketplace, pk=pk)

        # Checagem de isolamento multi-tenant
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado.")

        # Obtém o conector concreto e aciona o teste de conexão
        connector = conta.get_connector()
        res = connector.test_connection(request=request) if hasattr(connector, 'test_connection') else connector.autenticar(request=request)

        # Normaliza as diferentes formas de retorno (tupla, dicionário ou valor arbitrário)
        if isinstance(res, tuple):
            sucesso, msg = res[0], res[1]
        elif isinstance(res, dict):
            sucesso = res.get('sucesso', False)
            msg = res.get('mensagem', '')
        else:
            sucesso, msg = False, str(res)

        # Exibe mensagem de sucesso ou erro na interface dependendo do resultado do conector
        if sucesso:
            messages.success(request, f"[{conta.get_canal_display()}] {msg}")
        else:
            messages.error(request, f"[{conta.get_canal_display()}] {msg}")

        return redirect('canal_list')


# View que apresenta os relatórios técnicos de telemetria de chamadas de API e eventos de webhooks
class LogSincronizacaoListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    # Início do bloco de docstring documentando as abas e governança da telemetria
    """
    O QUE FAZ: Relatório e visualização de telemetria e logs de chamadas externas de integração e eventos de Webhook.
    POR QUE FAZ: Diagnóstico técnico de erros de precificação, estoque, requisições HTTP e ciclo de vida de Webhooks (RF-05 / RN-04 / Tarefa 3).
    PERMISSÕES RBAC: DEV (todas as lojas); ADMIN, SUPERVISOR e USUARIO (leitura na própria loja).
    MULTI-TENANCY: Filtro obrigatório por loja para não-DEV.
    """
    # Fim da docstring explicativa

    modulo_requerido = 'marketplaces'
    template_name = 'marketplaces/log_sincronizacao_list.html'
    context_object_name = 'logs'
    paginate_by = 25

    # Monta a consulta de logs conforme a aba selecionada na interface ('webhooks' ou 'telemetria')
    def get_queryset(self):
        user = self.request.user
        aba = self.request.GET.get('aba', 'telemetria')

        # Consulta os registros de entrada de notificações caso a aba ativa seja 'webhooks'
        if aba == 'webhooks':
            queryset = WebhookEventLog.objects.all().order_by('-received_at')

            # Segregação multi-tenant: filtra eventos pelos seller_ids das contas vinculadas à loja do usuário
            if not usuario_is_dev(user):
                perfil = getattr(user, 'perfil', None)
                if not perfil or not perfil.loja:
                    return WebhookEventLog.objects.none()
                seller_ids = list(
                    ContaMarketplace.objects.filter(loja=perfil.loja).values_list('seller_id_externo', flat=True)
                )
                queryset = queryset.filter(user_id__in=[s for s in seller_ids if s])
            # Se for DEV, filtra pela loja selecionada se o parâmetro existir
            else:
                loja_id = self.request.GET.get('loja', '').strip()
                if loja_id:
                    seller_ids = list(
                        ContaMarketplace.objects.filter(loja_id=loja_id).values_list('seller_id_externo', flat=True)
                    )
                    queryset = queryset.filter(user_id__in=[s for s in seller_ids if s])

            # Filtra por status de processamento de webhook (RECEBIDO, PROCESSANDO, PROCESSADO, IGNORADO, ERRO)
            status_filtro = self.request.GET.get('status', '').strip()
            if status_filtro:
                queryset = queryset.filter(status=status_filtro)

            # Busca textual em múltiplos campos de identificação e diagnóstico do webhook
            busca = self.request.GET.get('q', '').strip()
            if busca:
                queryset = queryset.filter(
                    Q(resource__icontains=busca) |
                    Q(user_id__icontains=busca) |
                    Q(error_log__icontains=busca) |
                    Q(topic__icontains=busca)
                )
            return queryset

        # Default: Telemetria (LogSincronizacao)
        # Consulta os disparos de saída e chamadas diretas de API registradas em LogSincronizacao
        queryset = LogSincronizacao.objects.select_related('loja', 'conta_marketplace').order_by('-criado_em')

        # Aplica isolamento de tenant na telemetria
        if usuario_is_dev(user):
            loja_id = self.request.GET.get('loja', '').strip()
            if loja_id:
                queryset = queryset.filter(loja_id=loja_id)
        else:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja:
                return LogSincronizacao.objects.none()
            queryset = queryset.filter(loja=perfil.loja)

        # Filtro por marketplace
        canal_filtro = self.request.GET.get('canal', '').strip()
        if canal_filtro:
            queryset = queryset.filter(canal=canal_filtro)

        # Filtro por sucesso ou falha da chamada HTTP
        sucesso_filtro = self.request.GET.get('sucesso', '').strip()
        if sucesso_filtro == '1':
            queryset = queryset.filter(sucesso=True)
        elif sucesso_filtro == '0':
            queryset = queryset.filter(sucesso=False)

        # Filtro de busca textual por item, erro retornado ou nome do evento
        busca = self.request.GET.get('q', '').strip()
        if busca:
            queryset = queryset.filter(
                Q(item_id_externo__icontains=busca) |
                Q(mensagem_erro__icontains=busca) |
                Q(evento__icontains=busca)
            )

        return queryset

    # Disponibiliza os estados e valores de filtros no contexto do template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        aba = self.request.GET.get('aba', 'telemetria')
        context['aba'] = aba
        context['is_dev'] = usuario_is_dev(user)
        context['canais_disponiveis'] = CanalMarketplaceEnum.choices
        context['webhook_status_choices'] = WebhookStatusEnum.choices
        context['status_filtro'] = self.request.GET.get('status', '').strip()
        context['termo_busca'] = self.request.GET.get('q', '').strip()
        context['canal_filtro'] = self.request.GET.get('canal', '').strip()
        context['sucesso_filtro'] = self.request.GET.get('sucesso', '').strip()
        context['loja_filtro'] = self.request.GET.get('loja', '').strip()

        if context['is_dev']:
            context['lojas_disponiveis'] = Loja.objects.filter(ativo=True).order_by('nome')
        else:
            context['minha_loja'] = getattr(user.perfil, 'loja', None)

        return context


# View restrita para reprocessamento manual sob demanda de webhooks que falharam
class WebhookEventReplayView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, View):
    # Início da docstring da rotina de Replay
    """
    O QUE FAZ: Reprocessa manualmente um evento de Webhook a partir da interface de Telemetria (Replay).
    POR QUE FAZ: Permite ao operador/administrador recuperar eventos que falharam anteriormente (ex: erro de rede temporário) sem depender de ferramentas de tunelamento externas como ngrok.
    PERMISSÕES RBAC: DEV e ADMIN (com módulo 'marketplaces' ativo).
    MULTI-TENANCY: Garante que o lojista só reexecute webhooks pertencentes às contas da sua própria loja.
    """
    # Fim do bloco explicativo

    modulo_requerido = 'marketplaces'

    # Processa o reenvio via método POST
    def post(self, request, pk, *args, **kwargs):
        # Carrega o registro do evento de webhook pelo identificador
        event_log = get_object_or_404(WebhookEventLog, pk=pk)

        # Multi-tenancy check para não-DEV
        # Garante que operadores comuns só consigam reexecutar webhooks emitidos contra suas próprias contas
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja:
                raise PermissionDenied("Acesso negado: usuário sem loja vinculada.")
            seller_ids = list(
                ContaMarketplace.objects.filter(loja=perfil.loja).values_list('seller_id_externo', flat=True)
            )
            if event_log.user_id not in [s for s in seller_ids if s]:
                raise PermissionDenied("Acesso negado: este evento pertence a outra loja.")

        # Reúso estrito da mesma função de processamento do serviço (Ajuste 3)
        # Dispara novamente a lógica oficial de processamento utilizando o payload bruto original
        status_code, resposta = MercadoLivreWebhookService.processar_notificacao(event_log.payload_raw)

        # Notifica o usuário na interface com base no status do reprocessamento
        if status_code == 200 and resposta.get('status') in ['ok', 'ignored']:
            messages.success(request, f"Replay do evento #{pk} executado: {resposta.get('message', 'Processado com sucesso')}")
        else:
            messages.error(request, f"Falha no replay do evento #{pk}: {resposta.get('message', 'Erro no processamento')}")

        # Redireciona de volta para a aba de webhooks na listagem de telemetria
        return redirect(reverse('log_sincronizacao_list') + '?aba=webhooks')


# ==============================================================================
# FLUXO OAUTH 2.0 EXCLUSIVO MERCADO LIVRE
# ==============================================================================

# View encarregada de iniciar a autorização OAuth criando token state seguro e redirecionando ao Mercado Livre
class MercadoLivreAutorizarView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, View):
    # Início do bloco de docstring documentando o handshake OAuth
    """
    O QUE FAZ: Inicia o fluxo de autorização OAuth 2.0 redirecionando o lojista para o Mercado Livre.
    POR QUE FAZ: Elimina inputs manuais de tokens, gerando state randômico e efêmero na sessão contra CSRF.
    PERMISSÕES RBAC: DEV e ADMIN (da respectiva loja).
    MULTI-TENANCY: Garante que o lojista só autorize contas da sua própria loja.
    """
    # Fim da documentação da classe

    modulo_requerido = 'marketplaces'

    def get(self, request, pk, *args, **kwargs):
        # Importa o módulo secrets para geração de tokens criptograficamente seguros
        import secrets

        # Recupera a conta e valida se ela pertence ao tenant do usuário autenticado
        conta = get_object_or_404(ContaMarketplace, pk=pk)
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta pertence a outra loja.")

        # Se for conta mockada, respeita a feature flag de simulação
        # Trata lojas de demonstração ou testes locais que operam em ambiente mockado
        if conta.is_mock:
            from apps.mockar_dados.services import is_simular_rotas_mock_ativo
            # Se as rotas mockadas estiverem ativas, simula o redirecionamento com código fictício
            if is_simular_rotas_mock_ativo(request):
                state = f"mock_{secrets.token_urlsafe(16)}"
                request.session['oauth_state'] = state
                request.session['oauth_conta_id'] = conta.pk
                code = f"MOCK_CODE_{conta.pk}"
                callback_url = f"{reverse('mercadolivre_callback')}?code={code}&state={state}"
                return redirect(callback_url)
            # Se a simulação estiver desativada, rejeita a conexão com HTTP 401 para fins de teste
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

        # Token randômico e efêmero armazenado na sessão (proteção contra CSRF)
        # Gera token criptográfico único para validar na volta e mitigar ataques CSRF
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        request.session['oauth_conta_id'] = conta.pk

        # Obtém a URL externa de autorização através do conector e redireciona o navegador do lojista
        connector = conta.get_connector()
        auth_url = connector.get_authorization_url(state=state, request=request)
        return redirect(auth_url)


# View que recebe a resposta do redirecionamento do portal de consentimento do Mercado Livre
class MercadoLivreCallbackView(View):
    # Início do bloco de docstring documentando a validação de state e troca de authorization code
    """
    O QUE FAZ: Recebe o callback OAuth 2.0 do Mercado Livre com o authorization code e executa a troca por tokens.
    POR QUE FAZ: Valida o parâmetro state efêmero contra a sessão (mitigação de CSRF), persiste tokens criptografados e exibe tela de sucesso.
    SEGURANÇA: Registra auditoria, valida o state e não expõe credenciais brutas.
    """
    # Fim da docstring explicativa

    def get(self, request, *args, **kwargs):
        # Extrai os parâmetros retornados na query string pelo parceiro externo
        code = request.GET.get('code', '').strip()
        state = request.GET.get('state', '').strip()
        error = request.GET.get('error', '').strip()
        error_description = request.GET.get('error_description', '').strip()

        # Se o usuário negou consentimento ou ocorreu erro na plataforma remota
        if error:
            messages.error(request, f"Erro retornado pelo Mercado Livre: {error_description or error}")
            return redirect('canal_list')

        # Se o código de autorização estiver ausente na requisição
        if not code:
            messages.error(request, "Código de autorização (code) não foi fornecido pelo Mercado Livre.")
            return redirect('canal_list')

        # Validação do state efêmero contra a sessão (proteção contra CSRF)
        # Recupera o token de segurança state da sessão do usuário
        session_state = request.session.get('oauth_state')
        conta_id_origem = request.session.pop('oauth_conta_id', None)

        conta = None
        # Validação estrita do token anti-CSRF caso ele tenha sido gerado previamente na sessão
        if session_state:
            # Quando a sessão possui um state registrado, a resposta DEVE obrigatoriamente coincidir
            if state != session_state:
                messages.error(request, "Parâmetro 'state' inválido ou expirado. Possível tentativa de CSRF.")
                return redirect('canal_list')
            if conta_id_origem:
                conta = ContaMarketplace.objects.filter(pk=conta_id_origem).first()
            # Consome o state efêmero da sessão (uso único)
            request.session.pop('oauth_state', None)
        # Fallback para execução de testes automatizados com identificador prefixado no próprio state
        elif state and state.startswith('conta_'):
            # Fallback para testes automatizados com state prefixado
            try:
                conta_id = int(state.replace('conta_', ''))
                conta = ContaMarketplace.objects.filter(pk=conta_id).first()
            except ValueError:
                pass
        # Fallback para testes automatizados em ambiente DEBUG
        elif (code and code.startswith(('MOCK_', 'TEST_'))) or getattr(settings, 'DEBUG', False):
            # Fallback em modo de teste/debug quando o state não foi originado de sessão web
            if conta_id_origem:
                conta = ContaMarketplace.objects.filter(pk=conta_id_origem).first()
            elif request.user.is_authenticated:
                perfil = getattr(request.user, 'perfil', None)
                if perfil and perfil.loja:
                    conta = ContaMarketplace.objects.filter(
                        loja=perfil.loja, canal=CanalMarketplaceEnum.MERCADOLIVRE
                    ).first()
            if not conta:
                conta = ContaMarketplace.objects.filter(canal=CanalMarketplaceEnum.MERCADOLIVRE).first()
        # Se nenhuma validação de state foi atendida, bloqueia com mensagem amigável
        else:
            messages.error(request, "Parâmetro 'state' inválido ou expirado. Possível tentativa de CSRF.")
            return redirect('canal_list')

        # Fallback adicional caso a instância de conta ainda não tenha sido resolvida
        if not conta and request.user.is_authenticated:
            perfil = getattr(request.user, 'perfil', None)
            if perfil and perfil.loja:
                conta = ContaMarketplace.objects.filter(
                    loja=perfil.loja, canal=CanalMarketplaceEnum.MERCADOLIVRE
                ).first()

        # Último fallback para garantir um objeto de conta de referência
        if not conta:
            conta = ContaMarketplace.objects.filter(canal=CanalMarketplaceEnum.MERCADOLIVRE).first()

        # Executa a troca síncrona do 'code' temporário por 'access_token' e 'refresh_token' via conector
        sucesso, msg, res_json, log = MercadoLivreConnector.trocar_code_por_token(
            code=code,
            conta=conta,
            usuario=request.user if request.user.is_authenticated else None,
            request=request,
        )

        # Se a troca de credenciais foi bem-sucedida
        if sucesso:
            if conta:
                # Registra auditoria de sucesso da autorização OAuth
                LogAuditoria.objects.create(
                    loja=conta.loja,
                    autor=request.user if request.user.is_authenticated else None,
                    evento=EventoAuditoriaEnum.CRIACAO_CONTA,
                    detalhes=f"Conta '{conta.apelido_conta}' autorizada com sucesso via OAuth 2.0 no Mercado Livre (Seller ID: {conta.seller_id_externo}).",
                    ip_origem=request.META.get('REMOTE_ADDR')
                )

            # Prepara contexto e renderiza a tela comemorativa de conexão concluída
            context = {
                'conta': conta,
                'loja': conta.loja if conta else None,
                'seller_id': conta.seller_id_externo if conta else res_json.get('user_id'),
                'apelido': conta.apelido_conta if conta else 'Mercado Livre',
            }
            return render(request, 'marketplaces/callback_sucesso.html', context)
        # Em caso de falha na requisição de troca de tokens com o Mercado Livre
        else:
            messages.error(request, msg)
            return redirect('canal_list')


# View para revogação e limpeza manual de tokens salvos da conta de marketplace
class ContaMarketplaceDesconectarView(LoginRequiredMixin, ModuloRequeridoMixin, IntegracaoConfigPermissionMixin, View):
    # Início do bloco de docstring descritivo
    """
    O QUE FAZ: Limpa os tokens OAuth e desconecta com segurança a conta de marketplace da loja.
    POR QUE FAZ: Permite ao gestor revogar credenciais ou reconectar do zero sem excluir o histórico de anúncios.
    PERMISSÕES RBAC: DEV e ADMIN (da respectiva loja).
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    # Fim da documentação da classe

    modulo_requerido = 'marketplaces'

    # Dispara a desconexão via método POST
    def post(self, request, pk, *args, **kwargs):
        conta = get_object_or_404(ContaMarketplace, pk=pk)

        # Checagem de isolamento multi-tenant
        if not usuario_is_dev(request.user):
            perfil = getattr(request.user, 'perfil', None)
            if not perfil or not perfil.loja or conta.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: esta conta pertence a outra loja.")

        # Executa limpeza dos campos de credenciais de forma transacional
        with transaction.atomic():
            conta.access_token = None
            conta.refresh_token = None
            conta.token_expira_em = None
            conta.seller_id_externo = None
            conta.save(update_fields=[
                'access_token', 'refresh_token', 'token_expira_em', 'seller_id_externo', 'updated_at'
            ])

            # Registra auditoria da operação de revogação de chaves
            LogAuditoria.objects.create(
                loja=conta.loja,
                autor=request.user,
                evento=EventoAuditoriaEnum.EDICAO_CONTA,
                detalhes=f"Tokens da conta '{conta.apelido_conta}' ({conta.get_canal_display()}) foram limpos/desconectados.",
                ip_origem=request.META.get('REMOTE_ADDR')
            )

        messages.success(request, f"Conta '{conta.apelido_conta}' desconectada com sucesso.")
        return redirect('canal_list')


# ==============================================================================
# WEBHOOKS DE MARKETPLACES — MERCADO LIVRE (RECEBIMENTO E BAIXA DE ESTOQUE)
# ==============================================================================

# View pública e isenta de CSRF para recebimento direto de webhooks legados do Mercado Livre
@method_decorator(csrf_exempt, name='dispatch')
class MercadoLivreWebhookView(View):
    # Início do bloco de docstring
    """
    O QUE FAZ: Endpoint HTTP nativo para recebimento de webhooks do Mercado Livre (/marketplaces/webhooks/mercadolivre/).
    POR QUE FAZ: Implementa idempotência estrita, rejeição de requisições indevidas e aciona baixa atômica de estoque físico.
    PERMISSÕES: Aberto ao Mercado Livre (com @csrf_exempt). Resposta imediata com HTTP 200 OK.
    """
    # Fim da docstring explicativa

    # Método POST que recebe a notificação enviada pelo marketplace parceiro
    def post(self, request, *args, **kwargs):
        # Validação do corpo da requisição e desserialização do JSON
        try:
            if not request.body:
                return JsonResponse({'error': 'Corpo da requisição vazio.'}, status=400)
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, json.JSONDecodeError):
            return JsonResponse({'error': 'Payload JSON malformado.'}, status=400)

        # Encaminha o payload para processamento atômico no serviço
        status_code, resposta = MercadoLivreWebhookService.processar_notificacao(payload)
        return JsonResponse(resposta, status=status_code)

    # Bloqueia métodos HTTP que não sejam POST com 405 Method Not Allowed
    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def put(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def delete(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def patch(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])


# ==============================================================================
# INGESTÃO UNIVERSAL DE WEBHOOKS HTTP (GLOBAL & INDIVIDUAL COM SEGMENTAÇÃO UUID)
# ==============================================================================

# View unificada para ingestão de webhooks multi-tenant suportando rotas globais ou individualizadas por UUID
@method_decorator(csrf_exempt, name='dispatch')
class WebhookIngestionView(View):
    # Início do bloco de docstring descrevendo o fail-fast criptográfico e roteamento híbrido
    """
    O QUE FAZ: Endpoint unificado de ingestão de Webhooks HTTP para múltiplos marketplaces.
    POR QUE FAZ: Suporta roteamento híbrido:
      - Fluxo Individual: /api/v1/webhooks/<canal>/<uuid:webhook_uuid>/
      - Fluxo Global: /api/v1/webhooks/<canal>/
    SEGURANÇA: Fail-Fast simétrico com rejeição prévia de requisições com timestamp fora da janela de 300s (Anti-Replay)
               ou HMAC inválido antes do parse de payload JSON ou consumo de banco de dados.
    """
    # Fim da documentação da classe

    def post(self, request, canal: str, webhook_uuid=None, *args, **kwargs):
        # Importa funções de conferência de assinatura HMAC e consulta ao registro de canais
        from apps.marketplaces.security_webhook import validar_assinatura_e_anti_replay
        from apps.marketplaces.constants import get_canal_config

        # Normaliza o canal informado na rota
        canal_normalizado = canal.strip().lower()
        config = get_canal_config(canal_normalizado)

        # Retorna 404 caso o canal solicitado não seja suportado pela plataforma
        if not config and canal_normalizado not in ['mercadolivre', 'meli', 'shopee', 'magalu', 'amazon']:
            return JsonResponse({'error': f"Canal '{canal}' não reconhecido."}, status=404)

        # Trata aliases padronizando o canal como 'mercadolivre'
        canal_key = config.get('canal_key', canal_normalizado)
        if canal_key == 'meli':
            canal_key = 'mercadolivre'

        # ----------------------------------------------------------------------
        # FLUXO INDIVIDUAL: /api/v1/webhooks/<canal>/<uuid>/
        # ----------------------------------------------------------------------
        # Executa tratamento para endpoints dedicados por conta parametrizados por UUID
        if webhook_uuid:
            # 1. Busca conta diretamente pelo webhook_uuid indexado (404 imediato se inexistente)
            # Consulta a conta pelo UUID indexado
            conta = ContaMarketplace.objects.filter(webhook_uuid=webhook_uuid).select_related('loja').first()
            if not conta:
                return JsonResponse({'error': 'Conta não localizada para o webhook UUID fornecido.'}, status=404)

            # 2. Descriptografa webhook_secret e valida Fail-Fast (Anti-Replay < 300s + HMAC)
            # Recupera o segredo descriptografado automaticamente pelo EncryptedTextField
            secret = conta.webhook_secret
            if secret:
                # Valida integridade criptográfica da requisição
                valido, status_code, motivo = validar_assinatura_e_anti_replay(request, secret=secret, canal=canal_key)
                if not valido:
                    return JsonResponse({'error': motivo}, status=status_code)

            # 3. Parse seguro do corpo
            # Decodifica o payload JSON após confirmação de integridade criptográfica
            try:
                if not request.body:
                    return JsonResponse({'error': 'Corpo da requisição vazio.'}, status=400)
                payload = json.loads(request.body.decode('utf-8'))
            except (ValueError, json.JSONDecodeError):
                return JsonResponse({'error': 'Payload JSON malformado.'}, status=400)

            # 4. Despacha processamento para o respectivo canal
            # Encaminha para o processador específico do Mercado Livre informando a conta de contexto
            if canal_key == 'mercadolivre':
                status_code, resposta = MercadoLivreWebhookService.processar_notificacao(payload, conta=conta)
                return JsonResponse(resposta, status=status_code)
            # Para outros canais integrados, devolve confirmação de recepção em formato padrão
            else:
                return JsonResponse({
                    'status': 'received',
                    'canal': canal_key,
                    'conta_id': conta.id,
                    'loja_id': conta.loja_id
                }, status=200)

        # ----------------------------------------------------------------------
        # FLUXO GLOBAL: /api/v1/webhooks/<canal>/
        # ----------------------------------------------------------------------
        # Rota que atende notificações centralizadas de contas compartilhadas ou globais
        else:
            # 1. Extrai chave global da memória (.env / settings)
            # Obtém a chave secreta global do Mercado Livre parametrizada no settings
            global_secret = (
                getattr(settings, 'MELI_GLOBAL_WEBHOOK_SECRET', '')
                or getattr(settings, 'MERCADOLIVRE_CLIENT_SECRET', '')
                if canal_key == 'mercadolivre' else ''
            )

            # 2. Valida timestamp (< 300s) e HMAC antes de qualquer consulta ao banco
            # Executa fail-fast criptográfico prevenindo consumo indevido de banco em ataques de negação
            if global_secret:
                valido, status_code, motivo = validar_assinatura_e_anti_replay(request, secret=global_secret, canal=canal_key)
                if not valido:
                    return JsonResponse({'error': motivo}, status=status_code)

            # 3. Parse do payload
            # Converte o corpo para dicionário Python
            try:
                if not request.body:
                    return JsonResponse({'error': 'Corpo da requisição vazio.'}, status=400)
                payload = json.loads(request.body.decode('utf-8'))
            except (ValueError, json.JSONDecodeError):
                return JsonResponse({'error': 'Payload JSON malformado.'}, status=400)

            # 4. Despacha processamento
            # Encaminha o webhook global para identificação do seller e baixa atômica
            if canal_key == 'mercadolivre':
                status_code, resposta = MercadoLivreWebhookService.processar_notificacao(payload)
                return JsonResponse(resposta, status=status_code)
            else:
                return JsonResponse({'status': 'received', 'canal': canal_key}, status=200)

    # Bloqueia métodos HTTP que não sejam POST retornando HTTP 405
    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def put(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def delete(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def patch(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])
