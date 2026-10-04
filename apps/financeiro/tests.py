# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo json para serialização de cargas úteis em testes de requisições AJAX
import json

# Importa a classe Decimal para manipulação aritmética exata de moedas e alíquotas sem perda de precisão
from decimal import Decimal

# Importa a classe base TestCase (com isolamento transacional automático) e o cliente HTTP de testes do Django
from django.test import TestCase, Client

# Importa o modelo nativo User para criação e autenticação de usuários nos cenários de teste
from django.contrib.auth.models import User

# Importa o utilitário reverse para resolução dinâmica das URLs nomeadas da aplicação
from django.urls import reverse

# Importa os modelos de Loja (tenant) e Perfil de Usuário para estabelecer o vínculo multi-tenant
from apps.tenancy.models import Loja, PerfilUsuario

# Importa o enum que padroniza os papéis de controle de acesso hierárquico (RBAC)
from apps.tenancy.enums import PapelUsuarioEnum

# Importa as entidades de Categoria e Produto que compõem o catálogo comercial físico
from apps.catalogo.models import Categoria, Produto

# Importa as entidades de parametrização fiscal da loja e regras tarifárias por canal de marketplace
from apps.financeiro.models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace

# Importa a camada de serviço que encapsula a inteligência matemática de simulação promocional
from apps.financeiro.services import SimuladorPromocionalService


