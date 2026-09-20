# Os códigos foram gerados com auxilio de I.A.
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.marketplaces.models import ContaMarketplace, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from apps.catalogo.models import Categoria, Produto, AnuncioMarketplace, HistoricoPreco
from apps.anuncios.models import Anuncio, AnuncioComposicao
from apps.pedidos.models import PedidoVenda, ItemPedidoVenda, Pedido, ItemPedido
from apps.pedidos.services import ProcessamentoPedidoService


class PedidosAndAtomicStockTestCase(TestCase):
    """
    O QUE FAZ: Suíte de testes automatizados para processamento de pedidos, baixa atômica de estoque e detecção de rupturas (RN-05).
    POR QUE FAZ: Valida concorrência, idempotência e geração de alertas de saldo negativo.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Escopo por loja.
    """

    def setUp(self):
        self.client = Client()

        self.loja = Loja.objects.create(
            nome="Loja Pedidos",
            slug="loja-pedidos",
            cnpj="55.555.555/0001-55"
        )
        self.loja.garantir_modulos_padrao()

        self.user = User.objects.create_user(username='admin_pedidos', password='password123')
        PerfilUsuario.objects.create(usuario=self.user, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Geral",
            slug="geral"
        )

        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="TECLADO-RGB-PRO",
            nome="Teclado Mecânico RGB Pro",
            preco=Decimal('250.00'),
            estoque=5
        )

        self.conta_ml = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Pedidos",
            seller_id_externo="999888"
        )

        self.anuncio = AnuncioMarketplace.objects.create(
            produto=self.produto,
            conta_marketplace=self.conta_ml,
            item_id_externo="MLB776655",
            preco_sincronizado=Decimal('250.00')
        )

    def test_processamento_pedido_atomic_stock_deduction(self):
        """Valida que o processamento do pedido deduz o saldo de estoque físico com sucesso."""
        payload = {
            'order_id': 'ORD-1001',
            'total_amount': 500.00,
            'buyer': {'nickname': 'comprador_teste'},
            'items': [
                {
                    'item': {'id': 'MLB776655', 'title': 'Teclado Mecânico RGB Pro'},
                    'quantity': 2,
                    'unit_price': 250.00
                }
            ]
        }

        sucesso, msg, pedido = ProcessamentoPedidoService.processar_pedido_venda(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            pedido_id_externo="ORD-1001",
            dados_pedido=payload,
            conta=self.conta_ml
        )

        self.assertTrue(sucesso)
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.itens.count(), 1)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 3)  # 5 - 2 = 3
        self.assertFalse(pedido.teve_ruptura_estoque)

        # Valida que o HistoricoPreco foi registrado
        historico = HistoricoPreco.objects.filter(produto=self.produto).latest('criado_em')
        self.assertEqual(historico.estoque_anterior, 5)
        self.assertEqual(historico.estoque_novo, 3)
        self.assertEqual(historico.preco_anterior, Decimal('250.00'))
        self.assertEqual(historico.preco_novo, Decimal('250.00'))
        self.assertIn("ORD-1001", historico.motivo)
        self.assertIn("Mercado Livre", historico.motivo)

    def test_idempotency_prevents_duplicate_deduction(self):
        """Valida que reprocessar o mesmo pedido não duplica o débito de estoque."""
        payload = {
            'order_id': 'ORD-IDEMPOTENTE',
            'total_amount': 250.00,
            'items': [{'item': {'id': 'MLB776655'}, 'quantity': 1, 'unit_price': 250.00}]
        }

        # Primeiro processamento: estoque 5 -> 4
        ProcessamentoPedidoService.processar_pedido_venda(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            pedido_id_externo="ORD-IDEMPOTENTE",
            dados_pedido=payload
        )
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 4)

        # Segundo processamento (mesmo ID): ignora e mantém estoque em 4
        ProcessamentoPedidoService.processar_pedido_venda(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            pedido_id_externo="ORD-IDEMPOTENTE",
            dados_pedido=payload
        )
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 4)

    def test_stock_rupture_detection_and_audit_alert(self):
        """Valida que venda com quantidade superior ao saldo gera alerta de ruptura e flag de saldo negativo (RN-05)."""
        payload = {
            'order_id': 'ORD-RUPTURA',
            'total_amount': 2000.00,
            'items': [{'item': {'id': 'MLB776655'}, 'quantity': 8, 'unit_price': 250.00}]
        }

        sucesso, msg, pedido = ProcessamentoPedidoService.processar_pedido_venda(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            pedido_id_externo="ORD-RUPTURA",
            dados_pedido=payload
        )

        self.assertTrue(sucesso)
        self.assertTrue(pedido.teve_ruptura_estoque)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, -3)  # 5 - 8 = -3

        # Verifica se foi gerado o LogAuditoria com o evento ALERTA_RUPTURA_ESTOQUE
        log_ruptura = LogAuditoria.objects.filter(
            loja=self.loja, evento=EventoAuditoriaEnum.ALERTA_RUPTURA_ESTOQUE
        ).exists()
        self.assertTrue(log_ruptura)

    def test_webhook_mercadolivre_view_endpoint(self):
        """Valida o recebimento HTTP no endpoint de Webhook."""
        payload = {
            'resource': '/orders/999111222',
            'topic': 'orders_v2',
            'id': '999111222',
            'user_id': '999888',
            'total_amount': 250.00,
            'items': [{'item': {'id': 'MLB776655'}, 'quantity': 1, 'unit_price': 250.00}]
        }

        response = self.client.post(
            reverse('webhook_mercadolivre'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Confirma que o pedido foi gravado
        self.assertTrue(PedidoVenda.objects.filter(pedido_id_externo='999111222').exists())

    def test_webhook_shopee_and_magalu_endpoints(self):
        """Valida os endpoints de webhooks dos canais Shopee e Magalu."""
        res_shopee = self.client.post(
            reverse('webhook_shopee'),
            data=json.dumps({'order_sn': 'SHP_ORDER_99', 'total_amount': 150.00}),
            content_type='application/json'
        )
        self.assertEqual(res_shopee.status_code, 200)
        self.assertTrue(PedidoVenda.objects.filter(pedido_id_externo='SHP_ORDER_99').exists())

        res_magalu = self.client.post(
            reverse('webhook_magalu'),
            data=json.dumps({'code': 'MAG_ORDER_88', 'total_amount': 300.00}),
            content_type='application/json'
        )
        self.assertEqual(res_magalu.status_code, 200)
        self.assertTrue(PedidoVenda.objects.filter(pedido_id_externo='MAG_ORDER_88').exists())

    def test_webhook_mlb_venda_real_quantity_2_and_pedidos_screen(self):
        """
        Valida que venda real no Mercado Livre com quantidade 2:
        1. Abate exatamente 2 unidades do Produto (5 -> 3).
        2. Cria a entidade Pedido com valor total, dados do comprador e itens correspondentes.
        3. Permite acesso via aliases Pedido/ItemPedido (numero_pedido, canal, conta).
        4. Torna o pedido visível na listagem /pedidos/.
        """
        anuncio_ml = Anuncio.objects.create(
            conta=self.conta_ml,
            item_id_externo="MLB2856546762",
            titulo="Teclado Mecânico RGB Pro Anúncio",
            preco_venda=Decimal('250.00'),
            estoque_publicado=5,
            status_sincronizacao='ENVIADO',
            status='active'
        )
        AnuncioComposicao.objects.create(
            anuncio=anuncio_ml,
            produto=self.produto,
            quantidade=1
        )

        payload = {
            'topic': 'orders_v2',
            'resource': '/orders/40000012345678',
            'id': '40000012345678',
            'user_id': '999888',
            'total_amount': 500.00,
            'buyer': {'name': 'Ana Silva', 'nickname': 'anasilva'},
            'items': [
                {
                    'item': {'id': 'MLB2856546762', 'title': 'Teclado Mecânico RGB Pro Anúncio'},
                    'quantity': 2,
                    'unit_price': 250.00
                }
            ]
        }

        # Envia webhook via rota de pedidos
        response = self.client.post(
            reverse('webhook_mercadolivre'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # 1. Estoque físico reduzido de 5 para 3
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 3)

        # 2. Pedido e ItemPedido criados
        pedido = Pedido.objects.filter(pedido_id_externo='40000012345678').first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.numero_pedido, '40000012345678')
        self.assertEqual(pedido.canal, CanalMarketplaceEnum.MERCADOLIVRE)
        self.assertEqual(pedido.conta, self.conta_ml)
        self.assertEqual(pedido.valor_total, Decimal('500.00'))
        self.assertEqual(pedido.itens.count(), 1)

        item = pedido.itens.first()
        self.assertEqual(item.quantidade, 2)
        self.assertEqual(item.produto, self.produto)
        self.assertEqual(item.estoque_anterior, 5)
        self.assertEqual(item.estoque_posterior, 3)

        # 3. Visível na tela /pedidos/
        self.client.force_login(self.user)
        res_tela = self.client.get(reverse('pedido_list'))
        self.assertEqual(res_tela.status_code, 200)
        self.assertContains(res_tela, '40000012345678')

        # 4. Histórico de Alteração de Preço e Estoque registrado
        historico = HistoricoPreco.objects.filter(produto=self.produto).latest('criado_em')
        self.assertEqual(historico.estoque_anterior, 5)
        self.assertEqual(historico.estoque_novo, 3)
        self.assertEqual(historico.preco_anterior, Decimal('250.00'))
        self.assertEqual(historico.preco_novo, Decimal('250.00'))
        self.assertIn('40000012345678', historico.motivo)

    def test_historico_preco_estoque_gravado_na_baixa_de_venda(self):
        """
        Valida que ao processar um pedido com baixa atômica de estoque:
        1. É persistido o registro em HistoricoPreco.
        2. Mantém preco_anterior e novo_preco iguais ao preço do produto.
        3. Registra estoque_anterior e novo_estoque corretos.
        4. Define usuario responsável (admin da loja) e motivo com canal e id externo.
        """
        payload = {
            'order_id': 'ORD-HIST-01',
            'total_amount': 250.00,
            'buyer': {'name': 'Cliente Historico'},
            'items': [
                {
                    'item': {'id': 'MLB776655', 'title': 'Teclado Mecânico RGB Pro'},
                    'quantity': 1,
                    'unit_price': 250.00
                }
            ]
        }

        sucesso, msg, pedido = ProcessamentoPedidoService.processar_pedido_venda(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            pedido_id_externo="ORD-HIST-01",
            dados_pedido=payload,
            conta=self.conta_ml
        )

        self.assertTrue(sucesso)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 4)

        historico = HistoricoPreco.objects.filter(produto=self.produto, estoque_novo=4).first()
        self.assertIsNotNone(historico)
        self.assertEqual(historico.loja, self.loja)
        self.assertEqual(historico.preco_anterior, Decimal('250.00'))
        self.assertEqual(historico.preco_novo, Decimal('250.00'))
        self.assertEqual(historico.estoque_anterior, 5)
        self.assertEqual(historico.estoque_novo, 4)
        self.assertEqual(historico.usuario, self.user)
        self.assertIn("ORD-HIST-01", historico.motivo)
        self.assertIn("Mercado Livre", historico.motivo)

    def test_processamento_pedido_combo_multiproduto_baixa_atomica_ordenada(self):
        """
        Valida que o processamento de pedido de um Combo Multi-Produto (ADR-009):
        1. Localiza a composição do Anuncio moderno.
        2. Deduz de forma atômica e proporcional o saldo de cada componente (Produto A x 2 + Produto B x 3).
        3. Registra HistoricoPreco para cada um dos produtos deduzidos.
        4. Recalcula e atualiza estoque_publicado no Anuncio.
        5. Detecta ruptura se algum dos componentes atingir saldo negativo.
        """
        # Cria Produto A (estoque=10) e Produto B (estoque=15)
        prod_a = Produto.objects.create(
            loja=self.loja, categoria=self.categoria, sku="COMBO-PROD-A", nome="Produto A Combo",
            preco=Decimal('50.00'), estoque=10
        )
        prod_b = Produto.objects.create(
            loja=self.loja, categoria=self.categoria, sku="COMBO-PROD-B", nome="Produto B Combo",
            preco=Decimal('30.00'), estoque=15
        )

        anuncio_combo = Anuncio.objects.create(
            conta=self.conta_ml,
            item_id_externo="MLB-COMBO-ORDER",
            titulo="Combo Especial 2x A + 3x B",
            preco_venda=Decimal('180.00'),
            estoque_publicado=5
        )
        AnuncioComposicao.objects.create(anuncio=anuncio_combo, produto=prod_a, quantidade=2)
        AnuncioComposicao.objects.create(anuncio=anuncio_combo, produto=prod_b, quantidade=3)

        # Cota inicial: min(10//2, 15//3) = min(5, 5) = 5
        self.assertEqual(anuncio_combo.calcular_cota_disponivel(), 5)

        # Venda de 2 unidades do Combo:
        # Produto A deve baixar: 2 * 2 = 4 un. (10 -> 6)
        # Produto B deve baixar: 2 * 3 = 6 un. (15 -> 9)
        payload = {
            'order_id': 'ORD-COMBO-01',
            'total_amount': 360.00,
            'buyer': {'name': 'Comprador Combo'},
            'items': [
                {
                    'item': {'id': 'MLB-COMBO-ORDER', 'title': 'Combo Especial 2x A + 3x B'},
                    'quantity': 2,
                    'unit_price': 180.00
                }
            ]
        }

        sucesso, msg, pedido = ProcessamentoPedidoService.processar_pedido_venda(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            pedido_id_externo="ORD-COMBO-01",
            dados_pedido=payload,
            conta=self.conta_ml
        )

        self.assertTrue(sucesso)
        self.assertFalse(pedido.teve_ruptura_estoque)

        prod_a.refresh_from_db()
        prod_b.refresh_from_db()
        self.assertEqual(prod_a.estoque, 6)
        self.assertEqual(prod_b.estoque, 9)

        # Anúncio deve ter estoque_publicado atualizado para nova cota min(6//2, 9//3) = 3
        anuncio_combo.refresh_from_db()
        self.assertEqual(anuncio_combo.estoque_publicado, 3)

        # Históricos registrados para ambos
        hist_a = HistoricoPreco.objects.filter(produto=prod_a).latest('criado_em')
        self.assertEqual(hist_a.estoque_anterior, 10)
        self.assertEqual(hist_a.estoque_novo, 6)

        hist_b = HistoricoPreco.objects.filter(produto=prod_b).latest('criado_em')
        self.assertEqual(hist_b.estoque_anterior, 15)
        self.assertEqual(hist_b.estoque_novo, 9)

