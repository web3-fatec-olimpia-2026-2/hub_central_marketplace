# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo json para decodificação de requisições AJAX com payload estruturado
import json

# Importa a classe Decimal para manipulação de porcentagens e valores monetários com precisão exata
from decimal import Decimal

# Importa atalhos do Django para renderização de páginas HTML e recuperação de instâncias com disparo de 404
from django.shortcuts import render, get_object_or_404

# Importa as classes genéricas de visualização baseadas em classe (CBVs) TemplateView e View
from django.views.generic import TemplateView, View

# Importa o mixin nativo do Django que exige que o usuário esteja devidamente autenticado na sessão
from django.contrib.auth.mixins import LoginRequiredMixin

# Importa JsonResponse para retorno estruturado em JSON para os gráficos e painéis reativos do front-end
from django.http import JsonResponse

# Importa a exceção de segurança do Django que interrompe o fluxo disparando HTTP 403 Forbidden
from django.core.exceptions import PermissionDenied

# Importa a entidade Loja representativa do tenant no particionamento de dados
from apps.tenancy.models import Loja

# Importa os mixins e funções de controle de acesso (RBAC) e verificação contratual do módulo financeiro
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, FinancialAccessMixin, usuario_is_dev, pode_acessar_inteligencia_financeira
)

# Importa o modelo de Produto físico do catálogo para obtenção de preços e custos diretos
from apps.catalogo.models import Produto

# Importa as opções tarifárias de canais de venda e a entidade de parâmetros fiscais da loja
from .models import MARKETPLACE_CHOICES, ConfiguracaoTaxasLoja

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
