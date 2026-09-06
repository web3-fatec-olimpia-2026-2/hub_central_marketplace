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




