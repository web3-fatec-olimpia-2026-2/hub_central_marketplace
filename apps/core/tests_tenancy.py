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


class BolaIdorSecurityTestCase(TestCase):
    """
    O QUE FAZ: Suíte de testes de segurança para validação da mitigação de IDOR e BOLA (Doc ① §10.4, §17.3 e Doc ② §8.2).
    POR QUE FAZ: Garante que nenhuma rota exponha identificadores sequenciais inteiros (<int:pk>) e que o acesso
                 com UUID válido de outro tenant resulte estritamente em HTTP 404 (recurso inexistente no tenant).
    """

    def setUp(self):
        import uuid
        from decimal import Decimal
        from django.test import Client
        from apps.catalogo.models import Categoria, Produto
        from apps.anuncios.models import Anuncio
        from apps.marketplaces.models import ContaMarketplace
        from apps.marketplaces.enums import CanalMarketplaceEnum
        from apps.pedidos.models import PedidoVenda

        self.client = Client()

        # Tenant 1 (Alpha)
        self.loja_alpha = Loja.objects.create(nome="Loja Alpha", slug="loja-alpha-sec", cnpj="11.111.111/0001-11")
        self.user_alpha = User.objects.create_user(username="admin_alpha_sec", password="Password123!")
        self.perfil_alpha = PerfilUsuario.objects.create(usuario=self.user_alpha, loja=self.loja_alpha, papel=PapelUsuarioEnum.ADMIN)

        # Tenant 2 (Beta)
        self.loja_beta = Loja.objects.create(nome="Loja Beta", slug="loja-beta-sec", cnpj="22.222.222/0001-22")
        self.user_beta = User.objects.create_user(username="admin_beta_sec", password="Password123!")
        self.perfil_beta = PerfilUsuario.objects.create(usuario=self.user_beta, loja=self.loja_beta, papel=PapelUsuarioEnum.ADMIN)

        # Recursos do Tenant Alpha
        self.cat_alpha = Categoria.objects.create(loja=self.loja_alpha, nome="Categoria Alpha")
        self.prod_alpha = Produto.objects.create(loja=self.loja_alpha, categoria=self.cat_alpha, sku="SKU-ALPHA-1", nome="Produto Alpha", preco=Decimal("100.00"), estoque=10)
        self.conta_alpha = ContaMarketplace.objects.create(loja=self.loja_alpha, canal=CanalMarketplaceEnum.MERCADOLIVRE, apelido_conta="ML Alpha", seller_id_externo="11111")
        self.anuncio_alpha = Anuncio.objects.create(conta=self.conta_alpha, item_id_externo="MLB-ALPHA-1", titulo="Anuncio Alpha", preco_venda=Decimal("100.00"), estoque_publicado=5)
        self.pedido_alpha = PedidoVenda.objects.create(loja=self.loja_alpha, conta_marketplace=self.conta_alpha, canal_origem=CanalMarketplaceEnum.MERCADOLIVRE, pedido_id_externo="PED-ALPHA-1", valor_total=Decimal("100.00"))

    def test_rotas_rejeitam_identificador_inteiro_sequencial_com_404(self):
        """Tentativas de ataque de enumeração com IDs inteiros sequenciais (IDOR) devem retornar 404 via conversor de URL."""
        self.client.force_login(self.user_alpha)

        # Rotas com <uuid:public_id> rejeitam acessos com inteiros (/produtos/1/, /anuncios/1/, etc.)
        urls_com_inteiro = [
            f"/produtos/{self.prod_alpha.pk}/",
            f"/produtos/{self.prod_alpha.pk}/editar/",
            f"/anuncios/{self.anuncio_alpha.pk}/",
            f"/anuncios/{self.anuncio_alpha.pk}/editar/",
            f"/pedidos/{self.pedido_alpha.pk}/",
            f"/marketplaces/contas/{self.conta_alpha.pk}/editar/",
            f"/usuarios/{self.user_alpha.pk}/toggle-status/",
        ]
        for url in urls_com_inteiro:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 404,
                f"A rota '{url}' deveria retornar HTTP 404 para ID sequencial inteiro, mas retornou {response.status_code}."
            )

    def test_cross_tenant_produto_com_uuid_valido_retorna_404_ou_403(self):
        """Usuário do Tenant Beta não pode acessar Produto do Tenant Alpha mesmo conhecendo seu UUID (BOLA)."""
        self.client.force_login(self.user_beta)

        # GET detalhe do produto
        res_detail = self.client.get(f"/produtos/{self.prod_alpha.public_id}/")
        self.assertIn(res_detail.status_code, [403, 404])

        # GET edição do produto
        res_edit = self.client.get(f"/produtos/{self.prod_alpha.public_id}/editar/")
        self.assertIn(res_edit.status_code, [403, 404])

        # POST exclusão do produto
        res_del = self.client.post(f"/produtos/{self.prod_alpha.public_id}/excluir/")
        self.assertIn(res_del.status_code, [403, 404])

    def test_cross_tenant_anuncio_com_uuid_valido_retorna_404_ou_403(self):
        """Usuário do Tenant Beta não pode acessar Anúncio do Tenant Alpha mesmo com UUID válido (BOLA)."""
        self.client.force_login(self.user_beta)

        res_detail = self.client.get(f"/anuncios/{self.anuncio_alpha.public_id}/")
        self.assertIn(res_detail.status_code, [403, 404])

        res_edit = self.client.get(f"/anuncios/{self.anuncio_alpha.public_id}/editar/")
        self.assertIn(res_edit.status_code, [403, 404])

    def test_cross_tenant_pedido_com_uuid_valido_retorna_404_ou_403(self):
        """Usuário do Tenant Beta não pode acessar Pedido do Tenant Alpha mesmo com UUID válido (BOLA)."""
        self.client.force_login(self.user_beta)

        res = self.client.get(f"/pedidos/{self.pedido_alpha.public_id}/")
        self.assertIn(res.status_code, [403, 404])

    def test_cross_tenant_conta_marketplace_com_uuid_valido_retorna_404_ou_403(self):
        """Usuário do Tenant Beta não pode acessar Conta Marketplace do Tenant Alpha mesmo com UUID válido (BOLA)."""
        self.client.force_login(self.user_beta)

        res = self.client.get(f"/marketplaces/contas/{self.conta_alpha.public_id}/editar/")
        self.assertIn(res.status_code, [403, 404])

    def test_cross_tenant_usuario_management_com_uuid_valido_retorna_404_ou_403(self):
        """Admin do Tenant Beta não pode alterar status nem senha de Usuário do Tenant Alpha (BOLA)."""
        self.client.force_login(self.user_beta)

        res_toggle = self.client.post(f"/usuarios/{self.perfil_alpha.public_id}/toggle-status/")
        self.assertIn(res_toggle.status_code, [403, 404])

        res_pwd = self.client.post(f"/usuarios/{self.perfil_alpha.public_id}/password-reset/", {
            'nova_senha1': 'HackedPassword123!',
            'nova_senha2': 'HackedPassword123!'
        })
        self.assertIn(res_pwd.status_code, [403, 404])

    def test_modelos_geram_uuid4_canonica_no_public_id(self):
        """Valida que todos os modelos auditados possuem public_id no formato UUIDv4 canônico."""
        import uuid
        modelos = [
            self.loja_alpha,
            self.perfil_alpha,
            self.cat_alpha,
            self.prod_alpha,
            self.conta_alpha,
            self.anuncio_alpha,
            self.pedido_alpha,
        ]
        for instancia in modelos:
            self.assertIsNotNone(instancia.public_id)
            self.assertIsInstance(instancia.public_id, uuid.UUID)
            self.assertEqual(instancia.public_id.version, 4)

