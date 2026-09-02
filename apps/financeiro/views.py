# Os códigos foram gerados com auxilio de I.A.
import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied

from apps.tenancy.models import Loja
from apps.tenancy.permissions import (
    ModuloRequeridoMixin, FinancialAccessMixin, usuario_is_dev, pode_acessar_inteligencia_financeira
)
from apps.catalogo.models import Produto
from .models import MARKETPLACE_CHOICES, ConfiguracaoTaxasLoja
from .services import SimuladorPromocionalService


class SimuladorPromocionalView(LoginRequiredMixin, ModuloRequeridoMixin, FinancialAccessMixin, View):
    """
    O QUE FAZ: Interface interativa e endpoint AJAX para simulação financeira e formação de preço promocional.
    POR QUE FAZ: Fornece ao lojista análise de viabilidade, margem líquida em tempo real e volume de compensação (Q_meta) antes de aplicar descontos.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (FinancialAccessMixin / RN-09). USUARIO é bloqueado com 403 Forbidden.
    MULTI-TENANCY: Filtra os produtos da loja do usuário e utiliza os parâmetros fiscais do tenant.
    """
    modulo_requerido = 'financeiro'
    template_name = 'financeiro/simulador_promocional.html'

    def get(self, request, *args, **kwargs):
        user = request.user
        is_dev = usuario_is_dev(user)

        if is_dev:
            lojas = Loja.objects.filter(ativo=True).order_by('nome')
            loja_selecionada_id = request.GET.get('loja', '')
            if loja_selecionada_id:
                produtos = Produto.objects.filter(loja_id=loja_selecionada_id, status='ATIVO').order_by('nome')
            else:
                produtos = Produto.objects.filter(status='ATIVO').order_by('nome')
        else:
            perfil = getattr(user, 'perfil', None)
            lojas = [perfil.loja] if perfil and perfil.loja else []
            produtos = Produto.objects.filter(loja=perfil.loja, status='ATIVO').order_by('nome') if perfil and perfil.loja else []

        context = {
            'is_dev': is_dev,
            'lojas': lojas,
            'produtos': produtos,
            'canais': MARKETPLACE_CHOICES,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST
        except Exception:
            data = request.POST

        produto_id = data.get('produto_id')
        canal_nome = data.get('canal', 'mercadolivre_classico')
        desconto_pct = Decimal(str(data.get('desconto_pct', '10.0')))
        volume_mensal = int(data.get('volume_mensal', 100))

        if not produto_id:
            return JsonResponse({'erro': 'Selecione um produto para simular.'}, status=400)

        produto = get_object_or_404(Produto, pk=produto_id)

        # Ownership Check multi-tenant
        if not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.loja or produto.loja_id != perfil.loja_id:
                raise PermissionDenied("Acesso negado: o produto selecionado pertence a outra loja.")

        resultado = SimuladorPromocionalService.simular_impacto_promocional(
            produto=produto,
            canal_nome=canal_nome,
            percentual_desconto=desconto_pct,
            volume_estimado_mensal=volume_mensal
        )

        return JsonResponse(resultado)
