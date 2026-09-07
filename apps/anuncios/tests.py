# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import CanalMarketplaceEnum
from apps.marketplaces.connectors.mercadolivre import MercadoLivreConnector
from apps.catalogo.models import Categoria, Produto
from apps.anuncios.models import Anuncio, AnuncioComposicao
from apps.anuncios.services import AnuncioImportacaoService, SincronizacaoAnuncioService


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
