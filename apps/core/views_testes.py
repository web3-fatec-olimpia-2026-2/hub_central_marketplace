# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o propósito das views de laboratório, cenários de teste e restrição RBAC
"""
Views para a Suíte e Laboratório de Testes Práticos de Concorrência e Resiliência.
Disponibiliza página intermediária (hub de testes) e views dedicadas para:
1. Teste de Baixa Concorrente de Saldo Físico com Lock Pessimista (Produto).
2. Teste de Renovação Concorrente de Tokens OAuth com Double-Checked Locking (ContaMarketplace).
Acesso estritamente restrito a usuários com papel DEV via RBAC (DevRequiredMixin).
"""
# Fim do bloco de documentação arquitetural do módulo de views de testes

# Importa o módulo nativo json para decodificar corpos de requisições enviadas no formato application/json
import json

# Importa atalhos do Django para renderização de templates HTML e redirecionamento de rotas
from django.shortcuts import render, redirect

# Importa a classe base genérica View do Django para criação de Class-Based Views
from django.views import View

# Importa JsonResponse para devolver respostas estruturadas em JSON aos clientes e chamadas AJAX
from django.http import JsonResponse

# Importa a entidade Produto que representa o inventário físico gerenciado
from apps.catalogo.models import Produto

# Importa a enumeração de status de ciclo de vida dos produtos
from apps.catalogo.enums import StatusProdutoEnum

# Importa o modelo de credenciais de contas vinculadas aos canais parceiros
from apps.marketplaces.models import ContaMarketplace

# Importa o mixin de permissão que bloqueia qualquer operador que não possua papel estrito de DEV
from apps.tenancy.permissions import DevRequiredMixin

# Importa os serviços que orquestram os testes multithread de estoque e tokens OAuth
from .services_testes import ConcorrenciaEstoqueTestService, ConcorrenciaOAuthTestService


# View intermediária que funciona como painel central/hub de navegação do laboratório de testes
class TestesDashboardView(DevRequiredMixin, View):
    # Início do bloco de docstring documentando a responsabilidade do dashboard de testes
    """
    Página intermediária (Hub de Testes do Sistema).
    Apresenta catálogo com os testes disponíveis no laboratório de concorrência e integridade,
    permitindo navegação modularizada para as views dedicadas de cada teste.
    """
    # Fim da docstring explicativa

    # Caminho do template HTML do painel de testes
    template_name = 'testes/dashboard.html'

    # Método GET que contabiliza recursos ativos no sistema e renderiza o dashboard
    def get(self, request, *args, **kwargs):
        # Contabiliza a quantidade total de produtos ativos cadastrados no sistema
        total_produtos = Produto.objects.filter(status=StatusProdutoEnum.ATIVO).count()

        # Contabiliza a quantidade total de contas de integração ativas
        total_contas = ContaMarketplace.objects.filter(ativo=True).count()

        # Monta o dicionário de contexto repassado ao template
        context = {
            'total_produtos': total_produtos,
            'total_contas': total_contas,
        }

        # Renderiza e entrega a página HTML do hub de testes
        return render(request, self.template_name, context)


# View dedicada ao Teste 1: simulação de concorrência e lock pessimista sobre o estoque físico
class ConcorrenciaEstoqueView(DevRequiredMixin, View):
    # Início do bloco de docstring documentando o escopo do teste de concorrência de estoque
    """
    Teste 1: Baixa Concorrente de Saldo Físico com Lock Pessimista (select_for_update).
    Simula três requisições concorrentes disparadas no mesmo milissegundo disputando a mesma linha de Produto.
    Mede a contenção real da tabela, tempo de travamento e grava auditoria completa em HistoricoPreco.
    """
    # Fim da docstring explicativa da view de estoque

    # Caminho do template HTML da interface de testes de estoque
    template_name = 'testes/concorrencia_estoque.html'

    # Método GET que carrega a listagem de produtos ativos para preenchimento do formulário
    def get(self, request, *args, **kwargs):
        # Consulta produtos ativos pré-carregando a loja relacionada e ordenando por nome
        produtos = Produto.objects.filter(status=StatusProdutoEnum.ATIVO).select_related('loja').order_by('nome')

        # Injeta a coleção de produtos no contexto
        context = {
            'produtos': produtos,
        }

        # Renderiza o template de teste de estoque
        return render(request, self.template_name, context)

    # Método POST que processa a submissão dos parâmetros e dispara a simulação das 3 threads
    def post(self, request, *args, **kwargs):
        # Avalia se a requisição foi enviada com payload JSON via AJAX
        if request.content_type == 'application/json':
            # Bloco protegido para decodificação do corpo JSON
            try:
                dados = json.loads(request.body)
            # Retorna erro HTTP 400 em caso de payload malformado
            except Exception:
                return JsonResponse({'sucesso': False, 'erro': 'JSON malformatado.'}, status=400)
        # Se for submissão padrão de formulário HTML (application/x-www-form-urlencoded)
        else:
            dados = request.POST

        # Bloco protegido para extração de parâmetros, execução do serviço e tratamento de exceções
        try:
            # Extrai e sanitiza o ID do produto alvo
            produto_id = int(dados.get('produto_id', 0))

            # Extrai a quantidade a ser deduzida na requisição concorrente 1
            qtd1 = int(dados.get('qtd1', 0))

            # Extrai a quantidade a ser deduzida na requisição concorrente 2
            qtd2 = int(dados.get('qtd2', 0))

            # Extrai a quantidade a ser deduzida na requisição concorrente 3
            qtd3 = int(dados.get('qtd3', 0))

            # Extrai o tempo em milissegundos de retenção forçada da trava (sleep)
            tempo_trava_ms = int(dados.get('tempo_trava_ms', 0))

            # Executa o serviço de testes disparando as 3 threads simultâneas
            resultado = ConcorrenciaEstoqueTestService.executar_teste(
                produto_id=produto_id,
                qtd1=qtd1,
                qtd2=qtd2,
                qtd3=qtd3,
                tempo_trava_ms=tempo_trava_ms,
                user=request.user
            )

            # Define código HTTP 200 para sucesso matemático ou 400 se houver inconsistência
            status_code = 200 if resultado.get('sucesso') else 400

            # Retorna a telemetria consolidada em JSON
            return JsonResponse(resultado, status=status_code)

        # Trata erros de validação de parâmetros numéricos ou produto inexistente
        except (ValueError, Produto.DoesNotExist) as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)}, status=400)

        # Trata exceções não mapeadas do sistema
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': f'Erro interno durante o teste: {str(e)}'}, status=500)


