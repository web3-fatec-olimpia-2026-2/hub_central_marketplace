# Os códigos foram gerados com auxilio de I.A.
"""
Suíte de Testes Automatizados para a Funcionalidade de Testes de Concorrência e Locks Transacionais.
Valida os fluxos de Lock Pessimista (Estoque) e Double-Checked Locking (OAuth) com 3 requisições simultâneas.
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
    Testes de integração e unidade para as views e serviços de concorrência com 3 requisições simultâneas.
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
            estoque=30,
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
        self.assertContains(response, "Painel A: Baixa Concorrente de Estoque")
        self.assertContains(response, "Painel B: Concorrência OAuth & Double-Checked Locking")

    def test_navbar_contem_item_testes(self):
        """A barra de navegação deve exibir o link Testes direcionando para a rota central."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        response = self.client.get(self.url_concorrencia)
        self.assertContains(response, 'href="/testes/concorrencia/"')
        self.assertContains(response, 'Testes')

    def test_validacao_tres_quantidades_obrigatorias(self):
        """As três quantidades de requisição devem ser obrigatoriamente preenchidas com valores > 0."""
        with self.assertRaises(ValueError) as ctx:
            ConcorrenciaEstoqueTestService.executar_teste(
                produto_id=self.produto.id,
                qtd1=1,
                qtd2=2,
                qtd3=0  # Inválido: zero
            )
        self.assertIn("obrigatório", str(ctx.exception))

    def test_servico_concorrencia_estoque_tres_requisicoes_simultaneas(self):
        """
        Valida a execução paralela de três requisições concorrentes no estoque:
        - As 3 threads partem no mesmo milissegundo.
        - Saldo Final = Saldo Inicial - (Qtd1 + Qtd2 + Qtd3).
        - Prova matemática confirmada e tempo total de bloqueio medido.
        """
        saldo_inicial = self.produto.estoque
        qtd1 = 2
        qtd2 = 3
        qtd3 = 4
        total_deduzir = qtd1 + qtd2 + qtd3

        resultado = ConcorrenciaEstoqueTestService.executar_teste(
            produto_id=self.produto.id,
            qtd1=qtd1,
            qtd2=qtd2,
            qtd3=qtd3
        )

        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['saldo_inicial'], saldo_inicial)
        self.assertEqual(resultado['total_deduzido'], total_deduzir)
        self.assertEqual(resultado['saldo_final'], saldo_inicial - total_deduzir)
        self.assertTrue(resultado['consistente'])

        # Todas as três threads finalizadas com sucesso
        self.assertEqual(resultado['thread1']['status'], 'SUCESSO')
        self.assertEqual(resultado['thread2']['status'], 'SUCESSO')
        self.assertEqual(resultado['thread3']['status'], 'SUCESSO')
        self.assertGreater(resultado['tempo_total_bloqueio_tabela_ms'], 0)

        # Checagem na base de dados
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, saldo_inicial - total_deduzir)

    def test_servico_concorrencia_oauth_tres_requisicoes_double_checked_locking(self):
        """
        Valida o Lock Pessimista e Double-Checked Locking com 3 requisições simultâneas:
        - 3 requisições disparam no mesmo milissegundo.
        - A primeira renova a credencial (chamadas API = 1).
        - A segunda e a terceira aguardam e ativam o Double-Checked Locking (chamadas API = 0 cada).
        - Total de chamadas à API externa: estritamente 1 chamada.
        """
        resultado = ConcorrenciaOAuthTestService.executar_teste(
            conta_id=self.conta.id
        )

        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['total_chamadas_api'], 1)
        self.assertEqual(resultado['total_reaproveitadas'], 2)
        self.assertGreater(resultado['tempo_total_bloqueio_tabela_ms'], 0)

        # Checagem no banco: nova data de expiração no futuro
        self.conta.refresh_from_db()
        self.assertGreater(self.conta.token_expira_em, timezone.now())

    def test_endpoint_post_teste_estoque_json(self):
        """Testa disparo do teste de estoque via requisição AJAX JSON com 3 quantidades."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        payload = {
            'acao': 'teste_estoque',
            'produto_id': self.produto.id,
            'qtd1': 1,
            'qtd2': 2,
            'qtd3': 3
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
        self.assertEqual(data['total_deduzido'], 6)
        self.assertEqual(data['saldo_final'], 30 - 6)

    def test_endpoint_post_teste_oauth_json(self):
        """Testa disparo do teste de OAuth com 3 requisições via requisição AJAX JSON."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        payload = {
            'acao': 'teste_oauth',
            'conta_id': self.conta.id
        }
        response = self.client.post(
            self.url_concorrencia,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['total_chamadas_api'], 1)
        self.assertEqual(data['total_reaproveitadas'], 2)

    def test_endpoint_post_quantidade_zerada_retorna_400(self):
        """Post com quantidade zerada deve retornar HTTP 400 com mensagem explicativa."""
        self.client.login(username="analista_concorrencia", password="testpassword123")
        payload = {
            'acao': 'teste_estoque',
            'produto_id': self.produto.id,
            'qtd1': 1,
            'qtd2': 0,  # Inválido
            'qtd3': 2
        }
        response = self.client.post(
            self.url_concorrencia,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['sucesso'])
        self.assertIn("obrigatório", data['erro'])