# Declaração da classe de testes focada no motor financeiro e simulador promocional
class SimuladorPromocionalTestCase(TestCase):
    # Início da docstring que documenta o objetivo da suíte, fórmulas testadas, RBAC e multi-tenancy
    """
    O QUE FAZ: Suíte de testes automatizados para o Motor de Inteligência Financeira e Simulador Promocional.
    POR QUE FAZ: Valida com precisão a resolução do frete por partes, markup divisor, elasticidade de volume e status de viabilidade.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (Acesso); USUARIO (Bloqueio 403).
    MULTI-TENANCY: Parâmetros fiscais e de canais isolados por loja.
    """
    # Fim da docstring explicativa da suíte de testes

    # Método de preparação do ambiente executado previamente a cada método de teste individual
    def setUp(self):
        # Instancia o simulador de requisições HTTP do Django
        self.client = Client()

        # Cria a organização/loja que servirá de tenant para os testes financeiros
        self.loja = Loja.objects.create(
            nome="Loja Finanças",
            slug="loja-financas",
            cnpj="66.666.666/0001-66"
        )
        # Assegura que os módulos padrão do ecossistema estejam provisionados para esta loja
        self.loja.garantir_modulos_padrao()

        # Configurações fiscais: 4% imposto, R$ 2.50 embalagem padrão, 15% margem mínima
        # Cadastra a parametrização fiscal e de custos fixos da loja tenant
        ConfiguracaoTaxasLoja.objects.create(
            loja=self.loja,
            aliquota_imposto=Decimal('0.0400'),
            custo_embalagem_padrao=Decimal('2.50'),
            margem_minima_seguranca=Decimal('0.1500'),
            custos_fixos_mensais=Decimal('5000.00')
        )

        # Parâmetro Mercado Livre Clássico: 12% comissão, piso R$ 79.00, frete acima R$ 18.00, taxa fixa R$ 6.00
        # Configura as regras tarifárias e de frete do canal Mercado Livre Clássico para esta loja
        ParametroCanalMarketplace.objects.create(
            loja=self.loja,
            marketplace='mercadolivre_classico',
            comissao_padrao=Decimal('0.1200'),
            frete_gratis_piso=Decimal('79.00'),
            taxa_frete_acima_limite=Decimal('18.00'),
            taxa_fixa_abaixo_limite=Decimal('6.00')
        )

        # Cria categoria básica vinculada ao tenant da loja
        self.categoria = Categoria.objects.create(loja=self.loja, nome="Tech", slug="tech")

        # Cria produto base com CMV de R$ 45.00, embalagem de R$ 5.00 e preço de venda de R$ 100.00
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
        # Cria usuário administrador com permissão de acesso aos dados financeiros da loja
        self.user_admin = User.objects.create_user(username='admin_fin', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        # Cria usuário operacional padrão sujeito a bloqueios de governança em relatórios financeiros
        self.user_padrao = User.objects.create_user(username='user_fin', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

    # Teste de validação do cálculo do Custo Variável Unitário (CVu) e o impacto da modalidade Full
    def test_direct_unit_cost_calculation_with_modalidade_full(self):
        """Valida que modalidade_full=True zera o custo de embalagem própria."""
        # Sem Full: 45 + 5 = 50
        # Calcula CVu com logística própria considerando aquisição (45.00) + embalagem própria (5.00)
        cvu_proprio = SimuladorPromocionalService.calcular_custo_direto_unitario(self.produto, Decimal('2.50'))
        # Valida que o CVu resultante é de exatamente R$ 50.00
        self.assertEqual(cvu_proprio, Decimal('50.00'))

        # Com Full: 45 + 0 = 45
        # Altera a modalidade de envio do produto para Fulfillment (Full)
        self.produto.modalidade_full = True
        self.produto.save()
        # Recalcula o CVu e valida que a embalagem própria foi zerada por assumir envio pelo marketplace
        cvu_full = SimuladorPromocionalService.calcular_custo_direto_unitario(self.produto, Decimal('2.50'))
        # Valida que o custo unitário direto resultante passou a ser estritamente R$ 45.00
        self.assertEqual(cvu_full, Decimal('45.00'))

    # Teste de verificação da função linear por partes (Piecewise) que aplica frete ou taxa fixa com base no limiar
    def test_piecewise_freight_resolution(self):
        """Valida a resolução de frete por partes abaixo e acima de R$ 79,00."""
        # Recupera as configurações tarifárias ativas para o canal
        param = ParametroCanalMarketplace.objects.get(loja=self.loja, marketplace='mercadolivre_classico')

        # Abaixo de R$ 79.00 -> R$ 6.00
        # Simula preço de venda de R$ 50.00 (abaixo do corte de R$ 79.00)
        frete_abaixo, _ = SimuladorPromocionalService.calcular_frete_para_preco(Decimal('50.00'), param)
        # Valida se o sistema aplicou a taxa fixa de baixo ticket de R$ 6.00
        self.assertEqual(frete_abaixo, Decimal('6.00'))

        # Acima de R$ 79.00 -> R$ 18.00
        # Simula preço de venda de R$ 100.00 (acima do corte de R$ 79.00)
        frete_acima, _ = SimuladorPromocionalService.calcular_frete_para_preco(Decimal('100.00'), param)
        # Valida se o sistema debitou o frete compulsório de R$ 18.00
        self.assertEqual(frete_acima, Decimal('18.00'))

    # Teste de simulação de campanha com desconto saudável, apuração de margem e cálculo de elasticidade
    def test_promotional_simulation_and_elasticity(self):
        """Valida a simulação de desconto, cálculo de MCU, nova margem e volume de compensação."""
        # Executa a simulação financeira aplicando 10% de desconto sobre o preço de R$ 100.00
        resultado = SimuladorPromocionalService.simular_impacto_promocional(
            produto=self.produto,
            canal_nome='mercadolivre_classico',
            percentual_desconto=Decimal('10.0'),  # 10% desconto: R$ 100 -> R$ 90
            volume_estimado_mensal=100
        )

        # Valida que o preço original apurado foi de R$ 100.00
        self.assertEqual(resultado['preco_original'], 100.00)
        # Valida que o novo preço promocional calculado foi de R$ 90.00
        self.assertEqual(resultado['preco_promocional'], 90.00)
        # Confirma que o status de viabilidade está contido nas categorias válidas do serviço
        self.assertIn(resultado['status_viabilidade'], ['VIAVEL', 'ALERTA_ELASTICIDADE', 'PREJUIZO'])
        # Confirma que para compensar a margem unitária menor, o volume de vendas meta (Q_meta) deve ser superior a 100 un.
        self.assertGreater(resultado['cenario_promocional']['volume_meta'], 100)

    # Teste de proteção de viabilidade: descontos que geram margem negativa devem ser marcados como PREJUIZO
    def test_promotional_simulation_prejuizo_detection(self):
        """Valida que desconto excessivo gerando margem negativa é classificado como PREJUIZO."""
        # 60% de desconto em produto com CVu = 50: Preço R$ 40 < CVu 50
        # Aplica desconto agressivo de 60%, derrubando o preço para R$ 40.00 (inferior ao próprio CVu de R$ 50.00)
        resultado = SimuladorPromocionalService.simular_impacto_promocional(
            produto=self.produto,
            canal_nome='mercadolivre_classico',
            percentual_desconto=Decimal('60.0'),
            volume_estimado_mensal=100
        )

        # Valida que a campanha foi categorizada estritamente com status de 'PREJUIZO'
        self.assertEqual(resultado['status_viabilidade'], 'PREJUIZO')
        # Valida que a meta de volume é nula, pois nenhuma quantidade vendida reverteria o prejuízo unitário
        self.assertIsNone(resultado['cenario_promocional']['volume_meta'])

    # Teste de segurança RBAC: operadores comuns (USUARIO) devem ser barrados com HTTP 403
    def test_usuario_role_blocked_from_simulator_view_with_403(self):
        """Valida que o perfil USUARIO é bloqueado de acessar a view do simulador financeiro (FinancialAccessMixin)."""
        # Autentica com o usuário sem privilégios de gestão financeira
        self.client.login(username='user_fin', password='password123')
        # Tenta acessar via GET a interface do simulador
        response = self.client.get(reverse('simulador_promocional'))
        # Valida que o acesso foi negado com status HTTP 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Autentica com o perfil administrador
        self.client.login(username='admin_fin', password='password123')
        # Tenta acessar novamente a tela do simulador
        response_admin = self.client.get(reverse('simulador_promocional'))
        # Valida que a requisição foi autorizada com status HTTP 200 OK
        self.assertEqual(response_admin.status_code, 200)

    # Teste de integração do endpoint AJAX que devolve a telemetria da simulação em JSON
    def test_simulator_ajax_post_endpoint(self):
        """Valida a requisição AJAX POST no simulador financeiro retornando JSON com os dados calculados."""
        # Autentica o cliente com perfil de administrador
        self.client.login(username='admin_fin', password='password123')
        # Submete requisição POST enviando JSON com os parâmetros da simulação
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
        # Valida retorno HTTP 200 OK
        self.assertEqual(response.status_code, 200)
        # Decodifica a resposta JSON retornada pela view
        data = response.json()
        # Valida que o SKU retornado confere com o produto testado
        self.assertEqual(data['produto_sku'], 'SSD-NVME-1TB')
        # Valida se a alíquota de desconto aplicada foi de 15.0%
        self.assertEqual(data['desconto_aplicado_pct'], 15.0)
        # Valida se o preço com 15% de desconto sobre R$ 100.00 resultou em R$ 85.00
        self.assertEqual(data['preco_promocional'], 85.00)
        # Confirma que a resposta traz as estruturas detalhadas de ambos os cenários
        self.assertIn('cenario_original', data)
        self.assertIn('cenario_promocional', data)


class TaxasEParametrosViewsTestCase(TestCase):
    """
    O QUE FAZ: Testa o controle de acesso RBAC, isolamento multi-tenant e rotas com UUIDv4
              para a gestão de taxas das lojas e parâmetros dos marketplaces.
    """
    def setUp(self):
        self.client = Client()

        self.loja1 = Loja.objects.create(
            nome="Loja Alpha",
            slug="loja-alpha",
            cnpj="11.111.111/0001-11"
        )
        self.loja1.garantir_modulos_padrao()

        self.loja2 = Loja.objects.create(
            nome="Loja Beta",
            slug="loja-beta",
            cnpj="22.222.222/0001-22"
        )
        self.loja2.garantir_modulos_padrao()

        self.config_loja1 = ConfiguracaoTaxasLoja.objects.create(
            loja=self.loja1,
            aliquota_imposto=Decimal('0.0400'),
            custo_embalagem_padrao=Decimal('2.50'),
            margem_minima_seguranca=Decimal('0.1500'),
            custos_fixos_mensais=Decimal('3000.00')
        )

        self.config_loja2 = ConfiguracaoTaxasLoja.objects.create(
            loja=self.loja2,
            aliquota_imposto=Decimal('0.0600'),
            custo_embalagem_padrao=Decimal('3.00'),
            margem_minima_seguranca=Decimal('0.2000'),
            custos_fixos_mensais=Decimal('5000.00')
        )

        self.param_loja1 = ParametroCanalMarketplace.objects.create(
            loja=self.loja1,
            marketplace='mercadolivre_classico',
            comissao_padrao=Decimal('0.1200'),
            frete_gratis_piso=Decimal('79.00'),
            taxa_frete_acima_limite=Decimal('18.00'),
            taxa_fixa_abaixo_limite=Decimal('6.00')
        )

        self.param_loja2 = ParametroCanalMarketplace.objects.create(
            loja=self.loja2,
            marketplace='shopee',
            comissao_padrao=Decimal('0.1400'),
            frete_gratis_piso=Decimal('50.00'),
            taxa_frete_acima_limite=Decimal('15.00'),
            taxa_fixa_abaixo_limite=Decimal('4.00')
        )

        # Usuários
        self.user_dev = User.objects.create_user(username='dev_tester', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PapelUsuarioEnum.DEV, loja=None)

        self.user_admin1 = User.objects.create_user(username='admin_alpha', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin1, papel=PapelUsuarioEnum.ADMIN, loja=self.loja1)

        self.user_comum = User.objects.create_user(username='user_comum', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_comum, papel=PapelUsuarioEnum.USUARIO, loja=self.loja1)

    def test_taxas_loja_list_access_permissions(self):
        """Valida que DEV e ADMIN acessam a listagem de taxas e USUARIO é bloqueado."""
        # Não autenticado -> redireciona login
        res = self.client.get(reverse('taxas_loja_list'))
        self.assertEqual(res.status_code, 302)

        # USUARIO -> 403 Forbidden
        self.client.login(username='user_comum', password='password123')
        res = self.client.get(reverse('taxas_loja_list'))
        self.assertEqual(res.status_code, 403)

        # ADMIN -> 200 OK
        self.client.login(username='admin_alpha', password='password123')
        res = self.client.get(reverse('taxas_loja_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Loja Alpha")

        # DEV -> 200 OK
        self.client.login(username='dev_tester', password='password123')
        res = self.client.get(reverse('taxas_loja_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Loja Alpha")
        self.assertContains(res, "Loja Beta")

    def test_taxas_loja_update_and_tenant_security(self):
        """Valida edição de taxas com UUIDv4 e bloqueio de adulteração cross-tenant."""
        url_loja1 = reverse('taxas_loja_update', kwargs={'public_id': self.config_loja1.public_id})
        url_loja2 = reverse('taxas_loja_update', kwargs={'public_id': self.config_loja2.public_id})

        # ADMIN da Loja 1 tenta acessar taxas da Loja 2 -> 403 Forbidden
        self.client.login(username='admin_alpha', password='password123')
        res = self.client.get(url_loja2)
        self.assertEqual(res.status_code, 403)

        # ADMIN da Loja 1 edita taxas da sua própria loja com sucesso
        res = self.client.post(url_loja1, {
            'aliquota_imposto': '0.0550',
            'custo_embalagem_padrao': '3.50',
            'margem_minima_seguranca': '0.1800',
            'custos_fixos_mensais': '4500.00'
        })
        self.assertEqual(res.status_code, 302)

        self.config_loja1.refresh_from_db()
        self.assertEqual(self.config_loja1.aliquota_imposto, Decimal('0.0550'))
        self.assertEqual(self.config_loja1.custo_embalagem_padrao, Decimal('3.50'))

        # DEV pode editar qualquer loja
        self.client.login(username='dev_tester', password='password123')
        res_dev = self.client.post(url_loja2, {
            'aliquota_imposto': '0.0700',
            'custo_embalagem_padrao': '4.00',
            'margem_minima_seguranca': '0.2200',
            'custos_fixos_mensais': '6000.00'
        })
        self.assertEqual(res_dev.status_code, 302)

        self.config_loja2.refresh_from_db()
        self.assertEqual(self.config_loja2.aliquota_imposto, Decimal('0.0700'))

    def test_parametro_canal_crud_and_tenant_security(self):
        """Valida listagem e edição de parâmetros de canais por UUIDv4."""
        # USUARIO é bloqueado
        self.client.login(username='user_comum', password='password123')
        res = self.client.get(reverse('parametro_canal_list'))
        self.assertEqual(res.status_code, 403)

        # ADMIN da Loja 1 acessa listagem e vê apenas sua loja
        self.client.login(username='admin_alpha', password='password123')
        res = self.client.get(reverse('parametro_canal_list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['parametros']), 1)
        self.assertEqual(res.context['parametros'][0].marketplace, 'mercadolivre_classico')
        self.assertContains(res, "Loja Alpha")
        self.assertNotContains(res, "Loja Beta")

        # ADMIN da Loja 1 tenta editar parâmetro da Loja 2 -> 403 Forbidden
        url_edit_loja2 = reverse('parametro_canal_update', kwargs={'public_id': self.param_loja2.public_id})
        res = self.client.get(url_edit_loja2)
        self.assertEqual(res.status_code, 403)

        # ADMIN da Loja 1 edita parâmetro de sua loja com sucesso
        url_edit_loja1 = reverse('parametro_canal_update', kwargs={'public_id': self.param_loja1.public_id})
        res = self.client.post(url_edit_loja1, {
            'marketplace': 'mercadolivre_classico',
            'comissao_padrao': '0.1300',
            'frete_gratis_piso': '85.00',
            'taxa_frete_acima_limite': '19.50',
            'taxa_fixa_abaixo_limite': '6.50'
        })
        self.assertEqual(res.status_code, 302)

        self.param_loja1.refresh_from_db()
        self.assertEqual(self.param_loja1.comissao_padrao, Decimal('0.1300'))
        self.assertEqual(self.param_loja1.frete_gratis_piso, Decimal('85.00'))

