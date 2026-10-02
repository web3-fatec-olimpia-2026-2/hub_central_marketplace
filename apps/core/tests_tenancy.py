# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Testes unitários para o contrato neutro de Tenancy get_tenant(request) (Doc ① §10.6 e §22.1 item 18).
POR QUE FAZ: Garante que a resolução do tenant funcione com segurança nos modos 'single' e 'row', e em tarefas assíncronas.
"""

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser

from apps.core.tenancy import get_tenant, get_tenant_mode
from apps.tenancy.models import Loja, PerfilUsuario, PapelUsuarioEnum


class TenancyContratoNeutroTests(TestCase):
    """Valida o comportamento de get_tenant(request) conforme o modo de isolamento."""

    def setUp(self):
        self.factory = RequestFactory()
        self.loja_alpha = Loja.objects.create(
            nome="Loja Alpha",
            slug="loja-alpha",
            cnpj="10.000.000/0001-01"
        )
        self.loja_beta = Loja.objects.create(
            nome="Loja Beta",
            slug="loja-beta",
            cnpj="20.000.000/0001-02"
        )

        self.user_alpha = User.objects.create_user(username="user_alpha", password="Password123!")
        self.perfil_alpha = PerfilUsuario.objects.create(
            usuario=self.user_alpha,
            loja=self.loja_alpha,
            papel=PapelUsuarioEnum.ADMIN
        )

        self.user_beta = User.objects.create_user(username="user_beta", password="Password123!")
        self.perfil_beta = PerfilUsuario.objects.create(
            usuario=self.user_beta,
            loja=self.loja_beta,
            papel=PapelUsuarioEnum.ADMIN
        )

    @override_settings(TENANCY_MODE='single')
    def test_modo_single_retorna_tenant_fixo_default(self):
        """Em modo 'single', devolve sempre o mesmo tenant fixo independentemente do usuário (Doc ① §10.6)."""
        request = self.factory.get('/')
        request.user = self.user_beta

        tenant_resolvido = get_tenant(request)
        # Deve retornar a loja default (alpha)
        self.assertEqual(tenant_resolvido, self.loja_alpha)

    @override_settings(TENANCY_MODE='row')
    def test_modo_row_resolve_tenant_pelo_perfil_do_usuario(self):
        """Em modo 'row', resolve o tenant pelo vínculo request.user.perfil.loja."""
        # Requisição do usuário Alpha
        request_a = self.factory.get('/')
        request_a.user = self.user_alpha
        self.assertEqual(get_tenant(request_a), self.loja_alpha)

        # Requisição do usuário Beta
        request_b = self.factory.get('/')
        request_b.user = self.user_beta
        self.assertEqual(get_tenant(request_b), self.loja_beta)

    def test_explicit_tenant_para_tarefas_background_e_comandos(self):
        """Tarefas em background e testes devem receber explicit_tenant sem estado global compartilhado."""
        resultado = get_tenant(request=None, explicit_tenant=self.loja_beta)
        self.assertEqual(resultado, self.loja_beta)
