# Os códigos foram gerados com auxilio de I.A.
"""
Views para a Interface Gráfica de Testes Práticos de Concorrência.
Disponibiliza os painéis interativos de demonstração do Lock Pessimista e Double-Checked Locking.
"""
import json
from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied

from apps.catalogo.models import Produto
from apps.catalogo.enums import StatusProdutoEnum
from apps.marketplaces.models import ContaMarketplace
from apps.tenancy.permissions import usuario_is_dev
from .services_testes import ConcorrenciaEstoqueTestService, ConcorrenciaOAuthTestService


class ConcorrenciaTestesView(LoginRequiredMixin, View):
    """
    Interface e endpoints AJAX para testes de concorrência e integridade transacional.
    Demonstra visualmente a retenção do Lock Pessimista e o funcionamento do Double-Checked Locking.
    """
    template_name = 'testes/concorrencia.html'

    def _get_tenant_loja(self, user):
        perfil = getattr(user, 'perfil', None)
        return getattr(perfil, 'loja', None) if perfil else None

    def get(self, request, *args, **kwargs):
        is_dev = usuario_is_dev(request.user)
        loja = self._get_tenant_loja(request.user)

        if is_dev or request.user.is_superuser or not loja:
            produtos = Produto.objects.filter(status=StatusProdutoEnum.ATIVO).select_related('loja').order_by('nome')
            contas = ContaMarketplace.objects.filter(ativo=True).select_related('loja').order_by('apelido_conta')
        else:
            produtos = Produto.objects.filter(loja=loja, status=StatusProdutoEnum.ATIVO).order_by('nome')
            contas = ContaMarketplace.objects.filter(loja=loja, ativo=True).order_by('apelido_conta')

        context = {
            'produtos': produtos,
            'contas': contas,
            'is_dev': is_dev,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # Suporta requisições com payload JSON ou Form Data tradicional
        if request.content_type == 'application/json':
            try:
                dados = json.loads(request.body)
            except Exception:
                return JsonResponse({'sucesso': False, 'erro': 'JSON malformatado.'}, status=400)
        else:
            dados = request.POST

        acao = dados.get('acao')

        try:
            if acao == 'teste_estoque':
                produto_id = int(dados.get('produto_id', 0))
                qtd1 = int(dados.get('qtd1', 1))
                qtd2 = int(dados.get('qtd2', 2))
                delay_ms = int(dados.get('delay_ms', 500))

                resultado = ConcorrenciaEstoqueTestService.executar_teste(
                    produto_id=produto_id,
                    qtd1=qtd1,
                    qtd2=qtd2,
                    delay_ms=delay_ms,
                    user=request.user
                )
                status_code = 200 if resultado.get('sucesso') else 400
                return JsonResponse(resultado, status=status_code)

            elif acao == 'teste_oauth':
                conta_id = int(dados.get('conta_id', 0))
                delay_ms = int(dados.get('delay_ms', 500))

                resultado = ConcorrenciaOAuthTestService.executar_teste(
                    conta_id=conta_id,
                    delay_ms=delay_ms,
                    user=request.user
                )
                status_code = 200 if resultado.get('sucesso') else 400
                return JsonResponse(resultado, status=status_code)

            else:
                return JsonResponse({'sucesso': False, 'erro': f'Ação desconhecida: {acao}'}, status=400)

        except (ValueError, Produto.DoesNotExist, ContaMarketplace.DoesNotExist) as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': f'Erro interno durante o teste: {str(e)}'}, status=500)
