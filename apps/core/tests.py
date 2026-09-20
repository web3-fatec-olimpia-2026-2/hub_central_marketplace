# Os códigos foram gerados com auxilio de I.A.
"""
Suíte de Testes Automatizados para a Funcionalidade de Testes de Concorrência e Locks Transacionais.
Valida os fluxos de Lock Pessimista (Estoque) e Double-Checked Locking (OAuth) dos ADRs 004, 005 e 008.
"""
import json
from decimal import Decimal
from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.catalogo.models import Categoria, Produto
from apps.catalogo.enums import StatusProdutoEnum
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import CanalMarketplaceEnum
from .services_testes import ConcorrenciaEstoqueTestService, ConcorrenciaOAuthTestService


class ConcorrenciaTestesCase(TransactionTestCase):
    """
    Testes de integração e unidade para as views e serviços de concorrência.
    """

    def setUp(self):
        self.client = Client()

        # Loja Tenant
        self.loja = Loja.objects.create(
            nome="Loja Laboratório Concorrência",
            slug="loja-lab-concorrencia",
            cnpj="11.222.333/0001-44"
        )

        # Usuário Autenticado
        self.user = User.objects.create_user(
            username="analista_concorrencia",
            email="analista@hub.local",
            password="testpassword123"
        )
        self.perfil = PerfilUsuario.objects.create(
            usuario=self.user,
            papel=PapelUsuarioEnum.ADMIN,
            loja=self.loja
        )

        # Categoria e Produto
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Informática",
            slug="informatica"
        )
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="SSD NVMe 1TB High Speed",
            sku="SSD-NVME-1TB",
            preco=Decimal('350.00'),
            estoque=25,
            status=StatusProdutoEnum.ATIVO
        )

        # Conta Marketplace
        self.conta = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="Mercado Livre Lab Test",
            seller_id_externo="987654321",
            ativo=True,
            is_mock=True,
            access_token="INITIAL_TOKEN",
            refresh_token="INITIAL_REFRESH",
            token_expira_em=timezone.now()
        )

        self.url_concorrencia = reverse('testes_concorrencia')

    def test_acesso_anonimo_redireciona_login(self):
        """Usuário não autenticado deve ser redirecionado para a página de login."""
        response = self.client.get(self.url_concorrencia)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_acesso_autenticado_retorna_200_com_template(self):
        """Usuário autenticado visualiza a página e templates de testes corretamente."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        response = self.client.get(self.url_concorrencia)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'testes/concorrencia.html')
        self.assertContains(response, "SSD NVMe 1TB High Speed")
        self.assertContains(response, "Mercado Livre Lab Test")
        self.assertContains(response, "Painel A: Baixa Concorrente de Stock")
        self.assertContains(response, "Painel B: Concorrência OAuth & Double-Checked Locking")

    def test_navbar_contem_item_testes(self):
        """A barra de navegação deve exibir o link Testes direcionando para a rota central."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        response = self.client.get(self.url_concorrencia)
        self.assertContains(response, 'href="/testes/concorrencia/"')
        self.assertContains(response, 'Testes')

    def test_validacao_delay_invalido(self):
        """Atrasos menores que 100 ms ou maiores que 10.000 ms devem ser estritamente rejeitados."""
        # Menor que 100 ms
        with self.assertRaises(ValueError) as ctx_baixo:
            ConcorrenciaEstoqueTestService.validar_delay(50)
        self.assertIn("100 ms e 10.000 ms", str(ctx_baixo.exception))

        # Maior que 10.000 ms
        with self.assertRaises(ValueError) as ctx_alto:
            ConcorrenciaEstoqueTestService.validar_delay(15000)
        self.assertIn("100 ms e 10.000 ms", str(ctx_alto.exception))

    def test_servico_concorrencia_estoque_execucao_com_sucesso(self):
        """
        Valida a execução paralela das duas threads no estoque:
        - Thread 1 e Thread 2 realizam deduções simultâneas.
        - Não há Lost Updates: Saldo Final = Saldo Inicial - (Qtd1 + Qtd2).
        - Latência na fila de retenção da Thread 2 é mensurada.
        """
        saldo_inicial = self.produto.estoque
        qtd1 = 2
        qtd2 = 3
        delay_ms = 150

        resultado = ConcorrenciaEstoqueTestService.executar_teste(
            produto_id=self.produto.id,
            qtd1=qtd1,
            qtd2=qtd2,
            delay_ms=delay_ms
        )

        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['saldo_inicial'], saldo_inicial)
        self.assertEqual(resultado['saldo_final'], saldo_inicial - (qtd1 + qtd2))
        self.assertTrue(resultado['consistente'])
        self.assertEqual(resultado['thread1']['status'], 'SUCESSO')
        self.assertEqual(resultado['thread2']['status'], 'SUCESSO')
        self.assertGreater(resultado['tempo_espera_thread2_ms'], 0)

        # Checagem na base de dados
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, saldo_inicial - (qtd1 + qtd2))

    def test_servico_concorrencia_oauth_double_checked_locking(self):
        """
        Valida o Lock Pessimista e Double-Checked Locking na renovação de credenciais OAuth:
        - Thread 1 adquire lock e realiza renovação.
        - Thread 2 aguarda na trava e detecta credencial renovada (reaproveitado = True).
        - A API externa é acionada estritamente 1 única vez.
        """
        delay_ms = 150

        resultado = ConcorrenciaOAuthTestService.executar_teste(
            conta_id=self.conta.id,
            delay_ms=delay_ms
        )

        self.assertTrue(resultado['sucesso'])
        self.assertTrue(resultado['reaproveitado'])
        self.assertEqual(resultado['total_chamadas_api'], 1)
        self.assertEqual(resultado['thread1']['chamadas_api_externa'], 1)
        self.assertEqual(resultado['thread2']['chamadas_api_externa'], 0)
        self.assertGreater(resultado['tempo_espera_thread2_ms'], 0)

        # Checagem no banco: nova data de expiração no futuro
        self.conta.refresh_from_db()
        self.assertGreater(self.conta.token_expira_em, timezone.now())

    def test_endpoint_post_teste_estoque_json(self):
        """Testa disparo do teste de estoque via requisição AJAX JSON na view."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        payload = {
            'acao': 'teste_estoque',
            'produto_id': self.produto.id,
            'qtd1': 1,
            'qtd2': 2,
            'delay_ms': 120
        }
        response = self.client.post(
            self.url_concorrencia,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertTrue(data['consistente'])
        self.assertEqual(data['saldo_final'], 25 - 3)

    def test_endpoint_post_teste_oauth_json(self):
        """Testa disparo do teste de OAuth via requisição AJAX JSON na view."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        payload = {
            'acao': 'teste_oauth',
            'conta_id': self.conta.id,
            'delay_ms': 120
        }
        response = self.client.post(
            self.url_concorrencia,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertTrue(data['reaproveitado'])
        self.assertEqual(data['total_chamadas_api'], 1)

    def test_endpoint_post_delay_invalido_retorna_400(self):
        """Post com delay fora da faixa 100..10000 deve retornar HTTP 400 com erro amigável."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        payload = {
            'acao': 'teste_estoque',
            'produto_id': self.produto.id,
            'qtd1': 1,
            'qtd2': 2,
            'delay_ms': 50  # Inválido: < 100 ms
        }
        response = self.client.post(
            self.url_concorrencia,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['sucesso'])
        self.assertIn("100 ms e 10.000 ms", data['erro'])
