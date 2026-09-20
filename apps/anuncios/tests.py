# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.marketplaces.models import ContaMarketplace, LogSincronizacao, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from apps.marketplaces.connectors.mercadolivre import MercadoLivreConnector
from apps.catalogo.models import Categoria, Produto
from apps.anuncios.models import Anuncio, AnuncioComposicao
from apps.anuncios.services import AnuncioImportacaoService, SincronizacaoAnuncioService, AnuncioSincronizacaoService


class AnunciosMarketplaceTestCase(TestCase):
    """
    Suíte de testes para a Fase 1: Importação de Anúncios, Ficha Técnica / Kits e Paginação Scan & Bulk.
    """

    def setUp(self):
        self.client = Client()

        self.loja = Loja.objects.create(
            nome="Loja Matriz",
            slug="loja-matriz",
            cnpj="11.111.111/0001-11"
        )
        self.loja.garantir_modulos_padrao()

        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Informática",
            slug="informatica"
        )

        # Produto 1: Mouse Óptico (Estoque: 10)
        self.produto_mouse = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="MOUSE-OPT-01",
            nome="Mouse Óptico USB",
            preco=Decimal('50.00'),
            estoque=10
        )

        # Produto 2: Teclado Mecânico (Estoque: 4)
        self.produto_teclado = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="TEC-MEC-01",
            nome="Teclado Mecânico RGB",
            preco=Decimal('200.00'),
            estoque=4
        )

        # Usuários RBAC
        self.user_admin = User.objects.create_user(username='admin_loja', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.user_padrao = User.objects.create_user(username='usuario_loja', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

        # Conta Mercado Livre
        self.conta_meli = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Matriz",
            access_token="APP_USR_TEST_VALID_TOKEN",
            refresh_token="REFRESH_VALID_TOKEN",
            seller_id_externo="86176658"
        )

    def test_calculo_cota_disponivel_unitario_e_kit(self):
        """Valida o cálculo da cota máxima vendável para anúncio unitário e para kit."""
        # 1. Anúncio Unitário (Mouse - 1x)
        anuncio_unit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB1001",
            titulo="Mouse Óptico Unitário",
            preco_venda=Decimal('55.00'),
            estoque_publicado=10,
            sku_vendedor="MOUSE-OPT-01"
        )
        AnuncioComposicao.objects.create(
            anuncio=anuncio_unit,
            produto=self.produto_mouse,
            quantidade=1
        )
        # Cota deve ser igual ao estoque do mouse (10)
        self.assertEqual(anuncio_unit.calcular_cota_disponivel(), 10)
        self.assertFalse(anuncio_unit.eh_kit)

        # 2. Anúncio Kit 3x Mouse
        anuncio_kit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB1002",
            titulo="Kit 3x Mouse Óptico",
            preco_venda=Decimal('140.00'),
            estoque_publicado=3,
            sku_vendedor="KIT-MOUSE-3X"
        )
        AnuncioComposicao.objects.create(
            anuncio=anuncio_kit,
            produto=self.produto_mouse,
            quantidade=3
        )
        # Cota deve ser floor(10 / 3) = 3
        self.assertEqual(anuncio_kit.calcular_cota_disponivel(), 3)
        self.assertTrue(anuncio_kit.eh_kit)

        # 3. Anúncio Combo (2x Mouse + 1x Teclado)
        anuncio_combo = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB1003",
            titulo="Combo Gamer (2 Mouse + 1 Teclado)",
            preco_venda=Decimal('280.00'),
            estoque_publicado=4,
            sku_vendedor="COMBO-GAMER"
        )
        AnuncioComposicao.objects.create(anuncio=anuncio_combo, produto=self.produto_mouse, quantidade=2)
        AnuncioComposicao.objects.create(anuncio=anuncio_combo, produto=self.produto_teclado, quantidade=1)

        # Mouse: 10 // 2 = 5; Teclado: 4 // 1 = 4. Cota = min(5, 4) = 4
        self.assertEqual(anuncio_combo.calcular_cota_disponivel(), 4)
        self.assertTrue(anuncio_combo.eh_kit)

        # Se estoque do teclado zerar, cota vai a zero
        self.produto_teclado.estoque = 0
        self.produto_teclado.save()
        self.assertEqual(anuncio_combo.calcular_cota_disponivel(), 0)

    @patch('requests.get')
    def test_importar_anuncios_paginacao_normal_e_bulk_chunking(self, mock_get):
        """Valida paginação comum e fatiamento correto em lotes de até 20 itens para /items/bulk."""
        # 25 IDs para testar chunking (20 + 5)
        item_ids = [f"MLB{i:05d}" for i in range(1, 26)]

        # Mock 1: /items/search com 25 resultados
        resp_search = MagicMock()
        resp_search.status_code = 200
        resp_search.json.return_value = {
            "paging": {"total": 25, "offset": 0, "limit": 100},
            "results": item_ids
        }

        # Mock 2: /items/bulk chunk 1 (20 itens)
        bulk_items_1 = [
            {"code": 200, "body": {"id": item_id, "title": f"Produto {item_id}", "price": 99.90, "available_quantity": 10, "status": "active", "seller_custom_field": "MOUSE-OPT-01"}}
            for item_id in item_ids[:20]
        ]
        resp_bulk_1 = MagicMock()
        resp_bulk_1.status_code = 200
        resp_bulk_1.json.return_value = bulk_items_1

        # Mock 3: /items/bulk chunk 2 (5 itens)
        bulk_items_2 = [
            {"code": 200, "body": {"id": item_id, "title": f"Produto {item_id}", "price": 49.90, "available_quantity": 5, "status": "active", "seller_custom_field": "TEC-MEC-01"}}
            for item_id in item_ids[20:]
        ]
        resp_bulk_2 = MagicMock()
        resp_bulk_2.status_code = 200
        resp_bulk_2.json.return_value = bulk_items_2

        mock_get.side_effect = [resp_search, resp_bulk_1, resp_bulk_2]

        connector = self.conta_meli.get_connector()
        # Força requisição HTTP
        connector._forcar_http_real = True

        with patch.object(connector, 'get_valid_access_token', return_value="FAKE_TOKEN"):
            res = connector.importar_anuncios()

        self.assertTrue(res['sucesso'])
        self.assertEqual(res['total'], 25)
        self.assertEqual(len(res['itens']), 25)

        # Valida que /items/bulk foi chamado 2 vezes
        calls = [c[0][0] for c in mock_get.call_args_list]
        bulk_calls = [c for c in calls if '/items/bulk?ids=' in c]
        self.assertEqual(len(bulk_calls), 2)
        self.assertEqual(len(bulk_calls[0].split('ids=')[1].split(',')), 20)
        self.assertEqual(len(bulk_calls[1].split('ids=')[1].split(',')), 5)

    @patch('requests.get')
    def test_importar_anuncios_scan_mode(self, mock_get):
        """Valida que contas com search_type=scan consomem scroll_id até exaustão."""
        resp_scan_1 = MagicMock()
        resp_scan_1.status_code = 200
        resp_scan_1.json.return_value = {
            "scroll_id": "SCROLL_123",
            "results": ["MLB101", "MLB102"]
        }

        resp_scan_2 = MagicMock()
        resp_scan_2.status_code = 200
        resp_scan_2.json.return_value = {
            "scroll_id": None,
            "results": ["MLB103"]
        }

        resp_bulk = MagicMock()
        resp_bulk.status_code = 200
        resp_bulk.json.return_value = [
            {"code": 200, "body": {"id": "MLB101", "title": "Item 1", "price": 10.0, "available_quantity": 2}},
            {"code": 200, "body": {"id": "MLB102", "title": "Item 2", "price": 20.0, "available_quantity": 3}},
            {"code": 200, "body": {"id": "MLB103", "title": "Item 3", "price": 30.0, "available_quantity": 4}},
        ]

        mock_get.side_effect = [resp_scan_1, resp_scan_2, resp_bulk]

        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        with patch.object(connector, 'get_valid_access_token', return_value="FAKE_TOKEN"):
            res = connector.importar_anuncios(search_type='scan')

        self.assertTrue(res['sucesso'])
        self.assertEqual(res['total'], 3)
        self.assertEqual([i['item_id_externo'] for i in res['itens']], ['MLB101', 'MLB102', 'MLB103'])

    def test_persistencia_idempotente_e_autovinculo_sku(self):
        """Valida persistência idempotente no banco e auto-vínculo de AnuncioComposicao por SKU."""
        mock_itens = [
            {
                "item_id_externo": "MLB9991",
                "titulo": "Mouse Óptico Importado",
                "preco": Decimal("59.90"),
                "quantidade_disponivel": 8,
                "status": "active",
                "sku_vendedor": "MOUSE-OPT-01",  # Coincide com self.produto_mouse.sku
                "thumbnail": "https://img.mlstatic.com/item1.jpg",
                "permalink": "https://produto.mercadolivre.com.br/MLB9991",
            },
            {
                "item_id_externo": "MLB9992",
                "titulo": "Headset Gamer Sem Cadastro",
                "preco": Decimal("150.00"),
                "quantidade_disponivel": 2,
                "status": "active",
                "sku_vendedor": "HEADSET-SEM-CADASTRO",
                "thumbnail": None,
                "permalink": None,
            }
        ]

        with patch.object(MercadoLivreConnector, 'importar_anuncios', return_value={"sucesso": True, "itens": mock_itens, "total": 2}):
            # 1. Primeira Execução
            res1 = AnuncioImportacaoService.importar_anuncios_da_conta(self.conta_meli, usuario=self.user_admin)
            self.assertTrue(res1['sucesso'])
            self.assertEqual(res1['total_importados'], 2)
            self.assertEqual(res1['total_vinculados'], 1)  # Apenas MOUSE-OPT-01 existia no estoque

            # Confirma persistência
            anuncio1 = Anuncio.objects.get(conta=self.conta_meli, item_id_externo="MLB9991")
            self.assertEqual(anuncio1.titulo, "Mouse Óptico Importado")
            self.assertEqual(anuncio1.itens_composicao.count(), 1)
            self.assertEqual(anuncio1.itens_composicao.first().produto, self.produto_mouse)
            self.assertEqual(anuncio1.calcular_cota_disponivel(), 10)

            anuncio2 = Anuncio.objects.get(conta=self.conta_meli, item_id_externo="MLB9992")
            self.assertEqual(anuncio2.itens_composicao.count(), 0)

            # 2. Segunda Execução (Idempotência com atualização de preço e título)
            mock_itens[0]["titulo"] = "Mouse Óptico Importado (Atualizado)"
            mock_itens[0]["preco"] = Decimal("64.90")

            res2 = AnuncioImportacaoService.importar_anuncios_da_conta(self.conta_meli, usuario=self.user_admin)
            self.assertTrue(res2['sucesso'])
            self.assertEqual(res2['total_importados'], 0)
            self.assertEqual(res2['total_atualizados'], 2)

            anuncio1.refresh_from_db()
            self.assertEqual(anuncio1.titulo, "Mouse Óptico Importado (Atualizado)")
            self.assertEqual(anuncio1.preco_venda, Decimal("64.90"))
            self.assertEqual(Anuncio.objects.filter(conta=self.conta_meli).count(), 2)

    def test_anuncio_views_and_rbac_permissions(self):
        """Valida endpoints de listagem, disparo de importação e RBAC."""
        # 1. Usuário comum (USUARIO) tem acesso à listagem mas é bloqueado ao disparar importação (403)
        self.client.login(username='usuario_loja', password='password123')
        res_list = self.client.get(reverse('anuncio_list'))
        self.assertEqual(res_list.status_code, 200)

        res_import_forbidden = self.client.post(reverse('anuncio_importar', kwargs={'pk': self.conta_meli.pk}))
        self.assertEqual(res_import_forbidden.status_code, 403)

        # 2. Administrador (ADMIN) pode disparar importação com sucesso
        self.client.login(username='admin_loja', password='password123')
        with patch.object(MercadoLivreConnector, 'importar_anuncios') as mock_imp:
            mock_imp.return_value = {
                "sucesso": True,
                "itens": [
                    {
                        "item_id_externo": "MLB7771",
                        "titulo": "Item Teste View",
                        "preco": Decimal("30.00"),
                        "quantidade_disponivel": 1,
                        "status": "active",
                    }
                ],
                "total": 1
            }
            res_import = self.client.post(reverse('anuncio_importar', kwargs={'pk': self.conta_meli.pk}), follow=True)
            self.assertEqual(res_import.status_code, 200)
            self.assertContains(res_import, "Importação de anúncios concluída com sucesso!")
            self.assertTrue(Anuncio.objects.filter(item_id_externo="MLB7771").exists())

        # 3. Gerenciamento de Composição via View
        anuncio = Anuncio.objects.get(item_id_externo="MLB7771")
        res_comp = self.client.post(reverse('anuncio_composicao_add', kwargs={'pk': anuncio.pk}), {
            'produto': self.produto_mouse.pk,
            'quantidade': 2
        })
        self.assertEqual(res_comp.status_code, 302)
        self.assertEqual(anuncio.itens_composicao.count(), 1)
        self.assertEqual(anuncio.itens_composicao.first().quantidade, 2)


