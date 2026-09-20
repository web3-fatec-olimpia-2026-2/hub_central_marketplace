# Os códigos foram gerados com auxilio de I.A.
"""
Suíte de Testes Automatizados para o Laboratório de Testes de Concorrência e Resiliência.
Valida:
1. Controle de Acesso Estrito RBAC: Exclusivo para perfil DEV (403 para ADMIN/SUPERVISOR/USUARIO).
2. Teste 1 (Estoque): Lock Pessimista com 3 requisições simultâneas, medição de trava (0 a 10.000 ms)
   e gravação de auditoria em HistoricoPreco com carimbos dia/mês/ano - hh:mm:ss.SSS.
3. Teste 2 (OAuth): Lock Pessimista e Double-Checked Locking com 3 requisições simultâneas.
4. Validação de parâmetros (quantidades obrigatórias e limite de 0 a 10.000 ms).
"""
import json
import re
from decimal import Decimal
from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.catalogo.models import Categoria, Produto, HistoricoPreco
from apps.catalogo.enums import StatusProdutoEnum
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import CanalMarketplaceEnum
from .services_testes import (
    ConcorrenciaEstoqueTestService,
    ConcorrenciaOAuthTestService,
    formatar_timestamp_ms,
)


class ConcorrenciaLaboratorioTestesCase(TransactionTestCase):
    """
    Testes de integração, permissão RBAC e serviços de concorrência com 3 requisições simultâneas.
    """

    def setUp(self):
        self.client = Client()

        # Loja Tenant
        self.loja = Loja.objects.create(
            nome="Loja Laboratório Concorrência",
            slug="loja-lab-concorrencia",
            cnpj="11.222.333/0001-44"
        )

        # Usuário DEV (Permissão Concedida)
        self.user_dev = User.objects.create_user(
            username="dev_concorrencia",
            email="dev@hub.local",
            password="testpassword123"
        )
        self.perfil_dev = PerfilUsuario.objects.create(
            usuario=self.user_dev,
            papel=PapelUsuarioEnum.DEV,
            loja=self.loja
        )

        # Usuário ADMIN (Acesso Bloqueado pelo RBAC DEV-only)
        self.user_admin = User.objects.create_user(
            username="admin_loja",
            email="admin@hub.local",
            password="testpassword123"
        )
        self.perfil_admin = PerfilUsuario.objects.create(
            usuario=self.user_admin,
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
            estoque=50,
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

        # URLs das views dedicadas
        self.url_dashboard = reverse('testes_dashboard')
        self.url_estoque = reverse('teste_concorrencia_estoque')
        self.url_oauth = reverse('teste_concorrencia_oauth')

    # =========================================================================
    # TESTES DE RBAC (ESTRITAMENTE DEV-ONLY)
    # =========================================================================

    def test_acesso_anonimo_redireciona_login(self):
        """Usuário não autenticado deve ser redirecionado para a página de login em todas as rotas."""
        for url in [self.url_dashboard, self.url_estoque, self.url_oauth]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/auth/login/', response.url)

    def test_usuario_nao_dev_recebe_403_forbidden(self):
        """Usuário com papel ADMIN (não-DEV) deve receber 403 Forbidden ao tentar acessar os testes."""
        self.client.login(username="admin_loja", password="testpassword123")
        for url in [self.url_dashboard, self.url_estoque, self.url_oauth]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_usuario_dev_acessa_com_sucesso(self):
        """Usuário com papel DEV deve acessar o dashboard e ambas as views com status 200."""
        self.client.login(username="dev_concorrencia", password="testpassword123")

        # Hub intermediário
        res_dash = self.client.get(self.url_dashboard)
        self.assertEqual(res_dash.status_code, 200)
        self.assertTemplateUsed(res_dash, 'testes/dashboard.html')
        self.assertContains(res_dash, "Baixa Concorrente de Saldo Físico")
        self.assertContains(res_dash, "Renovação Concorrente de Token OAuth")

        # Teste 1 (Estoque)
        res_est = self.client.get(self.url_estoque)
        self.assertEqual(res_est.status_code, 200)
        self.assertTemplateUsed(res_est, 'testes/concorrencia_estoque.html')
        self.assertContains(res_est, "SSD NVMe 1TB High Speed")

        # Teste 2 (OAuth)
        res_oau = self.client.get(self.url_oauth)
        self.assertEqual(res_oau.status_code, 200)
        self.assertTemplateUsed(res_oau, 'testes/concorrencia_oauth.html')
        self.assertContains(res_oau, "Mercado Livre Lab Test")

    # =========================================================================
    # VALIDAÇÃO DE FORMATO DE TIMESTAMPS E PARÂMETROS
    # =========================================================================

    def test_formatar_timestamp_ms_padrao_estrito(self):
        """Valida que formatar_timestamp_ms gera estritamente DD/MM/YYYY - HH:MM:SS.SSS."""
        agora = timezone.now()
        ts_str = formatar_timestamp_ms(agora)
        padrao = r'^\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3}$'
        self.assertRegex(ts_str, padrao)

    def test_validacao_tempo_trava_ms_limites(self):
        """Valida a restrição estrita de 0 a 10.000 ms."""
        self.assertEqual(ConcorrenciaEstoqueTestService.validar_tempo_trava(0), 0)
        self.assertEqual(ConcorrenciaEstoqueTestService.validar_tempo_trava(500), 500)
        self.assertEqual(ConcorrenciaEstoqueTestService.validar_tempo_trava(10000), 10000)

        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.validar_tempo_trava(-1)

        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.validar_tempo_trava(10001)

        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.validar_tempo_trava("invalido")

    def test_validacao_tres_quantidades_obrigatorias(self):
        """As três quantidades de requisição devem ser > 0."""
        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.executar_teste(
                produto_id=self.produto.id,
                qtd1=1,
                qtd2=2,
                qtd3=0
            )

    # =========================================================================
    # EXECUÇÃO DO TESTE 1: ESTOQUE E AUDITORIA EM HISTORICOPRECO
    # =========================================================================

    def test_servico_estoque_executa_e_grava_auditoria_no_historico(self):
        """
        Valida que a execução de 3 requisições simultâneas:
        1. Deduz o estoque corretamente sem Lost Updates.
        2. Registra cada uma das 3 baixas em HistoricoPreco com carimbos formatados.
        3. Registra os carimbos de início, lock e término.
        """
        saldo_inicial = self.produto.estoque
        qtd1, qtd2, qtd3 = 2, 3, 5
        total = qtd1 + qtd2 + qtd3

        resultado = ConcorrenciaEstoqueTestService.executar_teste(
            produto_id=self.produto.id,
            qtd1=qtd1,
            qtd2=qtd2,
            qtd3=qtd3,
            tempo_trava_ms=10,
            user=self.user_dev
        )

        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['saldo_inicial'], saldo_inicial)
        self.assertEqual(resultado['total_deduzido'], total)
        self.assertEqual(resultado['saldo_final'], saldo_inicial - total)
        self.assertTrue(resultado['consistente'])

        # Verifica se o produto no banco foi atualizado
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, saldo_inicial - total)

        # Verifica gravação no log do produto (HistoricoPreco)
        historicos = HistoricoPreco.objects.filter(produto=self.produto).order_by('-criado_em')
        self.assertEqual(historicos.count(), 3)

        padrao_motivo = r'Baixa Concorrente Lock Pessimista - Req \d+ \(baixa de \d+ un\.\) \[Início: \d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3} \| Lock: \d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3} \| Fim: \d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3}\]'
        for h in historicos:
            self.assertEqual(h.usuario, self.user_dev)
            self.assertRegex(h.motivo, padrao_motivo)

    # =========================================================================
    # EXECUÇÃO DO TESTE 2: OAUTH E DOUBLE-CHECKED LOCKING
    # =========================================================================

    def test_servico_oauth_tres_requisicoes_double_checked(self):
        """
        Valida que 3 requisições concorrentes de renovação de token:
        1. Apenas 1 executa chamada externa real.
        2. As outras 2 reaproveitam o token gerado.
        3. Retornam carimbos formatados de início, lock e liberação.
        """
        resultado = ConcorrenciaOAuthTestService.executar_teste(
            conta_id=self.conta.id,
            tempo_trava_ms=10,
            user=self.user_dev
        )

        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['total_chamadas_api'], 1)
        self.assertEqual(resultado['total_reaproveitadas'], 2)
        self.assertGreater(resultado['tempo_total_bloqueio_tabela_ms'], 0)

        # Verifica carimbos formatados
        padrao = r'^\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3}$'
        self.assertRegex(resultado['tempo_inicio_formatado'], padrao)
        self.assertRegex(resultado['tempo_fim_formatado'], padrao)

        self.conta.refresh_from_db()
        self.assertGreater(self.conta.token_expira_em, timezone.now())

    # =========================================================================
    # ENDPOINTS AJAX JSON (POST) COM DEV AUTENTICADO
    # =========================================================================

    def test_endpoint_post_estoque_json(self):
        """Valida POST em /testes/concorrencia/estoque/ retornando JSON completo."""
        self.client.login(username="dev_concorrencia", password="testpassword123")
        payload = {
            'produto_id': self.produto.id,
            'qtd1': 1,
            'qtd2': 2,
            'qtd3': 3,
            'tempo_trava_ms': 0
        }
        response = self.client.post(
            self.url_estoque,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertTrue(data['consistente'])
        self.assertEqual(data['total_deduzido'], 6)
        self.assertIn('tempo_inicio_formatado', data)
        self.assertIn('tempo_fim_formatado', data)

    def test_endpoint_post_oauth_json(self):
        """Valida POST em /testes/concorrencia/oauth/ retornando JSON completo."""
        self.client.login(username="dev_concorrencia", password="testpassword123")
        payload = {
            'conta_id': self.conta.id,
            'tempo_trava_ms': 0
        }
        response = self.client.post(
            self.url_oauth,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['total_chamadas_api'], 1)
        self.assertEqual(data['total_reaproveitadas'], 2)
