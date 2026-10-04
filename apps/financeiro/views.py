# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo json para decodificação de requisições AJAX com payload estruturado
import json

# Importa a classe Decimal para manipulação de porcentagens e valores monetários com precisão exata
from decimal import Decimal

# Importa atalhos do Django para renderização de páginas HTML e recuperação de instâncias com disparo de 404
from django.shortcuts import render, get_object_or_404

# Importa as classes genéricas de visualização baseadas em classe (CBVs)
from django.views.generic import TemplateView, View, ListView, UpdateView, CreateView

# Importa o mixin nativo do Django que exige que o usuário esteja devidamente autenticado na sessão
from django.contrib.auth.mixins import LoginRequiredMixin

# Importa utilitários de mensagens, redirecionamento e permissões do Django
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied

# Importa a entidade Loja representativa do tenant no particionamento de dados
from apps.tenancy.models import Loja

# Importa os mixins e funções de controle de acesso (RBAC) e verificação contratual do módulo financeiro
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, FinancialAccessMixin, usuario_is_dev, pode_acessar_inteligencia_financeira
)

# Importa o modelo de Produto físico do catálogo para obtenção de preços e custos diretos
from apps.catalogo.models import Produto

# Importa as opções tarifárias de canais de venda e entidades de taxas e tarifas
from .models import MARKETPLACE_CHOICES, ConfiguracaoTaxasLoja, ParametroCanalMarketplace
from .forms import ConfiguracaoTaxasLojaForm, ParametroCanalMarketplaceForm

# Importa o mecanismo central de controle de acesso RBAC e salvaguardas
from apps.accounts.rbac import (
    tem_funcionalidade,
    RBACFuncionalidadeRequiredMixin,
    FUNC_FINANCEIRO_TAXAS_EDITAR,
    FUNC_FINANCEIRO_PARAMETROS_CANAIS,
)

# Importa o modelo e enum de auditoria para rastreabilidade de mutações
from apps.marketplaces.models import LogAuditoria
from apps.marketplaces.enums import EventoAuditoriaEnum

# Importa a camada de serviço responsável pelo processamento matemático do motor financeiro
from .services import SimuladorPromocionalService