# View dedicada ao Teste 2: simulação de renovação concorrente de tokens OAuth e Double-Checked Locking
class ConcorrenciaOAuthView(DevRequiredMixin, View):
    # Início do bloco de docstring documentando o teste de renovação e reaproveitamento de tokens
    """
    Teste 2: Renovação Concorrente de Token OAuth & Double-Checked Locking.
    Simula três requisições simultâneas de refresh token sobre a mesma credencial de marketplace.
    Comprova que apenas uma chamada à API externa é disparada e as requisições subsequentes reaproveitam o token gerado.
    """
    # Fim da docstring informativa da view de OAuth

    # Caminho do template HTML da interface de testes de OAuth
    template_name = 'testes/concorrencia_oauth.html'

    # Método GET que recupera as contas de marketplace ativas para exibição na tela
    def get(self, request, *args, **kwargs):
        # Consulta contas ativas pré-carregando a loja e ordenando por apelido
        contas = ContaMarketplace.objects.filter(ativo=True).select_related('loja').order_by('apelido_conta')

        # Injeta as contas no contexto
        context = {
            'contas': contas,
        }

        # Renderiza a página de teste de OAuth
        return render(request, self.template_name, context)

    # Método POST que recebe os parâmetros e aciona o teste de concorrência com 3 requisições
    def post(self, request, *args, **kwargs):
        # Checa se o conteúdo é JSON
        if request.content_type == 'application/json':
            # Tenta decodificar o corpo JSON
            try:
                dados = json.loads(request.body)
            except Exception:
                return JsonResponse({'sucesso': False, 'erro': 'JSON malformatado.'}, status=400)
        # Processa dados submetidos via formulário convencional
        else:
            dados = request.POST

        # Inicia bloco de execução do teste
        try:
            # Extrai e converte a PK da conta de integração
            conta_id = int(dados.get('conta_id', 0))

            # Extrai o tempo de trava em milissegundos
            tempo_trava_ms = int(dados.get('tempo_trava_ms', 0))

            # Executa o serviço que testa a concorrência e o Double-Checked Locking
            resultado = ConcorrenciaOAuthTestService.executar_teste(
                conta_id=conta_id,
                tempo_trava_ms=tempo_trava_ms,
                user=request.user
            )

            # Define o código de retorno com base no sucesso da rotina
            status_code = 200 if resultado.get('sucesso') else 400

            # Retorna o relatório completo em formato JSON
            return JsonResponse(resultado, status=status_code)

        # Captura parâmetros inválidos ou conta inexistente
        except (ValueError, ContaMarketplace.DoesNotExist) as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)}, status=400)

        # Captura falhas inesperadas de execução
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': f'Erro interno durante o teste: {str(e)}'}, status=500)


# View para redirecionamento retrocompatível da rota legada de testes para o novo dashboard
class ConcorrenciaTestesView(DevRequiredMixin, View):
    # Início do bloco de docstring que documenta o propósito de redirecionamento legado
    """
    View de compatibilidade legada que redireciona para a nova página intermediária (Hub de Testes).
    """
    # Fim da docstring explicativa

    # Método GET que intercepta requisições à URL antiga e redireciona para o dashboard
    def get(self, request, *args, **kwargs):
        # Redireciona para a rota nomeada 'testes_dashboard'
        return redirect('testes_dashboard')
