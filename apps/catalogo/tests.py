# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import CanalMarketplaceEnum
from apps.catalogo.models import Categoria, Produto, AnuncioMarketplace, HistoricoPreco
from apps.catalogo.enums import TipoAjusteEstoqueEnum


class CatalogoAndRBACPermissionsTestCase(TestCase):
    """
    O QUE FAZ: Suíte de testes automatizados para Catálogo de Produtos, Anúncios Multicanal e Restrições RBAC (RN-09).
    POR QUE FAZ: Garante que o papel USUARIO não altere preços nem exclua itens, mas possa registrar baixas por avaria.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR, USUARIO.
    MULTI-TENANCY: Isolamento por Loja.
    """

    def setUp(self):
        self.client = Client()

        self.loja = Loja.objects.create(
            nome="Loja Central",
            slug="loja-central",
            cnpj="44.444.444/0001-44"
        )
        self.loja.garantir_modulos_padrao()

        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Eletrônicos",
            slug="eletronicos"
        )

        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="NOTE-DELL-G15",
            nome="Notebook Dell G15",
            preco=Decimal('5000.00'),
            estoque=10,
            custo_aquisicao=Decimal('3500.00'),
            custo_embalagem=Decimal('15.00')
        )

        # Usuários
        self.user_admin = User.objects.create_user(username='admin_cat', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.user_padrao = User.objects.create_user(username='usuario_cat', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

        # Contas de marketplace para anúncio multicanal
        self.conta_ml = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Principal",
            seller_id_externo="1111"
        )
        self.conta_shopee = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.SHOPEE,
            apelido_conta="Shopee Principal",
            seller_id_externo="2222"
        )

    def test_anuncio_multicanal_decoupling(self):
        """Valida a vinculação de múltiplos anúncios em canais distintos ao mesmo produto."""
        anuncio_ml = AnuncioMarketplace.objects.create(
            produto=self.produto,
            conta_marketplace=self.conta_ml,
            item_id_externo="MLB998877",
            preco_sincronizado=Decimal('5000.00')
        )
        anuncio_shopee = AnuncioMarketplace.objects.create(
            produto=self.produto,
            conta_marketplace=self.conta_shopee,
            item_id_externo="SHP112233",
            preco_sincronizado=Decimal('5000.00')
        )

        self.assertEqual(self.produto.anuncios.count(), 2)
        self.assertIn(anuncio_ml, self.produto.anuncios.all())
        self.assertIn(anuncio_shopee, self.produto.anuncios.all())

    def test_price_mutation_creates_history_record(self):
        """Valida que a alteração de preço grava automaticamente em HistoricoPreco."""
        self.client.login(username='admin_cat', password='password123')
        response = self.client.post(reverse('produto_update', kwargs={'pk': self.produto.pk}), {
            'sku': self.produto.sku,
            'nome': self.produto.nome,
            'categoria': self.categoria.pk,
            'preco': '5200.00',
            'estoque': '10',
            'status': 'ATIVO'
        })
        self.assertEqual(response.status_code, 302)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.preco, Decimal('5200.00'))

        historico = HistoricoPreco.objects.filter(produto=self.produto).latest('criado_em')
        self.assertEqual(historico.preco_anterior, Decimal('5000.00'))
        self.assertEqual(historico.preco_novo, Decimal('5200.00'))

    def test_usuario_role_cannot_alter_price_or_delete_product(self):
        """Valida as restrições do papel USUARIO: bloqueio de alteração de preço e exclusão (RN-09)."""
        # 1. Tenta alterar preço via formulário -> Preço é preservado e ignorado
        self.client.login(username='usuario_cat', password='password123')
        self.client.post(reverse('produto_update', kwargs={'pk': self.produto.pk}), {
            'sku': self.produto.sku,
            'nome': 'Notebook Dell G15 Editado',
            'categoria': self.categoria.pk,
            'preco': '1000.00',  # Tentativa de alteração não autorizada
            'estoque': '50',      # Tentativa de ajuste geral não autorizada
            'status': 'ATIVO'
        })

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.preco, Decimal('5000.00'))  # Preço intacto
        self.assertEqual(self.produto.estoque, 10)               # Estoque intacto
        self.assertEqual(self.produto.nome, 'Notebook Dell G15 Editado')  # Descritivo atualizado

        # 2. Tenta excluir produto -> Espera 403 Forbidden
        res_del = self.client.post(reverse('produto_delete', kwargs={'pk': self.produto.pk}))
        self.assertEqual(res_del.status_code, 403)

    def test_usuario_role_can_register_baixa_avaria(self):
        """Valida que o papel USUARIO pode registrar baixa pontual de estoque por motivo de avaria/perda (RN-09)."""
        self.client.login(username='usuario_cat', password='password123')
        response = self.client.post(reverse('produto_baixa_avaria', kwargs={'pk': self.produto.pk}), {
            'quantidade': 2,
            'tipo_baixa': TipoAjusteEstoqueEnum.SAIDA_AVARIA,
            'justificativa': 'Tela trincada durante o manuseio no galpão'
        })
        self.assertEqual(response.status_code, 302)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 8)  # 10 - 2 = 8

    def test_categoria_delete_blocked_when_products_exist(self):
        """Valida que categoria com produtos vinculados não pode ser excluída."""
        self.client.login(username='admin_cat', password='password123')
        res = self.client.post(reverse('categoria_delete', kwargs={'pk': self.categoria.pk}))
        self.assertEqual(res.status_code, 302)
        # Categoria deve continuar existindo
        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())

    def test_anuncio_marketplace_view_creation(self):
        """Valida a criação de vínculo de anúncio via endpoint da view."""
        self.client.login(username='admin_cat', password='password123')
        res = self.client.post(reverse('anuncio_marketplace_create', kwargs={'pk': self.produto.pk}), {
            'conta_marketplace': self.conta_ml.pk,
            'item_id_externo': 'MLB_NOVO_123',
            'status_anuncio': 'ativo',
            'preco_sincronizado': '5000.00'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(AnuncioMarketplace.objects.filter(item_id_externo='MLB_NOVO_123').exists())
