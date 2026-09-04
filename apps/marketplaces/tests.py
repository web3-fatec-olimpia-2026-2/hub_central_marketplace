# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import IntegrityError

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.marketplaces.models import ContaMarketplace, LogSincronizacao
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from apps.marketplaces.connectors.factory import get_connector_for_conta
from apps.marketplaces.connectors.mercadolivre import MercadoLivreConnector
from apps.marketplaces.connectors.shopee import ShopeeConnector
from apps.marketplaces.connectors.magalu import MagaluConnector


class MarketplacesHubTestCase(TestCase):
    """
    O QUE FAZ: Suíte de testes automatizados para o Hub Multicanal de Marketplaces e Conectores.
    POR QUE FAZ: Valida o isolamento multi-contas por loja, execução de conectores desacoplados e clamping de estoque.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Isolamento horizontal de credenciais e contas.
    """

    def setUp(self):
        self.loja = Loja.objects.create(
            nome="Loja Matriz",
            slug="loja-matriz",
            cnpj="33.333.333/0001-33"
        )
        self.loja.garantir_modulos_padrao()

        self.user_admin = User.objects.create_user(username='admin_loja', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        # 1. Conta Mercado Livre
        self.conta_meli = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Oficial",
            access_token="APP_USR_TEST_TOKEN",
            refresh_token="REFRESH_TEST_TOKEN",
            seller_id_externo="123456789"
        )

        # 2. Conta Shopee
        self.conta_shopee = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.SHOPEE,
            apelido_conta="Shopee Oficial",
            access_token="SHOPEE_TOKEN",
            seller_id_externo="987654"
        )

    def test_multi_account_unique_constraint(self):
        """Valida que não é permitido duplicar o mesmo canal e seller_id na mesma loja."""
        with self.assertRaises(IntegrityError):
            ContaMarketplace.objects.create(
                loja=self.loja,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                apelido_conta="ML Duplicado",
                seller_id_externo="123456789"
            )

    def test_connector_factory_resolution(self):
        """Valida que o Factory resolve o conector correto para cada conta."""
        connector_meli = get_connector_for_conta(self.conta_meli)
        self.assertIsInstance(connector_meli, MercadoLivreConnector)
        self.assertEqual(connector_meli.canal_nome, CanalMarketplaceEnum.MERCADOLIVRE)

        connector_shopee = get_connector_for_conta(self.conta_shopee)
        self.assertIsInstance(connector_shopee, ShopeeConnector)
        self.assertEqual(connector_shopee.canal_nome, CanalMarketplaceEnum.SHOPEE)

    @patch('requests.put')
    def test_mercadolivre_connector_price_update_and_logging(self, mock_put):
        """Valida o envio de PUT /items/{id} e gravação de telemetria no conector do Mercado Livre."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'MLB12345678', 'price': 99.90}
        mock_put.return_value = mock_response

        connector = get_connector_for_conta(self.conta_meli)
        sucesso, msg, log = connector.atualizar_preco("MLB12345678", Decimal('99.90'), usuario=self.user_admin)

        self.assertTrue(sucesso)
        self.assertIsNotNone(log)
        self.assertEqual(log.status_http, 200)
        self.assertTrue(log.sucesso)
        self.assertEqual(log.item_id_externo, "MLB12345678")
        self.assertEqual(log.evento, EventoAuditoriaEnum.SYNC_PRECO)

    @patch('requests.put')
    def test_mercadolivre_connector_stock_clamping(self, mock_put):
        """Valida que o conector aplica clamping max(0, estoque) para saldos negativos (RN-06)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'MLB12345678', 'available_quantity': 0}
        mock_put.return_value = mock_response

        connector = get_connector_for_conta(self.conta_meli)
        # Tenta enviar saldo negativo (-5)
        sucesso, msg, log = connector.atualizar_estoque("MLB12345678", -5, usuario=self.user_admin)

        self.assertTrue(sucesso)
        # Verifica que o payload enviado conteve 0 e não -5
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        self.assertEqual(kwargs['json']['available_quantity'], 0)

    def test_shopee_connector_stub_execution(self):
        """Valida a execução do conector didático da Shopee."""
        connector = get_connector_for_conta(self.conta_shopee)
        sucesso, msg, log = connector.atualizar_preco("SHOPEE_ITEM_1", Decimal('150.00'), usuario=self.user_admin)
        self.assertTrue(sucesso)
        self.assertEqual(log.canal, CanalMarketplaceEnum.SHOPEE)

    def test_magalu_and_amazon_connectors(self):
        """Valida a execução dos conectores de Magalu e Amazon."""
        conta_magalu = ContaMarketplace.objects.create(
            loja=self.loja, canal=CanalMarketplaceEnum.MAGALU, apelido_conta="Magalu Loja", access_token="MAG_TOKEN"
        )
        conn_mag = get_connector_for_conta(conta_magalu)
        suc_mag, _, log_mag = conn_mag.atualizar_estoque("SKU_MAG_1", 10)
        self.assertTrue(suc_mag)
        self.assertEqual(log_mag.canal, CanalMarketplaceEnum.MAGALU)

        conta_amz = ContaMarketplace.objects.create(
            loja=self.loja, canal=CanalMarketplaceEnum.AMAZON, apelido_conta="Amazon Loja", access_token="AMZ_TOKEN"
        )
        conn_amz = get_connector_for_conta(conta_amz)
        suc_amz, _, log_amz = conn_amz.atualizar_preco("B00123", Decimal('89.90'))
        self.assertTrue(suc_amz)
        self.assertEqual(log_amz.canal, CanalMarketplaceEnum.AMAZON)

    def test_conta_marketplace_views_and_test_connection(self):
        """Valida a criação e teste de conexão de contas de marketplace via views."""
        client = Client()
        client.login(username='admin_loja', password='password123')

        # Teste de conexão via view
        res_test = client.post(reverse('conta_marketplace_testar', kwargs={'pk': self.conta_shopee.pk}))
        self.assertEqual(res_test.status_code, 302)

        # Listagem de canais
        res_list = client.get(reverse('canal_list'))
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, "ML Oficial")
        self.assertContains(res_list, "Shopee Oficial")

    def test_connectors_publicar_anuncio_contracts(self):
        """Valida que todos os conectores suportam publicar_anuncio() gerando telemetria e IDs externos (RF-04)."""
        produto_dict = {
            'nome': 'Teclado Mecânico RGB',
            'sku': 'KB-RGB-01',
            'preco': Decimal('299.90'),
            'estoque': 25,
        }

        # 1. Mercado Livre
        conn_ml = get_connector_for_conta(self.conta_meli)
        suc_ml, msg_ml, ret_ml, log_ml = conn_ml.publicar_anuncio(
            produto_dict, conta=self.conta_meli, dados_extras={'listing_type_id': 'gold_special', 'category_id': 'MLB3530'}
        )
        self.assertTrue(suc_ml)
        self.assertTrue(ret_ml['item_id_externo'].startswith('MLB'))
        self.assertEqual(log_ml.evento, EventoAuditoriaEnum.PUBLICACAO_ANUNCIO)

        # 2. Shopee
        conn_shopee = get_connector_for_conta(self.conta_shopee)
        suc_shp, msg_shp, ret_shp, log_shp = conn_shopee.publicar_anuncio(
            produto_dict, conta=self.conta_shopee
        )
        self.assertTrue(suc_shp)
        self.assertTrue(ret_shp['item_id_externo'].startswith('SHP'))
        self.assertEqual(log_shp.canal, CanalMarketplaceEnum.SHOPEE)

        # 3. Magalu
        conta_magalu = ContaMarketplace.objects.create(
            loja=self.loja, canal=CanalMarketplaceEnum.MAGALU, apelido_conta="Magalu Loja", access_token="MAG_TOKEN"
        )
        conn_mag = get_connector_for_conta(conta_magalu)
        suc_mag, msg_mag, ret_mag, log_mag = conn_mag.publicar_anuncio(
            produto_dict, conta=conta_magalu
        )
        self.assertTrue(suc_mag)
        self.assertTrue(ret_mag['item_id_externo'].startswith('MGL'))
        self.assertEqual(log_mag.canal, CanalMarketplaceEnum.MAGALU)

    def test_encrypted_text_field_encryption_at_rest(self):
        """Valida que tokens são cifrados com Fernet no banco e decifrados transparentemente pelo ORM."""
        from django.db import connection

        raw_secret_token = "APP_USR_SUPER_SECRET_OAUTH_TOKEN_XYZ_12345"
        conta = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="Conta Criptografada",
            access_token=raw_secret_token,
            seller_id_externo="999888"
        )

        # 1. Consulta SQL direta na coluna do banco para verificar que NÃO está em texto claro
        with connection.cursor() as cursor:
            cursor.execute("SELECT access_token FROM marketplaces_contamarketplace WHERE id = %s", [conta.id])
            db_value = cursor.fetchone()[0]

        self.assertNotEqual(db_value, raw_secret_token)
        self.assertTrue(db_value.startswith("gAAAAA"), "O valor salvo no banco deve ser um ciphertext Fernet")

        # 2. Leitura via ORM do Django deve retornar o valor original decifrado
        conta_loaded = ContaMarketplace.objects.get(id=conta.id)
        self.assertEqual(conta_loaded.access_token, raw_secret_token)

    def test_mercadolivre_gerar_url_autorizacao_dynamic_settings(self):
        """Valida que a URL de autorização OAuth é construída dinamicamente sem hardcode."""
        url = MercadoLivreConnector.gerar_url_autorizacao(state="conta_42")
        self.assertIn("https://auth.mercadolivre.com.br/authorization?", url)
        self.assertIn("response_type=code", url)
        self.assertIn("client_id=", url)
        self.assertIn("redirect_uri=", url)
        self.assertIn("state=conta_42", url)

    def test_mercadolivre_callback_view_success_and_logging(self):
        """Valida a view de callback do OAuth 2.0 salvando tokens e renderizando template de sucesso."""
        client = Client()
        res = client.get(reverse('mercadolivre_callback'), {
            'code': 'TEST_MOCK_CODE_123',
            'state': f'conta_{self.conta_meli.pk}'
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Mercado Livre Conectado com Sucesso!")
        self.assertContains(res, "ML Oficial")

        self.conta_meli.refresh_from_db()
        self.assertTrue(self.conta_meli.access_token)
        self.assertTrue(self.conta_meli.refresh_token)
        self.assertIsNotNone(self.conta_meli.token_expira_em)
        self.assertIsNotNone(self.conta_meli.ultima_sincronizacao)

        # Log de sincronização criado
        self.assertTrue(
            LogSincronizacao.objects.filter(
                conta_marketplace=self.conta_meli, evento=EventoAuditoriaEnum.CRIACAO_CONTA
            ).exists()
        )

    def test_conta_marketplace_desconectar_view(self):
        """Valida a ação de desconectar e limpar tokens de uma conta com segurança."""
        client = Client()
        client.login(username='admin_loja', password='password123')

        res = client.post(reverse('conta_marketplace_desconectar', kwargs={'pk': self.conta_meli.pk}))
        self.assertEqual(res.status_code, 302)

        self.conta_meli.refresh_from_db()
        self.assertIsNone(self.conta_meli.access_token)
        self.assertIsNone(self.conta_meli.refresh_token)
        self.assertIsNone(self.conta_meli.token_expira_em)
        self.assertIsNone(self.conta_meli.seller_id_externo)

    def test_mock_toggle_mercadolivre_simulation(self):
        """Valida o comportamento de simulação mock ativa (200) vs desativada (401) no Mercado Livre."""
        conta_mock = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Mock Teste",
            is_mock=True,
            seller_id_externo="86176658"
        )
        conn = get_connector_for_conta(conta_mock)

        # 1. Simulação ATIVA (padrão)
        with patch('apps.mockar_dados.services.is_simular_rotas_mock_ativo', return_value=True):
            sucesso, msg, _ = conn.autenticar()
            self.assertTrue(sucesso)
            self.assertIn("Conexão simulada com sucesso", msg)
            conta_mock.refresh_from_db()
            self.assertIsNotNone(conta_mock.ultima_sincronizacao)
            timestamp_anterior = conta_mock.ultima_sincronizacao

            # Telemetria 200
            ultimo_log = LogSincronizacao.objects.filter(conta_marketplace=conta_mock).latest('criado_em')
            self.assertEqual(ultimo_log.status_http, 200)
            self.assertTrue(ultimo_log.sucesso)

        # 2. Simulação DESATIVADA (recusa legítima 401 sem alterar timestamp)
        with patch('apps.mockar_dados.services.is_simular_rotas_mock_ativo', return_value=False):
            sucesso, msg, _ = conn.autenticar()
            self.assertFalse(sucesso)
            self.assertIn("401", msg)
            conta_mock.refresh_from_db()
            self.assertEqual(conta_mock.ultima_sincronizacao, timestamp_anterior)

            # Telemetria 401
            ultimo_log = LogSincronizacao.objects.filter(conta_marketplace=conta_mock).latest('criado_em')
            self.assertEqual(ultimo_log.status_http, 401)
            self.assertFalse(ultimo_log.sucesso)
            self.assertIn("Não autorizado", ultimo_log.mensagem_erro)

    def test_mock_toggle_magalu_and_shopee_simulation(self):
        """Valida o comportamento de alternância mock em Magalu e Shopee."""
        conta_magalu_mock = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MAGALU,
            apelido_conta="Magalu Mock Teste",
            is_mock=True
        )
        conta_shopee_mock = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.SHOPEE,
            apelido_conta="Shopee Mock Teste",
            is_mock=True
        )

        conn_mag = get_connector_for_conta(conta_magalu_mock)
        conn_shp = get_connector_for_conta(conta_shopee_mock)

        # Simulação ATIVA
        with patch('apps.mockar_dados.services.is_simular_rotas_mock_ativo', return_value=True):
            suc_mag, msg_mag, _ = conn_mag.autenticar()
            suc_shp, msg_shp, _ = conn_shp.autenticar()
            self.assertTrue(suc_mag)
            self.assertTrue(suc_shp)
            conta_magalu_mock.refresh_from_db()
            conta_shopee_mock.refresh_from_db()
            self.assertIsNotNone(conta_magalu_mock.ultima_sincronizacao)
            self.assertIsNotNone(conta_shopee_mock.ultima_sincronizacao)

        # Simulação DESATIVADA -> 401
        with patch('apps.mockar_dados.services.is_simular_rotas_mock_ativo', return_value=False):
            suc_mag, msg_mag, _ = conn_mag.autenticar()
            suc_shp, msg_shp, _ = conn_shp.autenticar()
            self.assertFalse(suc_mag)
            self.assertFalse(suc_shp)
            self.assertIn("401", msg_mag)
            self.assertIn("401", msg_shp)

    def test_reconnect_button_visibility_rules(self):
        """Valida que o botão Reconectar Conta é exibido estritamente quando ultima_sincronizacao não é nula."""
        client = Client()
        client.login(username='admin_loja', password='password123')

        # 1. Conta ML sem sincronização prévia
        conta_nova_ml = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Sem Conexao",
            ultima_sincronizacao=None
        )

        res_list = client.get(reverse('canal_list'))
        self.assertEqual(res_list.status_code, 200)
        # Não deve haver botão de reconectar para a conta sem sincronização
        res_form = client.get(reverse('conta_marketplace_update', kwargs={'pk': conta_nova_ml.pk}))
        self.assertEqual(res_form.status_code, 200)
        self.assertNotContains(res_form, "Reconectar Conta")
        self.assertContains(res_form, "Conectar com Mercado Livre")

        # 2. Agora marcamos ultima_sincronizacao
        from django.utils import timezone
        conta_nova_ml.ultima_sincronizacao = timezone.now()
        conta_nova_ml.save()

        res_form_apos = client.get(reverse('conta_marketplace_update', kwargs={'pk': conta_nova_ml.pk}))
        self.assertEqual(res_form_apos.status_code, 200)
        self.assertContains(res_form_apos, "Reconectar Conta")