# Classe baseada em View que atua como interface gráfica e endpoint AJAX de inteligência financeira
class SimuladorPromocionalView(LoginRequiredMixin, ModuloRequeridoMixin, FinancialAccessMixin, View):
    # Início do bloco de docstring que detalha as funções do simulador, governança RBAC e isolamento multi-tenant
    """
    O QUE FAZ: Interface interativa e endpoint AJAX para simulação financeira e formação de preço promocional.
    POR QUE FAZ: Fornece ao lojista análise de viabilidade, margem líquida em tempo real e volume de compensação (Q_meta) antes de aplicar descontos.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (FinancialAccessMixin / RN-09). USUARIO é bloqueado com 403 Forbidden.
    MULTI-TENANCY: Filtra os produtos da loja do usuário e utiliza os parâmetros fiscais do tenant.
    """
    # Fim do bloco de documentação estrutural da visualização

    # Define o módulo contratual exigido para acesso às rotinas financeiras
    modulo_requerido = 'financeiro'

    # Especifica o arquivo de template HTML que renderiza a interface interativa do simulador
    template_name = 'financeiro/simulador_promocional.html'

    # Método GET encarregado de carregar a tela, os produtos elegíveis e os canais de marketplace disponíveis
    def get(self, request, *args, **kwargs):
        # Obtém a referência do usuário autenticado na requisição
        user = request.user

        # Verifica se o usuário autenticado possui privilégio de desenvolvedor global (DEV)
        is_dev = usuario_is_dev(user)

        # Se for desenvolvedor, permite visualizar e alternar produtos de qualquer tenant cadastrado
        if is_dev:
            # Lista todas as lojas ativas cadastradas no sistema ordenadas alfabeticamente
            lojas = Loja.objects.filter(ativo=True).order_by('nome')
            # Recupera eventual filtro de loja informado via parâmetro GET
            loja_selecionada_id = request.GET.get('loja', '')
            # Se uma loja específica foi selecionada pelo desenvolvedor, filtra os produtos ativos dela
            if loja_selecionada_id:
                produtos = Produto.objects.filter(loja_id=loja_selecionada_id, status='ATIVO').order_by('nome')
            # Caso contrário, exibe os produtos ativos de todas as lojas
            else:
                produtos = Produto.objects.filter(status='ATIVO').order_by('nome')
        # Regra para operadores e gestores comuns (ADMIN e SUPERVISOR) vinculados a um tenant específico
        else:
            # Obtém o perfil estendido do usuário logado
            perfil = getattr(user, 'perfil', None)
            # Restringe o escopo de lojas exclusivamente à própria loja do usuário
            lojas = [perfil.loja] if perfil and perfil.loja else []
            # Filtra estritamente os produtos ativos pertencentes à loja do operador
            produtos = Produto.objects.filter(loja=perfil.loja, status='ATIVO').order_by('nome') if perfil and perfil.loja else []

        # Monta o dicionário de contexto repassado para o motor de templates
        context = {
            'is_dev': is_dev,
            'lojas': lojas,
            'produtos': produtos,
            'canais': MARKETPLACE_CHOICES,
        }

        # Renderiza a página HTML entregando o contexto estruturado
        return render(request, self.template_name, context)

    # Método POST responsável por processar o cálculo da simulação sob demanda e retornar a telemetria em JSON
    def post(self, request, *args, **kwargs):
        # Captura o usuário executor da requisição
        user = request.user

        # Bloco protegido para extração e decodificação dos dados enviados (JSON ou Form POST tradicional)
        try:
            # Se a requisição contiver cabeçalho indicando carga JSON (chamada AJAX moderna)
            if request.content_type == 'application/json':
                # Decodifica o corpo da requisição em UTF-8 e carrega no dicionário Python
                data = json.loads(request.body.decode('utf-8'))
            # Se for submissão via formulário convencional
            else:
                data = request.POST
        # Em caso de falha na decodificação do corpo JSON, adota o request.POST como fallback
        except Exception:
            data = request.POST

        # Extrai o identificador primário do produto selecionado
        produto_id = data.get('produto_id')

        # Extrai o canal de marketplace selecionado, adotando 'mercadolivre_classico' como padrão
        canal_nome = data.get('canal', 'mercadolivre_classico')

        # Converte o percentual de desconto informado para o tipo Decimal de alta precisão (padrão 10.0%)
        desconto_pct = Decimal(str(data.get('desconto_pct', '10.0')))

        # Converte o volume mensal base informado em número inteiro (padrão 100 unidades)
        volume_mensal = int(data.get('volume_mensal', 100))

        # Validação defensiva: se nenhum produto foi informado no payload, rejeita com HTTP 400 Bad Request
        if not produto_id:
            return JsonResponse({'erro': 'Selecione um produto para simular.'}, status=400)

        # Recupera o produto no catálogo pela chave primária ou interrompe com HTTP 404
        produto = get_object_or_404(Produto, pk=produto_id)

        # Ownership Check multi-tenant
        # Se não for usuário DEV global, valida se o produto selecionado pertence estritamente à mesma loja do usuário
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            # Se o usuário não tiver loja ou se o ID da loja do produto diferir da loja do perfil
            if not perfil or not perfil.loja or produto.loja_id != perfil.loja_id:
                # Bloqueia a execução disparando HTTP 403 Forbidden para impedir espionagem de custos entre concorrentes
                raise PermissionDenied("Acesso negado: o produto selecionado pertence a outra loja.")

        # Dispara o motor de inteligência financeira através da camada de serviço
        resultado = SimuladorPromocionalService.simular_impacto_promocional(
            produto=produto,
            canal_nome=canal_nome,
            percentual_desconto=desconto_pct,
            volume_estimado_mensal=volume_mensal
        )

        # Retorna o resultado completo da simulação (margens, elasticidade, status) em formato JSON
        return JsonResponse(resultado)


