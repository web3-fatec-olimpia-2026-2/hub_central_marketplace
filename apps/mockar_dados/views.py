# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: View do painel de controle e gerenciamento de dados mockados de desenvolvimento.
POR QUE FAZ: Fornece interface visual para o usuário DEV provisionar, restaurar e excluir dados fictícios de demonstração.
REGRAS DE SEGURANÇA E AMBIENTE:
- Acesso estritamente restrito a usuários com papel DEV (raise PermissionDenied caso contrário).
- Não afeta a conta mestre devmaster.
"""
from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.contrib import messages

from apps.tenancy.permissions import usuario_is_dev
from .services import MockDataService


class MockarDadosDashboardView(LoginRequiredMixin, View):
    """
    Painel de Gestão e Ações de Mock de Dados para Desenvolvimento.
    """
    template_name = 'mockar_dados/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: o módulo Mockar Dados é de uso restrito e exclusivo do perfil DEV.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        tem_dados = MockDataService.tem_dados_mockados()
        contadores = MockDataService.contar_registros_mockados()

        context = {
            'tem_dados_mockados': tem_dados,
            'contadores': contadores,
            'is_dev': True,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        acao = request.POST.get('acao')

        if acao == 'gerar':
            resultado = MockDataService.gerar_dados_mockados()
            messages.success(
                request,
                f"Conjunto de dados mockados gerado com sucesso! Foram provisionadas {resultado['lojas_criadas']} lojas, "
                f"{resultado['produtos_criados']} produtos e {resultado['anuncios_criados']} anúncios de marketplace."
            )
        elif acao == 'excluir':
            resultado = MockDataService.excluir_dados_mockados()
            messages.warning(
                request,
                f"Todos os dados mockados foram excluídos com sucesso ({resultado['lojas_excluidas']} lojas e "
                f"{resultado['usuarios_excluidos']} usuários de teste removidos). O usuário DEV mestre permanece intacto."
            )
        else:
            messages.error(request, "Ação não reconhecida.")

        return redirect('mockar_dados_dashboard')