class SincronizacaoEstoquePrecoTestCase(TestCase):
    """
    Suíte de testes para a Fase 2: Sincronização segura de estoque e preço no Mercado Livre,
    lógica defensiva, Circuit Breaker e disparo por Django Signals.
    """

    def setUp(self):
        self.loja = Loja.objects.create(
            nome="Loja Sync",
            slug="loja-sync",
            cnpj="22.222.222/0001-22"
        )
        self.loja.garantir_modulos_padrao()
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Eletrônicos",
            slug="eletronicos"
        )

        self.produto_gamer = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="HEADSET-01",
            nome="Headset Gamer 7.1",
            preco=Decimal('100.00'),
            estoque=20
        )

        self.produto_acessorio = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SUPORTE-01",
            nome="Suporte Headset RGB",
            preco=Decimal('50.00'),
            estoque=6
        )

        self.user_admin = User.objects.create_user(username='admin_sync', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.conta_meli = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Sync",
            access_token="APP_USR_REAL_TEST_TOKEN",
            refresh_token="TG_REAL_TEST_REFRESH",
            seller_id_externo="99887766"
        )

        # Anúncio 1: Unitário (Headset)
        self.anuncio_unitario = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB2001",
            titulo="Headset Gamer 7.1 Surround",
            preco_venda=Decimal('100.00'),
            estoque_publicado=20,
            status='active',
            sku_vendedor="HEADSET-01"
        )
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_unitario,
            produto=self.produto_gamer,
            quantidade=1
        )

        # Anúncio 2: Kit Gamer (1x Headset + 2x Suporte)
        self.anuncio_kit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB2002",
            titulo="Kit Combo Gamer Headset + 2 Suportes",
            preco_venda=Decimal('189.90'),
            estoque_publicado=3,
            status='active',
            sku_vendedor="KIT-GAMER-01"
        )
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_kit,
            produto=self.produto_gamer,
            quantidade=1
        )
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_kit,
            produto=self.produto_acessorio,
            quantidade=2
        )

    @patch('requests.put')
    def test_conector_meli_atualizar_estoque_e_preco_sucesso(self, mock_put):
        """Valida PUT /items/{id} para estoque e preço com criação de LogSincronizacao."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "MLB2001", "status": "updated"}
        mock_put.return_value = mock_resp

        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        # 1. Atualizar Estoque
        ok_est, msg_est, log_est = connector.atualizar_estoque("MLB2001", 15, usuario=self.user_admin)
        self.assertTrue(ok_est)
        self.assertIn("Estoque sincronizado no Mercado Livre: 15 un.", msg_est)
        self.assertIsNotNone(log_est)
        self.assertEqual(log_est.evento, EventoAuditoriaEnum.SYNC_ESTOQUE)
        self.assertEqual(log_est.item_id_externo, "MLB2001")
        self.assertEqual(log_est.payload_enviado, {"available_quantity": 15})

        # 2. Atualizar Preço
        ok_prc, msg_prc, log_prc = connector.atualizar_preco("MLB2001", Decimal('119.90'), usuario=self.user_admin)
        self.assertTrue(ok_prc)
        self.assertIn("Preço de R$ 119.90 sincronizado no Mercado Livre!", msg_prc)
        self.assertIsNotNone(log_prc)
        self.assertEqual(log_prc.evento, EventoAuditoriaEnum.SYNC_PRECO)
        self.assertEqual(log_prc.payload_enviado, {"price": 119.90})

    @patch('requests.put')
    def test_conector_meli_retry_refresh_sob_401(self, mock_put):
        """Valida que resposta HTTP 401 dispara renovar_token e retenta a requisição."""
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.json.return_value = {"message": "Invalid token"}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"id": "MLB2001", "status": "updated"}

        mock_put.side_effect = [resp_401, resp_200]

        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        with patch.object(connector, 'renovar_token', return_value=(True, "Token renovado")) as mock_renovar:
            ok, msg, log = connector.atualizar_estoque("MLB2001", 12)
            self.assertTrue(ok)
            self.assertEqual(mock_renovar.call_count, 1)
            self.assertEqual(mock_put.call_count, 2)

    @patch('requests.put')
    def test_conector_meli_rejeicao_api_externa(self, mock_put):
        """Valida tratamento de erro HTTP 400 com log de auditoria de falha."""
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.json.return_value = {"message": "Item paused, cannot update stock"}
        mock_put.return_value = resp_400

        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        ok, msg, log = connector.atualizar_estoque("MLB2001", 5)
        self.assertFalse(ok)
        self.assertIn("Mercado Livre rejeitou sincronização de estoque", msg)
        self.assertIsNotNone(log)
        self.assertFalse(log.sucesso)
        self.assertEqual(log.status_http, 400)

    def test_sincronizacao_cota_kit_e_unitario(self):
        """Valida cálculo de cota de kit (min entre componentes) e envio correto."""
        # Suporte tem estoque 6. Multiplicador no kit é 2. Logo cota do kit = 6 // 2 = 3.
        self.assertEqual(self.anuncio_kit.calcular_cota_disponivel(), 3)

        # Alterando estoque do suporte para 4: nova cota do kit deve ser 4 // 2 = 2.
        self.produto_acessorio.estoque = 4
        self.produto_acessorio.save()

        self.assertEqual(self.anuncio_kit.calcular_cota_disponivel(), 2)

        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_att:
            mock_att.return_value = (True, "OK", None)
            res = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(self.anuncio_kit, forcar=True)
            self.assertTrue(res['sucesso'])
            self.assertEqual(res['estoque_sincronizado'], 2)
            self.anuncio_kit.refresh_from_db()
            self.assertEqual(self.anuncio_kit.estoque_publicado, 2)

    def test_bloqueio_saldo_negativo_defensivo(self):
        """Valida que valores negativos de estoque são clampados para zero."""
        # Se produto ficar com estoque negativo (-5)
        self.produto_gamer.estoque = -5
        self.produto_gamer.save()

        cota = self.anuncio_unitario.calcular_cota_disponivel()
        self.assertEqual(cota, 0)

        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_att:
            mock_att.return_value = (True, "OK", None)
            res = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(self.anuncio_unitario, forcar=True)
            self.assertTrue(res['sucesso'])
            self.assertEqual(res['estoque_sincronizado'], 0)
            mock_att.assert_called_with("MLB2001", 0, usuario=None)

    def test_circuit_breaker_variacao_anomala_preco(self):
        """Valida bloqueio de variações de preço > 50% para baixo ou > 100% para cima sem override."""
        # Preço atual: R$ 100.00. Tentativa de baixar para R$ 40.00 (queda de 60%)
        res_queda = AnuncioSincronizacaoService.sincronizar_preco_anuncio(
            self.anuncio_unitario, Decimal('40.00'), usuario=self.user_admin, forcar=False
        )
        self.assertFalse(res_queda['sucesso'])
        self.assertTrue(res_queda.get('bloqueado_circuit_breaker'))
        self.assertIn("Circuit Breaker acionado: Queda anômala", res_queda['mensagem'])
        self.anuncio_unitario.refresh_from_db()
        self.assertEqual(self.anuncio_unitario.preco_venda, Decimal('100.00'))

        # Confirma registro no LogAuditoria
        self.assertTrue(LogAuditoria.objects.filter(
            loja=self.loja,
            evento=EventoAuditoriaEnum.SYNC_PRECO,
            detalhes__contains="Circuit Breaker"
        ).exists())

        # Tentativa de aumento anômalo: de R$ 100.00 para R$ 250.00 (aumento de 150% > 100%)
        res_alta = AnuncioSincronizacaoService.sincronizar_preco_anuncio(
            self.anuncio_unitario, Decimal('250.00'), usuario=self.user_admin, forcar=False
        )
        self.assertFalse(res_alta['sucesso'])
        self.assertTrue(res_alta.get('bloqueado_circuit_breaker'))
        self.assertIn("Aumento anômalo", res_alta['mensagem'])

        # Com forcar=True, deve aprovar e sincronizar
        with patch.object(MercadoLivreConnector, 'atualizar_preco') as mock_prc:
            mock_prc.return_value = (True, "Preço atualizado", None)
            res_forcar = AnuncioSincronizacaoService.sincronizar_preco_anuncio(
                self.anuncio_unitario, Decimal('40.00'), usuario=self.user_admin, forcar=True
            )
            self.assertTrue(res_forcar['sucesso'])
            self.anuncio_unitario.refresh_from_db()
            self.assertEqual(self.anuncio_unitario.preco_venda, Decimal('40.00'))

    def test_circuit_breaker_zeramento_lote(self):
        """Valida o bloqueio preventivo de operações massivas com risco de zeramento acidental."""
        # 6 de 10 anúncios zerando (> 5 e > 50%)
        ok, msg = AnuncioSincronizacaoService.validar_zeramento_em_lote(10, 6, forcar=False)
        self.assertFalse(ok)
        self.assertIn("Circuit Breaker acionado: Tentativa de zeramento em massa", msg)

        # Com forcar=True, deve aprovar
        ok_forcado, _ = AnuncioSincronizacaoService.validar_zeramento_em_lote(10, 6, forcar=True)
        self.assertTrue(ok_forcado)

        # 2 de 10 anúncios zerando (dentro do limite aceitável)
        ok_normal, _ = AnuncioSincronizacaoService.validar_zeramento_em_lote(10, 2, forcar=False)
        self.assertTrue(ok_normal)

    def test_signals_produto_disparam_sincronizacao_anuncios(self):
        """Valida que salvar Produto com alteração de estoque marca anúncios vinculados como PENDENTE sem disparar chamadas externas silenciosas."""
        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_sync_est:
            mock_sync_est.return_value = (True, "OK", None)

            # Define estado inicial sincronizado
            self.anuncio_unitario.status_sincronizacao = 'ENVIADO'
            self.anuncio_unitario.save()
            self.anuncio_kit.status_sincronizacao = 'ENVIADO'
            self.anuncio_kit.save()

            # Altera estoque do Headset de 20 para 2 (afeta cota unitária e do kit)
            self.produto_gamer.estoque = 2
            self.produto_gamer.save()

            # NÃO deve ter disparado chamadas externas à API do Mercado Livre (desacoplamento defensivo)
            self.assertEqual(mock_sync_est.call_count, 0)

            # Deve marcar anúncios vinculados como PENDENTE para confirmação manual
            self.anuncio_unitario.refresh_from_db()
            self.anuncio_kit.refresh_from_db()
            self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'PENDENTE')
            self.assertEqual(self.anuncio_kit.status_sincronizacao, 'PENDENTE')

            # Confirma registro na trilha de histórico de ciclo
            from apps.anuncios.models import HistoricoSincronizacaoAnuncio
            self.assertTrue(HistoricoSincronizacaoAnuncio.objects.filter(
                anuncio=self.anuncio_unitario, status_resultante='PENDENTE'
            ).exists())

    def test_signals_reabrem_anuncios_cancelados_sob_divergencia_fisica(self):
        """Valida que anúncios marcados como CANCELADO têm seu status alterado para PENDENTE quando houver nova divergência física no Produto."""
        self.anuncio_unitario.status_sincronizacao = 'CANCELADO'
        self.anuncio_unitario.save()

        # Altera estoque físico gerando divergência na cota
        self.produto_gamer.estoque = 5
        self.produto_gamer.save()

        self.anuncio_unitario.refresh_from_db()
        self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'PENDENTE')

    def test_toggle_ignorar_anuncio_view(self):
        """Valida alternância entre status CANCELADO e reativação para PENDENTE/ENVIADO."""
        self.client.force_login(self.user_admin)
        url = reverse('anuncio_toggle_ignorar', kwargs={'pk': self.anuncio_unitario.pk})

        # 1. Marca como CANCELADO
        resp1 = self.client.post(url, HTTP_REFERER='/produtos/1/')
        self.assertEqual(resp1.status_code, 302)
        self.anuncio_unitario.refresh_from_db()
        self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'CANCELADO')

        # 2. Reativa a sincronização
        resp2 = self.client.post(url, HTTP_REFERER='/produtos/1/')
        self.assertEqual(resp2.status_code, 302)
        self.anuncio_unitario.refresh_from_db()
        self.assertIn(self.anuncio_unitario.status_sincronizacao, ['PENDENTE', 'ENVIADO'])

    def test_sincronizar_anuncio_view_atualiza_status_para_enviado(self):
        """Valida que sincronização manual via view atualiza status_sincronizacao para ENVIADO e grava histórico."""
        self.client.force_login(self.user_admin)
        url = reverse('anuncio_sincronizar', kwargs={'pk': self.anuncio_unitario.pk})
        self.anuncio_unitario.status_sincronizacao = 'PENDENTE'
        self.anuncio_unitario.save()

        with patch.object(MercadoLivreConnector, 'atualizar_estoque', return_value=(True, "OK", None)), \
             patch.object(MercadoLivreConnector, 'atualizar_preco', return_value=(True, "OK", None)):
            resp = self.client.post(url, HTTP_REFERER='/produtos/1/')
            self.assertEqual(resp.status_code, 302)
            self.anuncio_unitario.refresh_from_db()
            self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'ENVIADO')

            from apps.anuncios.models import HistoricoSincronizacaoAnuncio
            self.assertTrue(HistoricoSincronizacaoAnuncio.objects.filter(
                anuncio=self.anuncio_unitario, status_resultante='ENVIADO'
            ).exists())

    def test_idempotencia_evita_requisicao_externa_redundante(self):
        """Valida que se o estoque calculado for idêntico ao já publicado, a chamada de rede é poupada."""
        self.anuncio_unitario.estoque_publicado = 20
        self.anuncio_unitario.save()

        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_att:
            res = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(self.anuncio_unitario, forcar=False)
            self.assertTrue(res['sucesso'])
            self.assertTrue(res.get('ignorado_idempotencia'))
            self.assertEqual(mock_att.call_count, 0)

    def test_exclusao_componente_intermediario_kit_3_itens_preserva_irmas(self):
        """
        Cenário 1: Kit com 3 componentes (A, B, C).
        Exclui o componente intermediário (B).
        Assertar que A e C continuam intactos no banco, com SKUs, quantidades e vínculos inalterados.
        Assertar que os produtos físicos continuam existindo.
        """
        self.client.force_login(self.user_admin)

        prod_a = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT3-A", nome="Produto A", preco=Decimal('10.00'), estoque=15)
        prod_b = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT3-B", nome="Produto B", preco=Decimal('20.00'), estoque=25)
        prod_c = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT3-C", nome="Produto C", preco=Decimal('30.00'), estoque=35)

        anuncio_kit3 = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB-KIT3-01",
            titulo="Anúncio Kit Triplo ABC",
            preco_venda=Decimal('60.00'),
            estoque_publicado=10
        )
        comp_a = AnuncioComposicao.objects.create(anuncio=anuncio_kit3, produto=prod_a, quantidade=1)
        comp_b = AnuncioComposicao.objects.create(anuncio=anuncio_kit3, produto=prod_b, quantidade=2)
        comp_c = AnuncioComposicao.objects.create(anuncio=anuncio_kit3, produto=prod_c, quantidade=3)

        url_delete = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio_kit3.pk, 'pk': comp_b.pk})
        resp = self.client.post(url_delete)
        self.assertEqual(resp.status_code, 302)

        # B foi excluído da composição
        self.assertFalse(AnuncioComposicao.objects.filter(pk=comp_b.pk).exists())

        # A e C continuam intactos na composição
        comp_a.refresh_from_db()
        comp_c.refresh_from_db()
        self.assertEqual(comp_a.quantidade, 1)
        self.assertEqual(comp_a.produto, prod_a)
        self.assertEqual(comp_c.quantidade, 3)
        self.assertEqual(comp_c.produto, prod_c)

        # Produtos físicos originais permanecem intactos no catálogo
        self.assertTrue(Produto.objects.filter(pk=prod_a.pk).exists())
        self.assertTrue(Produto.objects.filter(pk=prod_b.pk).exists())
        self.assertTrue(Produto.objects.filter(pk=prod_c.pk).exists())

    def test_exclusao_sequencial_componentes_kit_4_itens(self):
        """
        Cenário 2: Kit com 4 componentes (A, B, C, D).
        Executa a remoção sequencial de dois componentes em requisições isoladas.
        Assertar a integridade referencial dos registros restantes após cada requisição.
        """
        self.client.force_login(self.user_admin)

        prod_a = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-A", nome="Item A", preco=Decimal('10.00'), estoque=10)
        prod_b = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-B", nome="Item B", preco=Decimal('10.00'), estoque=10)
        prod_c = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-C", nome="Item C", preco=Decimal('10.00'), estoque=10)
        prod_d = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-D", nome="Item D", preco=Decimal('10.00'), estoque=10)

        anuncio_kit4 = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB-KIT4-01",
            titulo="Anúncio Kit Quádruplo",
            preco_venda=Decimal('40.00'),
            estoque_publicado=5
        )
        comp_a = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_a, quantidade=1)
        comp_b = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_b, quantidade=1)
        comp_c = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_c, quantidade=1)
        comp_d = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_d, quantidade=1)

        # 1ª Requisição: Exclui B
        url_del_b = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio_kit4.pk, 'pk': comp_b.pk})
        resp1 = self.client.post(url_del_b)
        self.assertEqual(resp1.status_code, 302)

        # Valida integridade após 1ª exclusão (restam A, C, D)
        restantes1 = list(anuncio_kit4.itens_composicao.values_list('produto__sku', flat=True))
        self.assertEqual(len(restantes1), 3)
        self.assertCountEqual(restantes1, ["KIT4-A", "KIT4-C", "KIT4-D"])

        # 2ª Requisição: Exclui C
        url_del_c = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio_kit4.pk, 'pk': comp_c.pk})
        resp2 = self.client.post(url_del_c)
        self.assertEqual(resp2.status_code, 302)

        # Valida integridade após 2ª exclusão (restam A, D)
        restantes2 = list(anuncio_kit4.itens_composicao.values_list('produto__sku', flat=True))
        self.assertEqual(len(restantes2), 2)
        self.assertCountEqual(restantes2, ["KIT4-A", "KIT4-D"])

        # Todos os 4 produtos físicos permanecem íntegros no banco
        self.assertEqual(Produto.objects.filter(sku__in=["KIT4-A", "KIT4-B", "KIT4-C", "KIT4-D"]).count(), 4)

    def test_validacao_snapshots_auditoria_exclusao_composicao(self):
        """
        Cenário 3: Validação de Snapshots de Auditoria.
        Assertar que, ao excluir um item, o registro criado em HistoricoSincronizacaoAnuncio
        grava fielmente a lista completa prévia em snapshot_antes e a lista restante exata em snapshot_depois.
        """
        self.client.force_login(self.user_admin)

        prod1 = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="SNAP-01", nome="Item 1", preco=Decimal('15.00'), estoque=20)
        prod2 = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="SNAP-02", nome="Item 2", preco=Decimal('25.00'), estoque=30)

        anuncio = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB-SNAP-TEST",
            titulo="Anúncio Teste Snapshots",
            preco_venda=Decimal('40.00'),
            estoque_publicado=20
        )
        comp1 = AnuncioComposicao.objects.create(anuncio=anuncio, produto=prod1, quantidade=1)
        comp2 = AnuncioComposicao.objects.create(anuncio=anuncio, produto=prod2, quantidade=2)

        from apps.anuncios.models import HistoricoSincronizacaoAnuncio
        hist_count_antes = HistoricoSincronizacaoAnuncio.objects.filter(anuncio=anuncio).count()

        # Dispara exclusão do comp1
        url_del = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio.pk, 'pk': comp1.pk})
        resp = self.client.post(url_del)
        self.assertEqual(resp.status_code, 302)

        # Valida que um novo registro de histórico foi criado com os snapshots
        hist = HistoricoSincronizacaoAnuncio.objects.filter(anuncio=anuncio).order_by('-criado_em').first()
        self.assertIsNotNone(hist)
        self.assertEqual(HistoricoSincronizacaoAnuncio.objects.filter(anuncio=anuncio).count(), hist_count_antes + 1)

        # Validação do snapshot_antes (deve conter comp1 e comp2)
        skus_antes = [item['sku'] for item in hist.snapshot_antes]
        self.assertEqual(len(hist.snapshot_antes), 2)
        self.assertIn("SNAP-01", skus_antes)
        self.assertIn("SNAP-02", skus_antes)

        # Validação do snapshot_depois (deve conter apenas comp2)
        skus_depois = [item['sku'] for item in hist.snapshot_depois]
        self.assertEqual(len(hist.snapshot_depois), 1)
        self.assertNotIn("SNAP-01", skus_depois)
        self.assertIn("SNAP-02", skus_depois)
        self.assertEqual(hist.snapshot_depois[0]['sku'], "SNAP-02")
        self.assertEqual(hist.snapshot_depois[0]['quantidade'], 2)


class AnuncioCriacaoManualEComposicaoTestCase(TestCase):
    """
    O QUE FAZ: Testes automatizados para criação e edição manual de anúncios e composições comerciais (ADR-003, ADR-009).
    POR QUE FAZ: Valida criação de combos heterogêneos, recálculo dinâmico de cota gargalo, rejeição de duplicidades,
                 isolamento multi-tenant estrito e autorização RBAC.
    """
    def setUp(self):
        self.client = Client()

        self.loja = Loja.objects.create(nome="Loja A", slug="loja-a", cnpj="11.111.111/0001-11")
        self.loja.garantir_modulos_padrao()

        self.loja_b = Loja.objects.create(nome="Loja B", slug="loja-b", cnpj="22.222.222/0001-22")
        self.loja_b.garantir_modulos_padrao()

        self.user_admin = User.objects.create_user(username='admin_a', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.user_padrao = User.objects.create_user(username='operador_a', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

        self.user_dev = User.objects.create_user(username='dev_master', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PapelUsuarioEnum.DEV)

        self.categoria = Categoria.objects.create(loja=self.loja, nome="Hardware", slug="hardware")
        self.categoria_b = Categoria.objects.create(loja=self.loja_b, nome="Hardware B", slug="hardware-b")

        self.produto_a = Produto.objects.create(
            loja=self.loja, categoria=self.categoria, sku="PROD-A", nome="Produto Alpha",
            preco=Decimal('100.00'), estoque=10
        )
        self.produto_b = Produto.objects.create(
            loja=self.loja, categoria=self.categoria, sku="PROD-B", nome="Produto Beta",
            preco=Decimal('50.00'), estoque=12
        )
        self.produto_loja_b = Produto.objects.create(
            loja=self.loja_b, categoria=self.categoria_b, sku="PROD-OUTRA-LOJA", nome="Produto Outra Loja",
            preco=Decimal('30.00'), estoque=50
        )

        self.conta = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Loja A",
            seller_id_externo="12345"
        )

    def test_criacao_manual_anuncio_combo_multiproduto(self):
        """Valida a criação manual de anúncio com 2 produtos heterogêneos (Combo) e cálculo da cota gargalo."""
        self.client.force_login(self.user_admin)
        url = reverse('anuncio_create')

        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-COMBO-99',
            'titulo': 'Combo Teclado + Mouse Gamer',
            'sku_vendedor': 'COMBO-GAMER',
            'preco_venda': '149.90',
            'status': 'active',
            # Inline formset (prefix 'itens_composicao')
            'itens_composicao-TOTAL_FORMS': '2',
            'itens_composicao-INITIAL_FORMS': '0',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            # Item 0: Produto A x 2 (10 // 2 = 5)
            'itens_composicao-0-produto': self.produto_a.pk,
            'itens_composicao-0-quantidade': '2',
            # Item 1: Produto B x 3 (12 // 3 = 4 -> gargalo!)
            'itens_composicao-1-produto': self.produto_b.pk,
            'itens_composicao-1-quantidade': '3',
        }

        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        anuncio = Anuncio.objects.filter(item_id_externo='MLB-COMBO-99').first()
        self.assertIsNotNone(anuncio)
        self.assertEqual(anuncio.itens_composicao.count(), 2)
        self.assertEqual(anuncio.tipo_composicao, "Combo Multi-Produto")
        self.assertEqual(anuncio.tipo_composicao_badge['label'], "Combo Multi-Produto")
        # Gargalo min(10//2, 12//3) = min(5, 4) = 4
        self.assertEqual(anuncio.calcular_cota_disponivel(), 4)
        self.assertEqual(anuncio.estoque_publicado, 4)

    def test_validacao_rejeicao_produtos_duplicados(self):
        """Valida que o formset rejeita o mesmo produto selecionado mais de uma vez."""
        self.client.force_login(self.user_admin)
        url = reverse('anuncio_create')

        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-DUP-01',
            'titulo': 'Anúncio com Duplicidade',
            'preco_venda': '100.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '2',
            'itens_composicao-INITIAL_FORMS': '0',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            # Linha 0 e 1 usam o mesmo produto_a
            'itens_composicao-0-produto': self.produto_a.pk,
            'itens_composicao-0-quantidade': '1',
            'itens_composicao-1-produto': self.produto_a.pk,
            'itens_composicao-1-quantidade': '2',
        }

        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            "adicionado mais de uma vez" in resp.content.decode('utf-8') or
            "duplicado" in resp.content.decode('utf-8')
        )
        self.assertFalse(Anuncio.objects.filter(item_id_externo='MLB-DUP-01').exists())

    def test_validacao_rejeicao_produto_outra_loja_multi_tenant(self):
        """Valida que produto de outra loja não é aceito no formset (ADR-003)."""
        self.client.force_login(self.user_admin)
        url = reverse('anuncio_create')

        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-CROSS-TENANT',
            'titulo': 'Anúncio Cross Tenant Tentativa',
            'preco_venda': '100.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '1',
            'itens_composicao-INITIAL_FORMS': '0',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            'itens_composicao-0-produto': self.produto_loja_b.pk,
            'itens_composicao-0-quantidade': '1',
        }

        resp = self.client.post(url, post_data)
        # O formulário rejeita porque o produto_loja_b não pertence ao queryset filtrado pela loja
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Anuncio.objects.filter(item_id_externo='MLB-CROSS-TENANT').exists())

    def test_edicao_anuncio_recalculo_cota(self):
        """Valida atualização do anúncio e recálculo da cota dinâmica via AnuncioUpdateView."""
        self.client.force_login(self.user_admin)

        anuncio = Anuncio.objects.create(
            conta=self.conta,
            item_id_externo='MLB-EDIT-01',
            titulo='Anúncio para Edição',
            preco_venda=Decimal('100.00'),
            estoque_publicado=10
        )
        comp_a = AnuncioComposicao.objects.create(anuncio=anuncio, produto=self.produto_a, quantidade=1)

        url = reverse('anuncio_update', kwargs={'pk': anuncio.pk})

        # Altera multiplicador do produto A de 1 para 5 (10 // 5 = 2)
        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-EDIT-01',
            'titulo': 'Anúncio Editado com Sucesso',
            'preco_venda': '120.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '1',
            'itens_composicao-INITIAL_FORMS': '1',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            'itens_composicao-0-id': comp_a.pk,
            'itens_composicao-0-produto': self.produto_a.pk,
            'itens_composicao-0-quantidade': '5',
        }

        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        anuncio.refresh_from_db()
        self.assertEqual(anuncio.titulo, 'Anúncio Editado com Sucesso')
        self.assertEqual(anuncio.preco_venda, Decimal('120.00'))
        self.assertEqual(anuncio.calcular_cota_disponivel(), 2)
        self.assertEqual(anuncio.estoque_publicado, 2)
        self.assertEqual(anuncio.tipo_composicao, "Kit Homogêneo")

    def test_rbac_usuario_padrao_bloqueado(self):
        """Valida que perfil USUARIO recebe 403 ao tentar criar ou editar anúncios."""
        self.client.force_login(self.user_padrao)

        anuncio = Anuncio.objects.create(
            conta=self.conta,
            item_id_externo='MLB-RBAC-01',
            titulo='Anúncio RBAC',
            preco_venda=Decimal('10.00'),
            estoque_publicado=5
        )

        resp_create = self.client.get(reverse('anuncio_create'))
        self.assertEqual(resp_create.status_code, 403)

        resp_update = self.client.get(reverse('anuncio_update', kwargs={'pk': anuncio.pk}))
        self.assertEqual(resp_update.status_code, 403)

    def test_dev_restringido_estritamente_produtos_da_loja_do_anuncio(self):
        """
        Valida que, mesmo acessando com usuário DEV, o anúncio e o formset são
        restringidos unicamente aos produtos pertencentes à loja em questão.
        """
        self.client.force_login(self.user_dev)

        anuncio = Anuncio.objects.create(
            conta=self.conta,
            item_id_externo='MLB-DEV-RESTRICT',
            titulo='Anúncio Teste DEV',
            preco_venda=Decimal('150.00'),
            estoque_publicado=10
        )
        AnuncioComposicao.objects.create(anuncio=anuncio, produto=self.produto_a, quantidade=1)

        # 1. GET no AnuncioUpdateView: o dropdown deve conter apenas produtos da Loja A
        url_edit = reverse('anuncio_update', kwargs={'pk': anuncio.pk})
        resp = self.client.get(url_edit)
        self.assertEqual(resp.status_code, 200)

        formset = resp.context['formset']
        form_prod_qs = formset.forms[0].fields['produto'].queryset
        # Deve conter produto_a (Loja A), e NÃO pode conter produto_loja_b (Loja B)
        self.assertIn(self.produto_a, form_prod_qs)
        self.assertNotIn(self.produto_loja_b, form_prod_qs)
        self.assertContains(resp, "PROD-A")
        self.assertNotContains(resp, "PROD-OUTRA-LOJA")

        # 2. POST com produto da Loja B pelo DEV deve ser rejeitado
        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-DEV-RESTRICT',
            'titulo': 'Tentativa DEV Cross-Tenant',
            'preco_venda': '150.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '1',
            'itens_composicao-INITIAL_FORMS': '1',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            'itens_composicao-0-produto': self.produto_loja_b.pk,
            'itens_composicao-0-quantidade': '1',
        }
        resp_post = self.client.post(url_edit, post_data)
        self.assertEqual(resp_post.status_code, 200)
        # Formset deve conter erro e rejeitar o salvamento
        self.assertTrue(bool(resp_post.context['formset'].errors))