# ==============================================================================
# TAXAS DAS LOJAS (PARÂMETROS FISCAIS, CUSTOS FIXOS E MARGENS)
# ==============================================================================

class TaxasLojaListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Lista as configurações de taxas fiscais e margens das lojas.
    POR QUE FAZ: Desacopla a visualização de parâmetros fiscais do Django Admin para o Hub.
    PERMISSÕES RBAC: DEV e ADMIN (ou perfis com financeiro.taxas_editar / financeiro.simulador_acessar).
    MULTI-TENANCY: DEV pode ver todas as lojas; demais perfis veem apenas a própria loja.
    """
    modulo_requerido = 'financeiro'
    model = ConfiguracaoTaxasLoja
    template_name = 'financeiro/taxas_loja_list.html'
    context_object_name = 'taxas_list'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (usuario_is_dev(request.user) or
                tem_funcionalidade(request.user, FUNC_FINANCEIRO_TAXAS_EDITAR) or
                tem_funcionalidade(request.user, 'financeiro.simulador_acessar')):
            raise PermissionDenied("Acesso negado: seu perfil não possui permissão para visualizar as taxas das lojas.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if usuario_is_dev(user):
            # Garante que todas as lojas ativas possuam configuração de taxas criada
            for lj in Loja.objects.filter(ativo=True):
                ConfiguracaoTaxasLoja.objects.get_or_create(loja=lj)
            qs = ConfiguracaoTaxasLoja.objects.select_related('loja').all()
            loja_uuid = self.request.GET.get('loja')
            if loja_uuid:
                qs = qs.filter(loja__public_id=loja_uuid)
            return qs.order_by('loja__nome')
        else:
            perfil = getattr(user, 'perfil', None)
            if perfil and perfil.loja:
                ConfiguracaoTaxasLoja.objects.get_or_create(loja=perfil.loja)
                return ConfiguracaoTaxasLoja.objects.filter(loja=perfil.loja).select_related('loja')
            return ConfiguracaoTaxasLoja.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_dev = usuario_is_dev(user)
        context['is_dev'] = is_dev
        context['pode_editar'] = is_dev or tem_funcionalidade(user, FUNC_FINANCEIRO_TAXAS_EDITAR)
        if is_dev:
            context['lojas'] = Loja.objects.filter(ativo=True).order_by('nome')
            context['loja_selecionada'] = self.request.GET.get('loja', '')
        return context


class TaxasLojaUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, RBACFuncionalidadeRequiredMixin, UpdateView):
    """
    O QUE FAZ: Formulário de edição das taxas fiscais, custos e margens de uma Loja.
    POR QUE FAZ: Governança de precificação direta via interface com isolamento multi-tenant e auditoria.
    PERMISSÕES RBAC: Exclusivo Grupos 3 (ADMIN) e 4 (DEV) via guard 'financeiro.taxas_editar'.
    MULTI-TENANCY: Identificação pública por UUID (<uuid:public_id>) e restrição à própria loja para não-DEV.
    """
    modulo_requerido = 'financeiro'
    funcionalidade_requerida = FUNC_FINANCEIRO_TAXAS_EDITAR
    model = ConfiguracaoTaxasLoja
    form_class = ConfiguracaoTaxasLojaForm
    template_name = 'financeiro/taxas_loja_form.html'
    slug_field = 'public_id'
    slug_url_kwarg = 'public_id'
    success_url = reverse_lazy('taxas_loja_list')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: você não tem permissão para editar taxas de outra loja.")
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)
        # Registra auditoria da alteração
        ip_cliente = self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))
        if ip_cliente and ',' in ip_cliente:
            ip_cliente = ip_cliente.split(',')[0].strip()

        LogAuditoria.objects.create(
            loja=self.object.loja,
            autor=self.request.user,
            evento=EventoAuditoriaEnum.EDICAO_TAXAS_LOJA,
            detalhes=(
                f"Taxas da loja '{self.object.loja.nome}' atualizadas: "
                f"Imposto={self.object.aliquota_imposto * 100:.2f}%, "
                f"Embalagem=R$ {self.object.custo_embalagem_padrao}, "
                f"Margem Mínima={self.object.margem_minima_seguranca * 100:.2f}%, "
                f"Custos Fixos=R$ {self.object.custos_fixos_mensais}"
            ),
            ip_origem=ip_cliente
        )
        messages.success(self.request, f"Parâmetros fiscais da loja '{self.object.loja.nome}' atualizados com sucesso.")
        return response


# ==============================================================================
# PARÂMETROS DOS MARKETPLACES (TARIFAS, COMISSÕES E FRETE GRÁTIS POR CANAL)
# ==============================================================================

class ParametroCanalListView(LoginRequiredMixin, ModuloRequeridoMixin, ListView):
    """
    O QUE FAZ: Exibe tabela de parâmetros de comissões, pisos de frete grátis e tarifas por canal de marketplace.
    POR QUE FAZ: Centraliza a gestão de taxas comerciais por canal sem necessidade do Django Admin.
    PERMISSÕES RBAC: DEV e ADMIN (ou perfis com financeiro.parametros_canais / financeiro.taxas_editar / simulador).
    MULTI-TENANCY: Isolamento por Loja; DEV visualiza todos os canais e lojas.
    """
    modulo_requerido = 'financeiro'
    model = ParametroCanalMarketplace
    template_name = 'financeiro/parametro_canal_list.html'
    context_object_name = 'parametros'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (usuario_is_dev(request.user) or
                tem_funcionalidade(request.user, FUNC_FINANCEIRO_PARAMETROS_CANAIS) or
                tem_funcionalidade(request.user, FUNC_FINANCEIRO_TAXAS_EDITAR) or
                tem_funcionalidade(request.user, 'financeiro.simulador_acessar')):
            raise PermissionDenied("Acesso negado: seu perfil não possui permissão para visualizar parâmetros dos marketplaces.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if usuario_is_dev(user):
            qs = ParametroCanalMarketplace.objects.select_related('loja').all()
            loja_uuid = self.request.GET.get('loja')
            if loja_uuid:
                qs = qs.filter(loja__public_id=loja_uuid)
        else:
            perfil = getattr(user, 'perfil', None)
            if perfil and perfil.loja:
                qs = ParametroCanalMarketplace.objects.filter(loja=perfil.loja).select_related('loja')
            else:
                qs = ParametroCanalMarketplace.objects.none()

        canal = self.request.GET.get('canal')
        if canal:
            qs = qs.filter(marketplace=canal)

        return qs.order_by('loja__nome', 'marketplace')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_dev = usuario_is_dev(user)
        context['is_dev'] = is_dev
        context['pode_editar'] = (
            is_dev or
            tem_funcionalidade(user, FUNC_FINANCEIRO_PARAMETROS_CANAIS) or
            tem_funcionalidade(user, FUNC_FINANCEIRO_TAXAS_EDITAR)
        )
        context['canais'] = MARKETPLACE_CHOICES
        context['canal_selecionado'] = self.request.GET.get('canal', '')
        if is_dev:
            context['lojas'] = Loja.objects.filter(ativo=True).order_by('nome')
            context['loja_selecionada'] = self.request.GET.get('loja', '')
        return context


class ParametroCanalCreateView(LoginRequiredMixin, ModuloRequeridoMixin, CreateView):
    """
    O QUE FAZ: Formulário para cadastro de novos parâmetros tarifários de um marketplace para uma Loja.
    POR QUE FAZ: Permite configurar novos canais diretamente pela interface do Hub.
    PERMISSÕES RBAC: DEV e ADMIN (via guard financeiro.parametros_canais / financeiro.taxas_editar).
    """
    modulo_requerido = 'financeiro'
    model = ParametroCanalMarketplace
    form_class = ParametroCanalMarketplaceForm
    template_name = 'financeiro/parametro_canal_form.html'
    success_url = reverse_lazy('parametro_canal_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (usuario_is_dev(request.user) or
                tem_funcionalidade(request.user, FUNC_FINANCEIRO_PARAMETROS_CANAIS) or
                tem_funcionalidade(request.user, FUNC_FINANCEIRO_TAXAS_EDITAR)):
            raise PermissionDenied("Acesso negado: seu perfil não possui permissão para cadastrar parâmetros de marketplaces.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        ip_cliente = self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))
        if ip_cliente and ',' in ip_cliente:
            ip_cliente = ip_cliente.split(',')[0].strip()

        LogAuditoria.objects.create(
            loja=self.object.loja,
            autor=self.request.user,
            evento=EventoAuditoriaEnum.CRIACAO_PARAMETROS_CANAL,
            detalhes=(
                f"Parâmetros tarifários cadastrados para {self.object.get_marketplace_display()} "
                f"(Loja: {self.object.loja.nome}): Comissão={self.object.comissao_padrao * 100:.2f}%, "
                f"Piso Frete=R$ {self.object.frete_gratis_piso}, "
                f"Taxa Acima=R$ {self.object.taxa_frete_acima_limite}, "
                f"Taxa Fixa Abaixo=R$ {self.object.taxa_fixa_abaixo_limite}"
            ),
            ip_origem=ip_cliente
        )
        messages.success(self.request, f"Parâmetros do marketplace '{self.object.get_marketplace_display()}' cadastrados com sucesso.")
        return response


class ParametroCanalUpdateView(LoginRequiredMixin, ModuloRequeridoMixin, UpdateView):
    """
    O QUE FAZ: Formulário de edição de parâmetros de comissão e frete de um canal de marketplace.
    POR QUE FAZ: Permite ajuste de tarifas comerciais com mitigação de IDOR/BOLA via <uuid:public_id>.
    PERMISSÕES RBAC: DEV e ADMIN (via guard financeiro.parametros_canais / financeiro.taxas_editar).
    MULTI-TENANCY: Identificação pública por UUID e restrição à própria loja para não-DEV.
    """
    modulo_requerido = 'financeiro'
    model = ParametroCanalMarketplace
    form_class = ParametroCanalMarketplaceForm
    template_name = 'financeiro/parametro_canal_form.html'
    slug_field = 'public_id'
    slug_url_kwarg = 'public_id'
    success_url = reverse_lazy('parametro_canal_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (usuario_is_dev(request.user) or
                tem_funcionalidade(request.user, FUNC_FINANCEIRO_PARAMETROS_CANAIS) or
                tem_funcionalidade(request.user, FUNC_FINANCEIRO_TAXAS_EDITAR)):
            raise PermissionDenied("Acesso negado: seu perfil não possui permissão para editar parâmetros de marketplaces.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or obj.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: você não tem permissão para editar parâmetros de outra loja.")
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)
        ip_cliente = self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))
        if ip_cliente and ',' in ip_cliente:
            ip_cliente = ip_cliente.split(',')[0].strip()

        LogAuditoria.objects.create(
            loja=self.object.loja,
            autor=self.request.user,
            evento=EventoAuditoriaEnum.EDICAO_PARAMETROS_CANAL,
            detalhes=(
                f"Parâmetros tarifários atualizados para {self.object.get_marketplace_display()} "
                f"(Loja: {self.object.loja.nome}): Comissão={self.object.comissao_padrao * 100:.2f}%, "
                f"Piso Frete=R$ {self.object.frete_gratis_piso}, "
                f"Taxa Acima=R$ {self.object.taxa_frete_acima_limite}, "
                f"Taxa Fixa Abaixo=R$ {self.object.taxa_fixa_abaixo_limite}"
            ),
            ip_origem=ip_cliente
        )
        messages.success(self.request, f"Parâmetros do marketplace '{self.object.get_marketplace_display()}' atualizados com sucesso.")
        return response

