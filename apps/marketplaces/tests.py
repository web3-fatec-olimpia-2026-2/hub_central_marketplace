# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import IntegrityError

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.marketplaces.models import ContaMarketplace, LogSincronizacao, WebhookEventLog, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum, WebhookStatusEnum
from apps.marketplaces.services import MercadoLivreWebhookService
from apps.marketplaces.connectors.factory import get_connector_for_conta
from apps.marketplaces.connectors.mercadolivre import MercadoLivreConnector
from apps.marketplaces.connectors.shopee import ShopeeConnector
from apps.marketplaces.connectors.magalu import MagaluConnector
from apps.catalogo.models import Produto, Categoria
from apps.anuncios.models import Anuncio, AnuncioComposicao
from apps.pedidos.models import PedidoVenda, ItemPedidoVenda, Pedido, ItemPedido
from apps.pedidos.enums import StatusPedidoEnum


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
            canal=CanalMarketplaceEnum.AMAZON,
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
        loja_mock = Loja.objects.create(
            nome="Loja Mock Teste",
            slug="loja-mock-teste",
            cnpj="44.444.444/0001-44"
        )
        loja_mock.garantir_modulos_padrao()

        conta_mock = ContaMarketplace.objects.create(
            loja=loja_mock,
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
        self.conta_shopee.is_mock = True
        self.conta_shopee.save()
        conta_shopee_mock = self.conta_shopee

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
        loja_recon = Loja.objects.create(
            nome="Loja Reconexao",
            slug="loja-reconexao",
            cnpj="55.555.555/0001-55"
        )
        loja_recon.garantir_modulos_padrao()
        user_recon = User.objects.create_user(username='admin_recon', password='password123')
        PerfilUsuario.objects.create(usuario=user_recon, papel=PapelUsuarioEnum.ADMIN, loja=loja_recon)

        client = Client()
        client.login(username='admin_recon', password='password123')

        # 1. Conta ML sem sincronização prévia
        conta_nova_ml = ContaMarketplace.objects.create(
            loja=loja_recon,
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

    def test_bloqueio_duplicidade_loja_canal(self):
        """Valida que uma mesma loja não pode ter mais de uma conta para o mesmo canal de marketplace."""
        from django.core.exceptions import ValidationError
        # self.conta_meli já existe para self.loja com MERCADOLIVRE
        conta_duplicada = ContaMarketplace(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="Outra Conta ML"
        )
        with self.assertRaises(ValidationError) as ctx:
            conta_duplicada.full_clean()
        self.assertIn('canal', ctx.exception.message_dict)

        with self.assertRaises(IntegrityError):
            ContaMarketplace.objects.create(
                loja=self.loja,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                apelido_conta="Outra Conta ML DB"
            )

    def test_bloqueio_duplicidade_canal_seller_id_externo_entre_lojas(self):
        """Valida que um mesmo seller_id_externo no mesmo canal não pode ser reaproveitado por outra loja."""
        from django.core.exceptions import ValidationError
        outra_loja = Loja.objects.create(
            nome="Loja Concorrente",
            slug="loja-concorrente",
            cnpj="66.666.666/0001-66"
        )
        # self.conta_meli já usa seller_id_externo="123456789" no MERCADOLIVRE
        conta_conflito = ContaMarketplace(
            loja=outra_loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Concorrente",
            seller_id_externo="123456789"
        )
        with self.assertRaises(ValidationError) as ctx:
            conta_conflito.full_clean()
        self.assertIn('seller_id_externo', ctx.exception.message_dict)

        with self.assertRaises(IntegrityError):
            ContaMarketplace.objects.create(
                loja=outra_loja,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                apelido_conta="ML Concorrente DB",
                seller_id_externo="123456789"
            )

    def test_bloqueio_duplicidade_loja_apelido_conta(self):
        """Valida que o apelido da conta deve ser único dentro da mesma loja."""
        from django.core.exceptions import ValidationError
        # self.conta_meli tem apelido "ML Oficial"
        conta_mesmo_apelido = ContaMarketplace(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MAGALU,
            apelido_conta="ML Oficial"
        )
        with self.assertRaises(ValidationError) as ctx:
            conta_mesmo_apelido.full_clean()
        self.assertIn('apelido_conta', ctx.exception.message_dict)

        with self.assertRaises(IntegrityError):
            ContaMarketplace.objects.create(
                loja=self.loja,
                canal=CanalMarketplaceEnum.MAGALU,
                apelido_conta="ML Oficial"
            )

    def test_imutabilidade_loja_e_canal_na_edicao_model(self):
        """Valida que alterar loja ou canal de uma conta existente gera ValidationError no modelo."""
        from django.core.exceptions import ValidationError
        outra_loja = Loja.objects.create(
            nome="Loja Destino",
            slug="loja-destino",
            cnpj="77.777.777/0001-77"
        )

        # 1. Tentativa de alterar a Loja
        self.conta_meli.loja = outra_loja
        with self.assertRaises(ValidationError) as ctx:
            self.conta_meli.clean()
        self.assertIn('loja', ctx.exception.message_dict)

        with self.assertRaises(ValidationError):
            self.conta_meli.save()

        # Restaura loja e tenta alterar o Canal
        self.conta_meli.refresh_from_db()
        self.conta_meli.canal = CanalMarketplaceEnum.MAGALU
        with self.assertRaises(ValidationError) as ctx:
            self.conta_meli.clean()
        self.assertIn('canal', ctx.exception.message_dict)

        with self.assertRaises(ValidationError):
            self.conta_meli.save()

    def test_imutabilidade_loja_e_canal_no_formulario(self):
        """Valida que o formulário de edição desabilita os campos canal e loja e preserva os valores originais."""
        from apps.marketplaces.forms import ContaMarketplaceForm
        outra_loja = Loja.objects.create(
            nome="Loja Invasora",
            slug="loja-invasora",
            cnpj="88.888.888/0001-88"
        )

        form = ContaMarketplaceForm(instance=self.conta_meli, autor=self.user_admin)
        self.assertTrue(form.fields['canal'].disabled)
        self.assertTrue(form.fields['loja'].disabled)

        # Simula tentativa de envio POST com canal e loja modificados
        post_data = {
            'loja': outra_loja.id,
            'canal': CanalMarketplaceEnum.MAGALU,
            'apelido_conta': 'Novo Apelido Permitido',
            'ativo': True
        }
        form_post = ContaMarketplaceForm(data=post_data, instance=self.conta_meli, autor=self.user_admin)
        self.assertTrue(form_post.is_valid())
        conta_salva = form_post.save()

        # Confirma que canal e loja continuam estritamente os originais
        self.assertEqual(conta_salva.canal, CanalMarketplaceEnum.MERCADOLIVRE)
        self.assertEqual(conta_salva.loja, self.loja)
        self.assertEqual(conta_salva.apelido_conta, 'Novo Apelido Permitido')

    def test_bloqueio_duplicidade_cnpj_loja_mesmos_digitos(self):
        """Valida que cada loja deve ter CNPJ estritamente único, mesmo com variações de pontuação."""
        from django.core.exceptions import ValidationError
        # self.loja possui cnpj="33.333.333/0001-33"
        loja_duplicada = Loja(
            nome="Loja Clone CNPJ",
            cnpj="33333333000133"
        )
        with self.assertRaises(ValidationError) as ctx:
            loja_duplicada.clean()
        self.assertIn('cnpj', ctx.exception.message_dict)

    def test_conta_get_connector_strategy_adapter(self):
        """Valida que conta.get_connector() resolve o Adapter concreto adequado a cada canal."""
        conn_meli = self.conta_meli.get_connector()
        self.assertIsInstance(conn_meli, MercadoLivreConnector)
        self.assertEqual(conn_meli.canal_nome, CanalMarketplaceEnum.MERCADOLIVRE)
        self.assertEqual(conn_meli.conta, self.conta_meli)

        conn_shopee = self.conta_shopee.get_connector()
        self.assertIsInstance(conn_shopee, ShopeeConnector)
        self.assertEqual(conn_shopee.canal_nome, CanalMarketplaceEnum.SHOPEE)

    def test_get_authorization_url_generates_correct_query(self):
        """Valida geração de URL com parâmetros client_id, redirect_uri e state."""
        connector = self.conta_meli.get_connector()
        url = connector.get_authorization_url(state="csrf_secure_token_123")
        self.assertIn("https://auth.mercadolivre.com.br/authorization?", url)
        self.assertIn("response_type=code", url)
        self.assertIn("state=csrf_secure_token_123", url)

    def test_get_valid_access_token_valid_and_auto_refresh(self):
        """Valida retorno direto de token válido e auto-refresh transparente quando faltam < 10 min."""
        from django.utils import timezone
        import datetime

        now = timezone.now()
        connector = self.conta_meli.get_connector()

        # Caso 1: Token válido por mais 2 horas (sem auto-refresh)
        self.conta_meli.token_expira_em = now + datetime.timedelta(hours=2)
        self.conta_meli.save(update_fields=['token_expira_em'])

        with patch.object(connector, 'refresh_credentials') as mock_refresh:
            token = connector.get_valid_access_token()
            self.assertEqual(token, "APP_USR_TEST_TOKEN")
            mock_refresh.assert_not_called()

        # Caso 2: Token expirando em 5 minutos (auto-refresh transparente deve ser disparado)
        self.conta_meli.token_expira_em = now + datetime.timedelta(minutes=5)
        self.conta_meli.save(update_fields=['token_expira_em'])

        token = connector.get_valid_access_token()
        self.assertTrue(token)
        self.conta_meli.refresh_from_db()
        # Após o refresh, a expiração deve ser em ~6 horas
        self.assertGreater(self.conta_meli.token_expira_em, now + datetime.timedelta(hours=5))

    def test_refresh_credentials_pessimistic_lock_and_double_check(self):
        """Valida renovação de credenciais e o mecanismo de double-checked locking contra race conditions."""
        from django.utils import timezone
        import datetime

        connector = self.conta_meli.get_connector()
        now = timezone.now()
        # Força expiração
        self.conta_meli.token_expira_em = now - datetime.timedelta(minutes=1)
        self.conta_meli.save(update_fields=['token_expira_em'])

        res = connector.refresh_credentials()
        self.assertTrue(res['sucesso'])
        self.assertIn('access_token', res)

        self.conta_meli.refresh_from_db()
        self.assertTrue(self.conta_meli.access_token.startswith('APP_USR_MOCK_REFRESHED_'))
        self.assertTrue(self.conta_meli.refresh_token.startswith('TG_MOCK_REFRESHED_'))

        # Chamada subsequente imediata: double-checked locking deve reaproveitar
        res2 = connector.refresh_credentials()
        self.assertTrue(res2['sucesso'])
        self.assertTrue(res2.get('reaproveitado'))

    @patch('requests.post')
    def test_refresh_credentials_invalid_grant_deactivates_account(self, mock_post):
        """Valida que o erro invalid_grant da API do Meli inativa a conta (ativo=False) e grava log."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Error validating grant. Your authorization code or refresh token may be expired or it was already used",
            "status": 400
        }
        mock_post.return_value = mock_response

        # Força token não-mock para disparar chamada HTTP externa simulada
        self.conta_meli.refresh_token = "REAL_REFRESH_TOKEN_ABC123"
        self.conta_meli.ativo = True
        self.conta_meli.save(update_fields=['refresh_token', 'ativo'])

        with patch.object(MercadoLivreConnector, '_get_client_secret', return_value='valid_secret_123'):
            connector = self.conta_meli.get_connector()
            res = connector.refresh_credentials()

        self.assertFalse(res['sucesso'])
        self.assertEqual(res['error'], 'invalid_grant')

        self.conta_meli.refresh_from_db()
        self.assertFalse(self.conta_meli.ativo, "A conta deve ser inativada após invalid_grant")

        log = LogSincronizacao.objects.filter(
            conta_marketplace=self.conta_meli, evento=EventoAuditoriaEnum.REFRESH_TOKEN
        ).latest('criado_em')
        self.assertFalse(log.sucesso)
        self.assertEqual(log.status_http, 400)

    @patch('requests.post')
    def test_refresh_credentials_operator_error(self, mock_post):
        """Valida que status 403 com invalid_operator_user_id orienta sobre conta titular."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": "invalid_operator_user_id",
            "message": "Operator user is not allowed"
        }
        mock_post.return_value = mock_response

        self.conta_meli.refresh_token = "REAL_REFRESH_TOKEN_XYZ"
        self.conta_meli.save(update_fields=['refresh_token'])

        with patch.object(MercadoLivreConnector, '_get_client_secret', return_value='valid_secret_123'):
            connector = self.conta_meli.get_connector()
            res = connector.refresh_credentials()

        self.assertFalse(res['sucesso'])
        self.assertEqual(res['status_code'], 403)
        self.assertIn("titular/administradora", res['mensagem'])

    @patch('requests.post')
    def test_refresh_credentials_rate_limited_retry(self, mock_post):
        """Valida retry sob HTTP 429 local_rate_limited com posterior sucesso 200."""
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.json.return_value = {"error": "local_rate_limited", "message": "Too many requests"}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "access_token": "APP_USR_NEW_TOKEN_AFTER_RETRY",
            "refresh_token": "TG_NEW_REFRESH_AFTER_RETRY",
            "expires_in": 21600
        }
        mock_post.side_effect = [resp_429, resp_200]

        self.conta_meli.refresh_token = "REAL_REFRESH_TOKEN_RATE"
        self.conta_meli.save(update_fields=['refresh_token'])

        with patch.object(MercadoLivreConnector, '_get_client_secret', return_value='valid_secret_123'):
            with patch('time.sleep', return_value=None):
                connector = self.conta_meli.get_connector()
                res = connector.refresh_credentials()

        self.assertTrue(res['sucesso'])
        self.assertEqual(res['access_token'], "APP_USR_NEW_TOKEN_AFTER_RETRY")

    @patch('requests.request')
    def test_connector_request_bearer_and_retry_on_401(self, mock_request):
        """Valida que connector.request() injeta Authorization: Bearer e reautentica sob 401."""
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.text = "Unauthorized"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"status": "ok", "user": "test"}

        mock_request.side_effect = [resp_401, resp_200]

        connector = self.conta_meli.get_connector()
        with patch.object(connector, 'refresh_credentials', return_value={'sucesso': True}):
            res = connector.request('GET', '/users/me')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(mock_request.call_count, 2)
        # Confirma cabeçalho Authorization enviado
        first_call_headers = mock_request.call_args_list[0][1]['headers']
        self.assertIn('Authorization', first_call_headers)
        self.assertTrue(first_call_headers['Authorization'].startswith('Bearer '))

    @patch.object(MercadoLivreConnector, 'request')
    def test_test_connection_active_validation_updates_sincronizacao(self, mock_request):
        """Valida que test_connection() consulta /users/me, atualiza ultima_sincronizacao e seller_id."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 88776655,
            "nickname": "TechZone Oficial",
            "site_id": "MLB"
        }
        mock_request.return_value = mock_resp

        self.conta_meli.seller_id_externo = None
        self.conta_meli.ultima_sincronizacao = None
        self.conta_meli.save(update_fields=['seller_id_externo', 'ultima_sincronizacao'])

        connector = self.conta_meli.get_connector()
        res = connector.test_connection()

        self.assertTrue(res['sucesso'])
        self.assertEqual(res['nickname'], "TechZone Oficial")
        self.assertEqual(res['id'], "88776655")

        self.conta_meli.refresh_from_db()
        self.assertEqual(self.conta_meli.seller_id_externo, "88776655")
        self.assertIsNotNone(self.conta_meli.ultima_sincronizacao)

    def test_oauth_csrf_ephemeral_state_validation(self):
        """Valida a proteção contra CSRF usando state randômico em sessão na autorização e callback."""
        client = Client()
        client.login(username='admin_loja', password='password123')

        # 1. Autorização gera state randômico na sessão
        res_auth = client.get(reverse('mercadolivre_autorizar', kwargs={'pk': self.conta_meli.pk}))
        self.assertEqual(res_auth.status_code, 302)
        session_state = client.session.get('oauth_state')
        self.assertTrue(session_state)
        self.assertEqual(client.session.get('oauth_conta_id'), self.conta_meli.pk)

        # 2. Callback com state forjado (CSRF) deve ser rejeitado
        res_forged = client.get(reverse('mercadolivre_callback'), {
            'code': 'TEST_CODE',
            'state': 'forged_fake_state'
        })
        self.assertEqual(res_forged.status_code, 302)

        # 3. Callback com o state correto da sessão deve ser aceito
        res_valid = client.get(reverse('mercadolivre_callback'), {
            'code': 'TEST_MOCK_CODE_VALID',
            'state': session_state
        })
        self.assertEqual(res_valid.status_code, 200)
        self.assertContains(res_valid, "Mercado Livre Conectado com Sucesso!")

        # Confirma que o state foi consumido da sessão (single use)
        self.assertNotIn('oauth_state', client.session)

    def test_reconexao_mesma_conta_sucesso_sem_conflito(self):
        """Valida a reconexão legítima da mesma conta sem disparar falsa colisão consigo mesma."""
        client = Client()
        client.login(username='admin_loja', password='password123')

        # 1. Inicia fluxo de autorização/reconexão a partir do card existente
        res_auth = client.get(reverse('mercadolivre_autorizar', kwargs={'pk': self.conta_meli.pk}))
        self.assertEqual(res_auth.status_code, 302)
        session_state = client.session.get('oauth_state')
        self.assertEqual(client.session.get('oauth_conta_id'), self.conta_meli.pk)

        # 2. Callback retorna o mesmo seller_id da conta de origem
        res_callback = client.get(reverse('mercadolivre_callback'), {
            'code': f'TEST_SELLER_{self.conta_meli.seller_id_externo}',
            'state': session_state
        })
        self.assertEqual(res_callback.status_code, 200)
        self.assertContains(res_callback, "Mercado Livre Conectado com Sucesso!")

        # 3. Confirma tokens atualizados sem colisão
        self.conta_meli.refresh_from_db()
        self.assertEqual(self.conta_meli.seller_id_externo, "123456789")
        self.assertTrue(self.conta_meli.access_token.startswith("APP_USR_MOCK_TOKEN_"))

    def test_reconexao_sessao_trocada_bloqueio_com_mensagem_amigavel(self):
        """Valida que autorizar com sessão trocada (seller ID de outro card) bloqueia com mensagem amigável."""
        # Cria uma segunda conta (pertencente a outra loja/card) com outro seller_id
        loja_secundaria = Loja.objects.create(
            nome="Loja Filial",
            slug="loja-filial",
            cnpj="44.444.444/0001-44"
        )
        conta_outro_card = ContaMarketplace.objects.create(
            loja=loja_secundaria,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Outro Card",
            access_token="TOKEN_CARD_2",
            refresh_token="REFRESH_CARD_2",
            seller_id_externo="999888777"
        )

        old_token = self.conta_meli.access_token
        old_refresh = self.conta_meli.refresh_token

        client = Client()
        client.login(username='admin_loja', password='password123')

        # 1. Inicia reconexão no card 1
        client.get(reverse('mercadolivre_autorizar', kwargs={'pk': self.conta_meli.pk}))
        session_state = client.session.get('oauth_state')
        self.assertEqual(client.session.get('oauth_conta_id'), self.conta_meli.pk)

        # 2. Callback retorna autorização pertencente ao card 2 (sessão trocada)
        res_callback = client.get(reverse('mercadolivre_callback'), {
            'code': 'TEST_SELLER_999888777',
            'state': session_state
        }, follow=True)

        self.assertRedirects(res_callback, reverse('canal_list'))

        # 3. Valida a mensagem amigável exata
        mensagem_esperada = (
            "Falha na reconexão: Você autorizou com a conta do Mercado Livre (ID: 999888777), "
            "que já pertence a outro card no sistema. Faça logout no Mercado Livre e repita o processo com a conta correta."
        )
        mensagens = [m.message for m in res_callback.context['messages']]
        self.assertIn(mensagem_esperada, mensagens)

        # 4. Confirma que os tokens do card de origem NÃO foram corrompidos/sobrescritos
        self.conta_meli.refresh_from_db()
        self.assertEqual(self.conta_meli.access_token, old_token)
        self.assertEqual(self.conta_meli.refresh_token, old_refresh)
        self.assertEqual(self.conta_meli.seller_id_externo, "123456789")

    def test_conta_marketplace_create_view_clears_oauth_conta_id_session(self):
        """Valida que acessar a tela de 'Conectar Nova Conta' limpa oauth_conta_id remanescente na sessão."""
        client = Client()
        client.login(username='admin_loja', password='password123')

        session = client.session
        session['oauth_conta_id'] = 999
        session.save()

        res = client.get(reverse('conta_marketplace_create'))
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('oauth_conta_id', client.session)


class MercadoLivreWebhookTestCase(TestCase):
    """
    O QUE FAZ: Suíte de testes para o endpoint de webhooks do Mercado Livre (/marketplaces/webhooks/mercadolivre/).
    POR QUE FAZ: Valida idempotência estrita, baixa atômica de estoque (unitários e kits), tratamento de erros e integridade HTTP.
    """

    def setUp(self):
        self.client = Client()
        self.url = reverse('mercadolivre_webhook')

        self.loja = Loja.objects.create(
            nome="Loja Webhook Test",
            slug="loja-webhook-test",
            cnpj="44.444.444/0001-44"
        )
        self.loja.garantir_modulos_padrao()

        self.user = User.objects.create_user(username='admin_webhook', password='password123')
        PerfilUsuario.objects.create(usuario=self.user, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.conta_meli = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Webhooks",
            access_token="APP_USR_MOCK_TOKEN",
            refresh_token="REFRESH_MOCK",
            seller_id_externo="777888999",
            is_mock=True
        )

        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Geral",
            slug="geral"
        )

        # Produto Unitário
        self.produto_unit = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SKU-UNIT-01",
            nome="Produto Teste Unitário",
            preco=Decimal('50.00'),
            estoque=10
        )
        self.anuncio_unit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB1001001",
            titulo="Anúncio Unitário MLB1001001",
            preco_venda=Decimal('50.00'),
            estoque_publicado=10,
            status='active'
        )
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_unit,
            produto=self.produto_unit,
            quantidade=1
        )

        # Produto para Kit
        self.produto_kit = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SKU-KIT-ITEM",
            nome="Item para Kit de 3 Unidades",
            preco=Decimal('20.00'),
            estoque=30
        )
        self.anuncio_kit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB2002002",
            titulo="Kit 3x Item Especial",
            preco_venda=Decimal('55.00'),
            estoque_publicado=10,
            status='active'
        )
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_kit,
            produto=self.produto_kit,
            quantidade=3
        )

    def test_webhook_url_exact_path(self):
        """Valida que o path da URL resolvida é exatamente /marketplaces/webhooks/mercadolivre/."""
        self.assertEqual(self.url, '/marketplaces/webhooks/mercadolivre/')

    def test_webhook_rejects_disallowed_methods(self):
        """Valida que verbos HTTP diferentes de POST retornam 405 Method Not Allowed."""
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, 405)

        res_put = self.client.put(self.url, data={'topic': 'orders_v2'}, content_type='application/json')
        self.assertEqual(res_put.status_code, 405)

        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, 405)

    def test_webhook_rejects_malformed_and_empty_payload(self):
        """Valida que payloads vazios, inválidos ou sem topic/resource retornam 400 Bad Request."""
        res_empty = self.client.post(self.url, data='', content_type='application/json')
        self.assertEqual(res_empty.status_code, 400)

        res_invalid = self.client.post(self.url, data='{not-a-valid-json', content_type='application/json')
        self.assertEqual(res_invalid.status_code, 400)

        res_missing = self.client.post(self.url, data={'user_id': '777888999'}, content_type='application/json')
        self.assertEqual(res_missing.status_code, 400)

    def test_webhook_ignores_non_orders_topics(self):
        """Valida que tópicos diferentes de orders_v2 retornam 200 OK e são gravados como IGNORADO."""
        payload = {
            'topic': 'items',
            'resource': '/items/MLB1001001',
            'user_id': '777888999',
            'application_id': '12345'
        }
        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ignored')

        # Verifica persistência do log como IGNORADO
        log = WebhookEventLog.objects.filter(resource='/items/MLB1001001').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, WebhookStatusEnum.IGNORADO)
        self.assertEqual(log.topic, 'items')

        # Estoque permanece inalterado
        self.produto_unit.refresh_from_db()
        self.assertEqual(self.produto_unit.estoque, 10)

    def test_webhook_successful_unit_product_stock_deduction(self):
        """Valida baixa atômica de estoque para anúncio unitário com registro de log e auditoria."""
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/2000001234567890',
            'user_id': '777888999',
            'order_data': {
                'id': '2000001234567890',
                'status': 'paid',
                'order_items': [
                    {
                        'item': {'id': 'MLB1001001', 'title': 'Anúncio Unitário'},
                        'quantity': 2,
                        'unit_price': 50.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        # Estoque reduziu de 10 para 8
        self.produto_unit.refresh_from_db()
        self.assertEqual(self.produto_unit.estoque, 8)

        # WebhookEventLog marcado como PROCESSADO
        log = WebhookEventLog.objects.filter(resource='/orders/2000001234567890').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, WebhookStatusEnum.PROCESSADO)
        self.assertIsNotNone(log.processed_at)

        # LogAuditoria gravado com BAIXA_ESTOQUE_VENDA
        auditoria = LogAuditoria.objects.filter(
            evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
            loja=self.loja
        ).first()
        self.assertIsNotNone(auditoria)
        self.assertIn('SKU-UNIT-01', auditoria.detalhes)
        self.assertIn('Saldo anterior: 10 -> Novo saldo: 8', auditoria.detalhes)

    def test_webhook_successful_kit_product_stock_deduction(self):
        """Valida que venda de Kit de 3 unidades abate a quantidade correta (2 kits = 6 itens)."""
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/20000088880001',
            'user_id': '777888999',
            'order_data': {
                'id': '20000088880001',
                'status': 'paid',
                'order_items': [
                    {
                        'item': {'id': 'MLB2002002', 'title': 'Kit 3x Item Especial'},
                        'quantity': 2,
                        'unit_price': 55.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        # 2 kits x 3 un = 6 un. Estoque inicial 30 -> 24
        self.produto_kit.refresh_from_db()
        self.assertEqual(self.produto_kit.estoque, 24)

        log = WebhookEventLog.objects.filter(resource='/orders/20000088880001').first()
        self.assertEqual(log.status, WebhookStatusEnum.PROCESSADO)

    def test_webhook_strict_idempotency_duplicate_notification(self):
        """
        REGRA CRÍTICA DE IDEMPOTÊNCIA:
        Envio de duas notificações idênticas com o mesmo resource.
        Deve debitar o estoque apenas na primeira vez e marcar a segunda como IGNORADO.
        """
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/20000099990001',
            'user_id': '777888999',
            'order_data': {
                'id': '20000099990001',
                'status': 'paid',
                'order_items': [
                    {
                        'item': {'id': 'MLB1001001', 'title': 'Anúncio Unitário'},
                        'quantity': 2,
                        'unit_price': 50.00
                    }
                ]
            }
        }

        # 1ª Requisição: Processamento legítimo
        res1 = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json().get('status'), 'ok')

        self.produto_unit.refresh_from_db()
        self.assertEqual(self.produto_unit.estoque, 8)

        logs = WebhookEventLog.objects.filter(resource='/orders/20000099990001').order_by('received_at')
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].status, WebhookStatusEnum.PROCESSADO)

        # 2ª Requisição: Reenvio da mesma notificação (duplicidade)
        res2 = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json().get('status'), 'ignored')

        # Comprova que o saldo NÃO decresceu novamente
        self.produto_unit.refresh_from_db()
        self.assertEqual(self.produto_unit.estoque, 8)

        # Comprova que um segundo log foi criado marcado como IGNORADO
        logs = WebhookEventLog.objects.filter(resource='/orders/20000099990001').order_by('received_at')
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs[0].status, WebhookStatusEnum.PROCESSADO)
        self.assertEqual(logs[1].status, WebhookStatusEnum.IGNORADO)
        self.assertIn("duplicada", logs[1].error_log.lower())

    @patch.object(MercadoLivreConnector, 'obter_detalhes_pedido')
    def test_webhook_api_failure_registers_error_log(self, mock_obter):
        """Valida que falha na API externa grava log com status ERRO sem alterar estoque."""
        mock_obter.return_value = (False, "Timeout de conexão com o Mercado Livre", {})

        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/20000055550001',
            'user_id': '777888999'
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'error')

        # Estoque inalterado
        self.produto_unit.refresh_from_db()
        self.assertEqual(self.produto_unit.estoque, 10)

        # Log gravado com ERRO
        log = WebhookEventLog.objects.filter(resource='/orders/20000055550001').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, WebhookStatusEnum.ERRO)
        self.assertIn("Timeout de conexão", log.error_log)

    def test_webhook_sale_quantity_2_exact_deduction_and_pedido_created(self):
        """
        CENÁRIO CRÍTICO DE VENDA REAL (MLB2856546762):
        1. Venda de 2 unidades via Webhook abatendo exatamente 2 unidades do saldo físico (5 -> 3).
        2. Criação imediata e atômica da entidade Pedido com comprador, valor total e itens com quantidade 2.
        3. Status do anúncio atualizado para ENVIADO com cota 3 (sem pendência manual no modal).
        4. Pedido registrado e visível na tela /pedidos/.
        """
        # Cria produto com saldo inicial 5 e anúncio MLB2856546762
        produto_mlb = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SKU-MLB-REAL-01",
            nome="Produto Venda Real Mercado Livre",
            preco=Decimal('150.00'),
            estoque=5
        )
        anuncio_mlb = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB2856546762",
            titulo="Anúncio MLB2856546762 Oficial",
            preco_venda=Decimal('150.00'),
            estoque_publicado=5,
            status_sincronizacao='ENVIADO',
            status='active'
        )
        AnuncioComposicao.objects.create(
            anuncio=anuncio_mlb,
            produto=produto_mlb,
            quantidade=1
        )

        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/20000077770002',
            'user_id': '777888999',
            'order_data': {
                'id': '20000077770002',
                'status': 'paid',
                'total_amount': 300.00,
                'shipping_cost': 20.00,
                'buyer': {
                    'id': 998877,
                    'nickname': 'COMPRADOR_ML_TESTE',
                    'first_name': 'Carlos',
                    'last_name': 'Ferreira'
                },
                'order_items': [
                    {
                        'item': {'id': 'MLB2856546762', 'title': 'Anúncio MLB2856546762 Oficial'},
                        'quantity': 2,
                        'unit_price': 150.00
                    }
                ]
            }
        }

        # Dispara o webhook
        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        # 1. Saldo físico abatido exatamente em 2 unidades (5 -> 3)
        produto_mlb.refresh_from_db()
        self.assertEqual(produto_mlb.estoque, 3)

        # 2. Anúncio marcado como ENVIADO com cota 3 (sem ficar PENDENTE para operador)
        anuncio_mlb.refresh_from_db()
        self.assertEqual(anuncio_mlb.status_sincronizacao, 'ENVIADO')
        self.assertEqual(anuncio_mlb.estoque_publicado, 3)
        self.assertFalse(anuncio_mlb.esta_pendente())

        # 3. Entidade Pedido (PedidoVenda) criada com integridade
        pedido = PedidoVenda.objects.filter(pedido_id_externo='20000077770002').first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.numero_pedido, '20000077770002')
        self.assertEqual(pedido.canal, CanalMarketplaceEnum.MERCADOLIVRE)
        self.assertEqual(pedido.conta, self.conta_meli)
        self.assertEqual(pedido.comprador_nome, 'Carlos Ferreira')
        self.assertEqual(pedido.valor_total, Decimal('300.00'))
        self.assertEqual(pedido.status, StatusPedidoEnum.PAGO)
        self.assertFalse(pedido.teve_ruptura_estoque)

        # Itens do pedido vinculados
        self.assertEqual(pedido.itens.count(), 1)
        item = pedido.itens.first()
        self.assertEqual(item.quantidade, 2)
        self.assertEqual(item.produto, produto_mlb)
        self.assertEqual(item.item_id_externo, 'MLB2856546762')
        self.assertEqual(item.preco_unitario, Decimal('150.00'))
        self.assertEqual(item.estoque_anterior, 5)
        self.assertEqual(item.estoque_posterior, 3)
        self.assertTrue(item.estoque_baixado)

        # 4. Verificação de visibilidade na tela /pedidos/
        self.client.force_login(self.user)
        res_pedidos = self.client.get(reverse('pedido_list'))
        self.assertEqual(res_pedidos.status_code, 200)
        self.assertContains(res_pedidos, '20000077770002')
        self.assertContains(res_pedidos, 'Carlos Ferreira')

    def test_webhook_automatic_immediate_sync_no_modal_pending(self):
        """Valida que venda via webhook não inclui o anúncio em anuncios_pendentes_sync no detalhe do produto."""
        produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SKU-AUTO-SYNC",
            nome="Produto Teste Auto Sync",
            preco=Decimal('80.00'),
            estoque=5
        )
        anuncio = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB99881122",
            titulo="Anúncio Auto Sync",
            preco_venda=Decimal('80.00'),
            estoque_publicado=5,
            status_sincronizacao='ENVIADO',
            status='active'
        )
        AnuncioComposicao.objects.create(
            anuncio=anuncio,
            produto=produto,
            quantidade=1
        )

        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/20000033334444',
            'user_id': '777888999',
            'order_data': {
                'id': '20000033334444',
                'status': 'paid',
                'total_amount': 160.00,
                'buyer': {'nickname': 'comprador_auto'},
                'order_items': [
                    {
                        'item': {'id': 'MLB99881122'},
                        'quantity': 2,
                        'unit_price': 80.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)

        # Verifica produto_detail: anúncio NÃO deve constar como pendente no modal
        self.client.force_login(self.user)
        res_prod = self.client.get(reverse('produto_detail', kwargs={'pk': produto.pk}))
        self.assertEqual(res_prod.status_code, 200)
        self.assertNotIn(anuncio, res_prod.context['anuncios_pendentes_sync'])

    @patch.object(MercadoLivreConnector, 'request')
    def test_obter_detalhes_pedido_real_api_call_without_mock_overwrite(self, mock_request):
        """
        Valida que para contas reais (is_mock=False, token real), obter_detalhes_pedido
        chama a API oficial GET /orders/{order_id} sem desvio indevido para fallback mock.
        """
        loja_real = Loja.objects.create(
            nome="Loja Real API",
            slug="loja-real-api",
            cnpj="99.999.999/0001-99"
        )
        loja_real.garantir_modulos_padrao()

        conta_real = ContaMarketplace.objects.create(
            loja=loja_real,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Conta Real",
            access_token="APP_REAL_TOKEN_PROD_12345",
            refresh_token="TG_REAL_REFRESH_12345",
            seller_id_externo="888777666",
            is_mock=False
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'id': '20000011122233',
            'status': 'paid',
            'order_items': [
                {
                    'item': {'id': 'MLB2856546762', 'title': 'Anúncio Real 2x'},
                    'quantity': 2,
                    'unit_price': 150.00
                }
            ],
            'total_amount': 300.00
        }
        mock_request.return_value = mock_resp

        connector = conta_real.get_connector()
        sucesso, msg, dados = connector.obter_detalhes_pedido('/orders/20000011122233')

        self.assertTrue(sucesso)
        mock_request.assert_called_once_with('GET', '/orders/20000011122233')
        self.assertEqual(len(dados.get('order_items', [])), 1)
        self.assertEqual(int(dados['order_items'][0]['quantity']), 2)

    def test_webhook_multitenant_resolucao_correta_duas_contas(self):
        """
        1. Multi-tenant — resolução correta: duas ContaMarketplace cadastradas para canal='mercadolivre'
        com seller_id diferentes em lojas diferentes. Webhook chega para uma delas → PedidoVenda criado
        estritamente na loja/tenant correspondente, nunca na primeira conta do banco.
        """
        loja_2 = Loja.objects.create(
            nome="Loja Filial 2",
            slug="loja-filial-2",
            cnpj="22.222.222/0001-22"
        )
        loja_2.garantir_modulos_padrao()

        cat_2 = Categoria.objects.create(
            loja=loja_2,
            nome="Geral 2",
            slug="geral-2"
        )

        conta_loja_2 = ContaMarketplace.objects.create(
            loja=loja_2,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Filial 2",
            seller_id_externo="seller_filial_999",
            is_mock=True,
            ativo=True
        )

        prod_2 = Produto.objects.create(
            loja=loja_2,
            categoria=cat_2,
            sku="SKU-LOJA-2",
            nome="Produto Loja 2",
            preco=Decimal('100.00'),
            estoque=10
        )
        anc_2 = Anuncio.objects.create(
            conta=conta_loja_2,
            item_id_externo="MLB_LOJA_2",
            titulo="Anuncio Loja 2",
            preco_venda=Decimal('100.00'),
            estoque_publicado=10,
            status='active'
        )
        AnuncioComposicao.objects.create(
            anuncio=anc_2,
            produto=prod_2,
            quantidade=1
        )

        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/200000_TENANT_2',
            'user_id': 'seller_filial_999',
            'order_data': {
                'id': '200000_TENANT_2',
                'status': 'paid',
                'total_amount': 200.00,
                'buyer': {'name': 'Cliente Loja 2'},
                'order_items': [
                    {
                        'item': {'id': 'MLB_LOJA_2', 'title': 'Anuncio Loja 2'},
                        'quantity': 2,
                        'unit_price': 100.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        pedido = PedidoVenda.objects.filter(pedido_id_externo="200000_TENANT_2").first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.loja, loja_2)
        self.assertNotEqual(pedido.loja, self.loja)
        self.assertEqual(pedido.conta_marketplace, conta_loja_2)

        prod_2.refresh_from_db()
        self.assertEqual(prod_2.estoque, 8)

    def test_webhook_conta_nao_localizada_erro_explicito(self):
        """
        2. Conta não localizada: seller_id do payload não corresponde a nenhuma conta cadastrada →
        assertar erro explícito registrado em log, sem crash e sem resolver para uma conta incorreta.
        """
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/99999999',
            'user_id': 'seller_inexistente_99999'
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'error')
        self.assertIn("ContaMarketplace não localizada para o seller_id seller_inexistente_99999", res.json().get('message'))

        log = WebhookEventLog.objects.filter(resource='/orders/99999999').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, WebhookStatusEnum.ERRO)
        self.assertIn("ContaMarketplace não localizada para o seller_id seller_inexistente_99999", log.error_log)
        self.assertEqual(PedidoVenda.objects.filter(pedido_id_externo="99999999").count(), 0)

    def test_webhook_conta_inativa_erro_distinto_de_nao_localizada(self):
        """
        Ajuste 1: Conta existe com seller_id_externo mas está ativo=False →
        assertar mensagem de erro específica de conta inativa, distinta de 'não localizada'.
        """
        loja_inativa = Loja.objects.create(
            nome="Loja Inativa",
            slug="loja-inativa",
            cnpj="11.111.111/0001-11"
        )
        loja_inativa.garantir_modulos_padrao()

        ContaMarketplace.objects.create(
            loja=loja_inativa,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Conta Inativa",
            seller_id_externo="seller_inativo_123",
            is_mock=True,
            ativo=False
        )

        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/88888888',
            'user_id': 'seller_inativo_123'
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'error')
        msg = res.json().get('message')
        self.assertIn("ContaMarketplace encontrada para o seller_id seller_inativo_123, mas está inativa", msg)
        self.assertNotIn("não localizada", msg)

        log = WebhookEventLog.objects.filter(resource='/orders/88888888').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, WebhookStatusEnum.ERRO)
        self.assertIn("mas está inativa", log.error_log)
        self.assertEqual(PedidoVenda.objects.filter(pedido_id_externo="88888888").count(), 0)

    def test_webhook_replay_evento_com_falha_previa_executa_com_sucesso(self):
        """
        3. Replay de evento com falha prévia: evento que abortou antes de persistir (ex: erro de rede prévio)
        deve permitir que o reprocessamento crie o PedidoVenda normalmente.
        """
        WebhookEventLog.objects.create(
            marketplace='mercadolivre',
            topic='orders_v2',
            resource='/orders/200000_REPLAY_1',
            user_id='777888999',
            status=WebhookStatusEnum.ERRO,
            error_log="Falha anterior antes da persistência"
        )

        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/200000_REPLAY_1',
            'user_id': '777888999',
            'order_data': {
                'id': '200000_REPLAY_1',
                'status': 'paid',
                'order_items': [
                    {
                        'item': {'id': 'MLB1001001', 'title': 'Anúncio Unitário'},
                        'quantity': 2,
                        'unit_price': 50.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        pedido = PedidoVenda.objects.filter(pedido_id_externo="200000_REPLAY_1").first()
        self.assertIsNotNone(pedido)

        self.produto_unit.refresh_from_db()
        self.assertEqual(self.produto_unit.estoque, 8)

    def test_webhook_replay_pedido_ja_concluido_bloqueia_duplicidade(self):
        """
        4. Replay de evento já concluído: um PedidoVenda já persistido com sucesso (inclusive com item em
        pendente_vinculo) recebe o mesmo webhook novamente → assertar que NÃO duplica o PedidoVenda nem altera estoque.
        """
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/200000_JA_PERSISTIDO',
            'user_id': '777888999',
            'order_data': {
                'id': '200000_JA_PERSISTIDO',
                'status': 'paid',
                'order_items': [
                    {
                        'item': {'id': 'MLB1001001', 'title': 'Anúncio Unitário'},
                        'quantity': 1,
                        'unit_price': 50.00
                    }
                ]
            }
        }

        # 1ª execução
        res1 = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json().get('status'), 'ok')

        self.produto_unit.refresh_from_db()
        estoque_apos_1 = self.produto_unit.estoque

        # 2ª execução (Replay)
        res2 = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json().get('status'), 'ignored')

        self.produto_unit.refresh_from_db()
        self.assertEqual(self.produto_unit.estoque, estoque_apos_1)
        self.assertEqual(PedidoVenda.objects.filter(pedido_id_externo="200000_JA_PERSISTIDO").count(), 1)

    def test_webhook_item_sem_vinculo_persiste_venda_com_status_pendente(self):
        """
        5. Item sem vínculo local: item vendido (MLB...) ainda sem produto físico vinculado no catálogo daquela loja →
        assertar que o PedidoVenda é persistido com sucesso, o item marcado com pendente_vinculo, e nenhuma exceção não tratada é lançada.
        """
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/200000_SEM_VINCULO',
            'user_id': '777888999',
            'order_data': {
                'id': '200000_SEM_VINCULO',
                'status': 'paid',
                'total_amount': 99.00,
                'buyer': {'name': 'Comprador Desconhecido'},
                'order_items': [
                    {
                        'item': {'id': 'MLB_SEM_VINCULO_999', 'title': 'Item Sem Vínculo de Catálogo'},
                        'quantity': 1,
                        'unit_price': 99.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        pedido = PedidoVenda.objects.filter(pedido_id_externo="200000_SEM_VINCULO").first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.loja, self.loja)
        self.assertEqual(pedido.itens.count(), 1)

        item = pedido.itens.first()
        self.assertEqual(item.status_integracao, 'pendente_vinculo')
        self.assertIsNone(item.produto)
        self.assertFalse(item.estoque_baixado)

        auditoria = LogAuditoria.objects.filter(
            evento=EventoAuditoriaEnum.ALERTA_RUPTURA_ESTOQUE,
            loja=self.loja,
            detalhes__contains="AVISO DE RECONCILIAÇÃO"
        ).first()
        self.assertIsNotNone(auditoria)

    def test_webhook_concorrencia_race_condition_bloqueada_por_constraint(self):
        """
        Ajuste 2: Duas requisições simultâneas onde a constraint de banco IntegrityError
        impede a criação duplicada de PedidoVenda, sendo tratada graciosamente como ignorada/duplicata.
        """
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/200000_RACE_01',
            'user_id': '777888999',
            'order_data': {
                'id': '200000_RACE_01',
                'status': 'paid',
                'order_items': [
                    {
                        'item': {'id': 'MLB1001001', 'title': 'Anúncio Unitário'},
                        'quantity': 1,
                        'unit_price': 50.00
                    }
                ]
            }
        }

        with patch('apps.pedidos.models.PedidoVenda.objects.update_or_create') as mock_create:
            mock_create.side_effect = IntegrityError("UNIQUE constraint failed: pedidos_pedidovenda.canal_origem, pedidos_pedidovenda.pedido_id_externo")

            status_code, resp = MercadoLivreWebhookService.processar_notificacao(payload)
            self.assertEqual(status_code, 200)
            self.assertEqual(resp.get('status'), 'ignored')

            log = WebhookEventLog.objects.filter(resource='/orders/200000_RACE_01').first()
            self.assertIsNotNone(log)
            self.assertEqual(log.status, WebhookStatusEnum.IGNORADO)
            self.assertIn("bloqueada por constraint de banco", log.error_log)

    def test_webhook_replay_view_reprocessa_com_sucesso(self):
        """
        Ajuste 3 & 4: Staff/ADMIN autenticado reprocessa evento através da WebhookEventReplayView.
        """
        payload_evento = {
            'topic': 'orders_v2',
            'resource': '/orders/200000_REPLAY_VIEW',
            'user_id': '777888999',
            'order_data': {
                'id': '200000_REPLAY_VIEW',
                'status': 'paid',
                'order_items': [
                    {
                        'item': {'id': 'MLB1001001', 'title': 'Anúncio Unitário'},
                        'quantity': 1,
                        'unit_price': 50.00
                    }
                ]
            }
        }

        event_log = WebhookEventLog.objects.create(
            marketplace='mercadolivre',
            topic='orders_v2',
            resource='/orders/200000_REPLAY_VIEW',
            user_id='777888999',
            payload_raw=payload_evento,
            status=WebhookStatusEnum.ERRO,
            error_log="Erro simulado para teste de replay"
        )

        self.client.force_login(self.user)
        url_replay = reverse('webhook_event_replay', kwargs={'pk': event_log.pk})

        res = self.client.post(url_replay)
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('log_sincronizacao_list'), res.url)

        # PedidoVenda criado com sucesso
        pedido = PedidoVenda.objects.filter(pedido_id_externo="200000_REPLAY_VIEW").first()
        self.assertIsNotNone(pedido)

    def test_webhook_replay_view_nega_acesso_sem_permissao(self):
        """
        Ajuste 3 & 4: Usuário sem papel ADMIN/DEV recebe 403 Forbidden ao tentar disparar Replay.
        """
        user_comum = User.objects.create_user(username='usuario_operador', password='password123')
        PerfilUsuario.objects.create(usuario=user_comum, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

        event_log = WebhookEventLog.objects.create(
            marketplace='mercadolivre',
            topic='orders_v2',
            resource='/orders/200000_FORBIDDEN',
            user_id='777888999',
            payload_raw={'topic': 'orders_v2'},
            status=WebhookStatusEnum.ERRO
        )

        url_replay = reverse('webhook_event_replay', kwargs={'pk': event_log.pk})

        # Usuário sem permissão
        self.client.force_login(user_comum)
        res = self.client.post(url_replay)
        self.assertEqual(res.status_code, 403)

        # Não autenticado redireciona para login
        self.client.logout()
        res_anon = self.client.post(url_replay)
        self.assertEqual(res_anon.status_code, 302)

    def test_safe_decimal_e_safe_int_conversoes_defensivas(self):
        """
        Valida que safe_decimal e safe_int toleram todos os tipos de entrada sem lançar exceções.
        """
        from apps.marketplaces.utils import safe_decimal, safe_int

        # safe_decimal
        self.assertEqual(safe_decimal(None), Decimal('0.00'))
        self.assertEqual(safe_decimal('None'), Decimal('0.00'))
        self.assertEqual(safe_decimal('null'), Decimal('0.00'))
        self.assertEqual(safe_decimal(''), Decimal('0.00'))
        self.assertEqual(safe_decimal('   '), Decimal('0.00'))
        self.assertEqual(safe_decimal('invalid_text'), Decimal('0.00'))
        self.assertEqual(safe_decimal(0), Decimal('0'))
        self.assertEqual(safe_decimal(0.0), Decimal('0.0'))
        self.assertEqual(safe_decimal(150.50), Decimal('150.5'))
        self.assertEqual(safe_decimal('150.50'), Decimal('150.50'))
        self.assertEqual(safe_decimal('150,50'), Decimal('150.50'))
        self.assertEqual(safe_decimal('1.250,50'), Decimal('1250.50'))
        self.assertEqual(safe_decimal('1,250.50'), Decimal('1250.50'))
        self.assertEqual(safe_decimal(None, default=Decimal('10.00')), Decimal('10.00'))

        # safe_int
        self.assertEqual(safe_int(None), 1)
        self.assertEqual(safe_int('None'), 1)
        self.assertEqual(safe_int('null'), 1)
        self.assertEqual(safe_int(''), 1)
        self.assertEqual(safe_int('invalid'), 1)
        self.assertEqual(safe_int(0), 0)
        self.assertEqual(safe_int(5), 5)
        self.assertEqual(safe_int('5'), 5)
        self.assertEqual(safe_int('5.0'), 5)

    def test_webhook_pedido_com_shipping_cost_null_processa_com_sucesso(self):
        """
        Valida que notificação com 'shipping_cost': null e 'shipping': {'cost': null}
        é processada com sucesso sem estourar decimal.InvalidOperation: ConversionSyntax.
        """
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/2000018428049332',
            'user_id': self.conta_meli.seller_id_externo,
            'order_data': {
                'id': '2000018428049332',
                'status': 'paid',
                'shipping_cost': None,
                'shipping': {
                    'id': 123456,
                    'cost': None
                },
                'total_amount': 250.00,
                'order_items': [
                    {
                        'item': {
                            'id': self.anuncio_unit.item_id_externo,
                            'title': self.anuncio_unit.titulo
                        },
                        'quantity': 2,
                        'unit_price': 125.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        pedido = PedidoVenda.objects.filter(pedido_id_externo='2000018428049332').first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.valor_frete, Decimal('0.00'))
        self.assertEqual(pedido.valor_total, Decimal('250.00'))
        self.assertEqual(pedido.itens.count(), 1)
        item = pedido.itens.first()
        self.assertEqual(item.quantidade, 2)
        self.assertEqual(item.preco_unitario, Decimal('125.00'))

    def test_webhook_pedido_com_total_amount_null_e_unit_price_null(self):
        """
        Valida resiliência total a múltiplos campos nulos: total_amount: null,
        shipping_cost: null, unit_price: null, quantity: null.
        """
        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/2000018428049999',
            'user_id': self.conta_meli.seller_id_externo,
            'order_data': {
                'id': '2000018428049999',
                'status': 'paid',
                'shipping_cost': None,
                'shipping': None,
                'total_amount': None,
                'paid_amount': 99.00,
                'order_items': [
                    {
                        'item': {
                            'id': self.anuncio_unit.item_id_externo,
                            'title': self.anuncio_unit.titulo
                        },
                        'quantity': None,
                        'unit_price': None,
                        'full_unit_price': 99.00
                    }
                ]
            }
        }

        res = self.client.post(self.url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        pedido = PedidoVenda.objects.filter(pedido_id_externo='2000018428049999').first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.valor_frete, Decimal('0.00'))
        self.assertEqual(pedido.valor_total, Decimal('99.00'))
        item = pedido.itens.first()
        self.assertEqual(item.quantidade, 1)
        self.assertEqual(item.preco_unitario, Decimal('99.00'))





