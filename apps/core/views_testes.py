# Os códigos foram gerados com auxilio de I.A.
"""
Views para a Suíte e Laboratório de Testes Práticos de Concorrência e Resiliência.
Disponibiliza página intermediária (hub de testes) e views dedicadas para:
1. Teste de Baixa Concorrente de Saldo Físico com Lock Pessimista (Produto).
2. Teste de Renovação Concorrente de Tokens OAuth com Double-Checked Locking (ContaMarketplace).
Acesso estritamente restrito a usuários com papel DEV via RBAC (DevRequiredMixin).
"""
import json
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse

from apps.catalogo.models import Produto
from apps.catalogo.enums import StatusProdutoEnum
from apps.marketplaces.models import ContaMarketplace
from apps.tenancy.permissions import DevRequiredMixin
from .services_testes import ConcorrenciaEstoqueTestService, ConcorrenciaOAuthTestService


class TestesDashboardView(DevRequiredMixin, View):
    """
    Página intermediária (Hub de Testes do Sistema).
    Apresenta catálogo com os testes disponíveis no laboratório de concorrência e integridade,
    permitindo navegação modularizada para as views dedicadas de cada teste.
    """
    template_name = 'testes/dashboard.html'

    def get(self, request, *args, **kwargs):
        total_produtos = Produto.objects.filter(status=StatusProdutoEnum.ATIVO).count()
        total_contas = ContaMarketplace.objects.filter(ativo=True).count()

        context = {
            'total_produtos': total_produtos,
            'total_contas': total_contas,
        }
        return render(request, self.template_name, context)


class ConcorrenciaEstoqueView(DevRequiredMixin, View):
    """
    Teste 1: Baixa Concorrente de Saldo Físico com Lock Pessimista (select_for_update).
    Simula três requisições concorrentes disparadas no mesmo milissegundo disputando a mesma linha de Produto.
    Mede a contenção real da tabela, tempo de travamento e grava auditoria completa em HistoricoPreco.
    """
    template_name = 'testes/concorrencia_estoque.html'

    def get(self, request, *args, **kwargs):
        produtos = Produto.objects.filter(status=StatusProdutoEnum.ATIVO).select_related('loja').order_by('nome')
        context = {
            'produtos': produtos,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        if request.content_type == 'application/json':
            try:
                dados = json.loads(request.body)
            except Exception:
                return JsonResponse({'sucesso': False, 'erro': 'JSON malformatado.'}, status=400)
        else:
            dados = request.POST

        try:
            produto_id = int(dados.get('produto_id', 0))
            qtd1 = int(dados.get('qtd1', 0))
            qtd2 = int(dados.get('qtd2', 0))
            qtd3 = int(dados.get('qtd3', 0))
            tempo_trava_ms = int(dados.get('tempo_trava_ms', 0))

            resultado = ConcorrenciaEstoqueTestService.executar_teste(
                produto_id=produto_id,
                qtd1=qtd1,
                qtd2=qtd2,
                qtd3=qtd3,
                tempo_trava_ms=tempo_trava_ms,
                user=request.user
            )
            status_code = 200 if resultado.get('sucesso') else 400
            return JsonResponse(resultado, status=status_code)

        except (ValueError, Produto.DoesNotExist) as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': f'Erro interno durante o teste: {str(e)}'}, status=500)


class ConcorrenciaOAuthView(DevRequiredMixin, View):
    """
    Teste 2: Renovação Concorrente de Token OAuth & Double-Checked Locking.
    Simula três requisições simultâneas de refresh token sobre a mesma credencial de marketplace.
    Comprova que apenas uma chamada à API externa é disparada e as requisições subsequentes reaproveitam o token gerado.
    """
    template_name = 'testes/concorrencia_oauth.html'

    def get(self, request, *args, **kwargs):
        contas = ContaMarketplace.objects.filter(ativo=True).select_related('loja').order_by('apelido_conta')
        context = {
            'contas': contas,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        if request.content_type == 'application/json':
            try:
                dados = json.loads(request.body)
            except Exception:
                return JsonResponse({'sucesso': False, 'erro': 'JSON malformatado.'}, status=400)
        else:
            dados = request.POST

        try:
            conta_id = int(dados.get('conta_id', 0))
            tempo_trava_ms = int(dados.get('tempo_trava_ms', 0))

            resultado = ConcorrenciaOAuthTestService.executar_teste(
                conta_id=conta_id,
                tempo_trava_ms=tempo_trava_ms,
                user=request.user
            )
            status_code = 200 if resultado.get('sucesso') else 400
            return JsonResponse(resultado, status=status_code)

        except (ValueError, ContaMarketplace.DoesNotExist) as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': f'Erro interno durante o teste: {str(e)}'}, status=500)


class ConcorrenciaTestesView(DevRequiredMixin, View):
    """
    View de compatibilidade legada que redireciona para a nova página intermediária (Hub de Testes).
    """
    def get(self, request, *args, **kwargs):
        return redirect('testes_dashboard')
