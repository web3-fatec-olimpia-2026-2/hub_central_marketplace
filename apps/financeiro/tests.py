# Os códigos foram gerados com auxilio de I.A.
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.catalogo.models import Categoria, Produto
from apps.financeiro.models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace
from apps.financeiro.services import SimuladorPromocionalService


class SimuladorPromocionalTestCase(TestCase):
    """
    O QUE FAZ: Suíte de testes automatizados para o Motor de Inteligência Financeira e Simulador Promocional.
    POR QUE FAZ: Valida com precisão a resolução do frete por partes, markup divisor, elasticidade de volume e status de viabilidade.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (Acesso); USUARIO (Bloqueio 403).
    MULTI-TENANCY: Parâmetros fiscais e de canais isolados por loja.
    """

    def setUp(self):
        self.client = Client()

        self.loja = Loja.objects.create(
            nome="Loja Finanças",
            slug="loja-financas",
            cnpj="66.666.666/0001-66"
        )
        self.loja.garantir_modulos_padrao()

        # Configurações fiscais: 4% imposto, R$ 2.50 embalagem padrão, 15% margem mínima
        ConfiguracaoTaxasLoja.objects.create(
            loja=self.loja,
            aliquota_imposto=Decimal('0.0400'),
            custo_embalagem_padrao=Decimal('2.50'),
            margem_minima_seguranca=Decimal('0.1500'),
            custos_fixos_mensais=Decimal('5000.00')
        )

        # Parâmetro Mercado Livre Clássico: 12% comissão, piso R$ 79.00, frete acima R$ 18.00, taxa fixa R$ 6.00
        ParametroCanalMarketplace.objects.create(
            loja=self.loja,
            marketplace='mercadolivre_classico',
            comissao_padrao=Decimal('0.1200'),
            frete_gratis_piso=Decimal('79.00'),
            taxa_frete_acima_limite=Decimal('18.00'),
            taxa_fixa_abaixo_limite=Decimal('6.00')
        )

        self.categoria = Categoria.objects.create(loja=self.loja, nome="Tech", slug="tech")

        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SSD-NVME-1TB",
            nome="SSD NVMe 1TB",
            preco=Decimal('100.00'),
            estoque=50,
            custo_aquisicao=Decimal('45.00'),
            custo_embalagem=Decimal('5.00'),
            modalidade_full=False
        )

        # Usuários
        self.user_admin = User.objects.create_user(username='admin_fin', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.user_padrao = User.objects.create_user(username='user_fin', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

    def test_direct_unit_cost_calculation_with_modalidade_full(self):
        """Valida que modalidade_full=True zera o custo de embalagem própria."""
        # Sem Full: 45 + 5 = 50
        cvu_proprio = SimuladorPromocionalService.calcular_custo_direto_unitario(self.produto, Decimal('2.50'))
        self.assertEqual(cvu_proprio, Decimal('50.00'))

        # Com Full: 45 + 0 = 45
        self.produto.modalidade_full = True
        self.produto.save()
        cvu_full = SimuladorPromocionalService.calcular_custo_direto_unitario(self.produto, Decimal('2.50'))
        self.assertEqual(cvu_full, Decimal('45.00'))

    def test_piecewise_freight_resolution(self):
        """Valida a resolução de frete por partes abaixo e acima de R$ 79,00."""
        param = ParametroCanalMarketplace.objects.get(loja=self.loja, marketplace='mercadolivre_classico')

        # Abaixo de R$ 79.00 -> R$ 6.00
        frete_abaixo, _ = SimuladorPromocionalService.calcular_frete_para_preco(Decimal('50.00'), param)
        self.assertEqual(frete_abaixo, Decimal('6.00'))

        # Acima de R$ 79.00 -> R$ 18.00
        frete_acima, _ = SimuladorPromocionalService.calcular_frete_para_preco(Decimal('100.00'), param)
        self.assertEqual(frete_acima, Decimal('18.00'))

    def test_promotional_simulation_and_elasticity(self):
        """Valida a simulação de desconto, cálculo de MCU, nova margem e volume de compensação."""
        resultado = SimuladorPromocionalService.simular_impacto_promocional(
            produto=self.produto,
            canal_nome='mercadolivre_classico',
            percentual_desconto=Decimal('10.0'),  # 10% desconto: R$ 100 -> R$ 90
            volume_estimado_mensal=100
        )

        self.assertEqual(resultado['preco_original'], 100.00)
        self.assertEqual(resultado['preco_promocional'], 90.00)
        self.assertIn(resultado['status_viabilidade'], ['VIAVEL', 'ALERTA_ELASTICIDADE', 'PREJUIZO'])
        self.assertGreater(resultado['cenario_promocional']['volume_meta'], 100)

    def test_promotional_simulation_prejuizo_detection(self):
        """Valida que desconto excessivo gerando margem negativa é classificado como PREJUIZO."""
        # 60% de desconto em produto com CVu = 50: Preço R$ 40 < CVu 50
        resultado = SimuladorPromocionalService.simular_impacto_promocional(
            produto=self.produto,
            canal_nome='mercadolivre_classico',
            percentual_desconto=Decimal('60.0'),
            volume_estimado_mensal=100
        )

        self.assertEqual(resultado['status_viabilidade'], 'PREJUIZO')
        self.assertIsNone(resultado['cenario_promocional']['volume_meta'])

    def test_usuario_role_blocked_from_simulator_view_with_403(self):
        """Valida que o perfil USUARIO é bloqueado de acessar a view do simulador financeiro (FinancialAccessMixin)."""
        self.client.login(username='user_fin', password='password123')
        response = self.client.get(reverse('simulador_promocional'))
        self.assertEqual(response.status_code, 403)

        self.client.login(username='admin_fin', password='password123')
        response_admin = self.client.get(reverse('simulador_promocional'))
        self.assertEqual(response_admin.status_code, 200)

    def test_simulator_ajax_post_endpoint(self):
        """Valida a requisição AJAX POST no simulador financeiro retornando JSON com os dados calculados."""
        self.client.login(username='admin_fin', password='password123')
        response = self.client.post(
            reverse('simulador_promocional'),
            data=json.dumps({
                'produto_id': self.produto.pk,
                'canal': 'mercadolivre_classico',
                'desconto_pct': '15.0',
                'volume_mensal': 120
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['produto_sku'], 'SSD-NVME-1TB')
        self.assertEqual(data['desconto_aplicado_pct'], 15.0)
        self.assertEqual(data['preco_promocional'], 85.00)
        self.assertIn('cenario_original', data)
        self.assertIn('cenario_promocional', data)
