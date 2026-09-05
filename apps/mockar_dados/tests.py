# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Suíte de testes automatizados para a aplicação mockar_dados.
POR QUE FAZ: Valida a injeção de credenciais em modo debug, o provisionamento/exclusão de dados mockados, a preservação do devmaster e os bloqueios de segurança RBAC.
REGRAS DE SEGURANÇA E AMBIENTE:
- Acesso à view restrito exclusivamente ao perfil DEV (403 Forbidden para outros papéis).
- O usuário devmaster NUNCA pode ser excluído pelas rotinas de mock.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum
from apps.catalogo.models import Produto, Categoria, AnuncioMarketplace
from apps.catalogo.enums import StatusProdutoEnum
from apps.marketplaces.models import ContaMarketplace
from .conf import (
    get_dev_debug_username,
    get_dev_debug_password,
    get_dev_debug_email,
)
from .services import MockDataService, garantir_usuario_devmaster
from .context_processors import login_debug_context


class MockarDadosTestCase(TestCase):
    """
    Testes de integridade, governança e execução do gerador de dados mockados.
    """

    def setUp(self):
        self.client = Client()

        # Criação do DEV Master
        self.dev_user = get_dev_debug_username()
        self.dev_pass = get_dev_debug_password() or 'test_password_123'
        self.dev_email = get_dev_debug_email()

        self.user_dev = User.objects.create_user(
            username=self.dev_user,
            email=self.dev_email,
            password=self.dev_pass
        )
        PerfilUsuario.objects.create(
            usuario=self.user_dev,
            papel=PapelUsuarioEnum.DEV,
            loja=None
        )

        # Criação de um usuário comum (não-DEV)
        self.loja_real = Loja.objects.create(
            nome="Loja Real de Produção",
            slug="loja-real",
            cnpj="99.999.999/0001-99"
        )
        self.user_admin = User.objects.create_user(
            username="admin_real",
            password="password123"
        )
        PerfilUsuario.objects.create(
            usuario=self.user_admin,
            papel=PapelUsuarioEnum.ADMIN,
            loja=self.loja_real
        )

    def test_mock_data_generation_and_product_status_balance(self):
        """Valida que gerar dados mockados cria as 3 lojas, 15 produtos com status equilibrados e anúncios."""
        resultado = MockDataService.gerar_dados_mockados()
        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['lojas_criadas'], 3)
        self.assertEqual(resultado['produtos_criados'], 15)

        # Valida que as 3 lojas sintéticas existem com os CNPJs anticoincidência
        lojas = Loja.objects.filter(slug__in=MockDataService.MOCK_SLUGS)
        self.assertEqual(lojas.count(), 3)
        self.assertTrue(Loja.objects.filter(cnpj='11.111.111/0001-11').exists())
        self.assertTrue(Loja.objects.filter(cnpj='22.222.222/0001-22').exists())
        self.assertTrue(Loja.objects.filter(cnpj='33.333.333/0001-33').exists())

        # Valida que cada loja possui 5 produtos e que o status está balanceado (ATIVO vs RASCUNHO)
        for loja in lojas:
            prods = Produto.objects.filter(loja=loja)
            self.assertEqual(prods.count(), 5)
            prods_ativos = prods.filter(status=StatusProdutoEnum.ATIVO).count()
            prods_rascunho = prods.filter(status=StatusProdutoEnum.RASCUNHO).count()
            self.assertEqual(prods_ativos, 3)
            self.assertEqual(prods_rascunho, 2)

        # Valida criação de contas e anúncios
        contas_mock = ContaMarketplace.objects.filter(loja__in=lojas)
        self.assertEqual(contas_mock.count(), 9)  # 3 contas por loja
        anuncios_mock = AnuncioMarketplace.objects.filter(produto__loja__in=lojas)
        self.assertGreater(anuncios_mock.count(), 0)

    def test_mock_data_exclusion_safeguards_devmaster(self):
        """Valida que a exclusão apaga os dados mockados sem alterar ou deletar o devmaster."""
        MockDataService.gerar_dados_mockados()
        self.assertTrue(MockDataService.tem_dados_mockados())

        # Executa a exclusão dos dados mockados
        res_del = MockDataService.excluir_dados_mockados()
        self.assertTrue(res_del['sucesso'])
        self.assertEqual(res_del['lojas_excluidas'], 3)
        self.assertFalse(MockDataService.tem_dados_mockados())

        # devmaster continua existindo e com papel DEV
        self.assertTrue(User.objects.filter(username=self.dev_user).exists())
        dev_user = User.objects.get(username=self.dev_user)
        self.assertEqual(dev_user.perfil.papel, PapelUsuarioEnum.DEV)

        # Loja real e usuários de fora do mock continuam intactos
        self.assertTrue(Loja.objects.filter(slug="loja-real").exists())
        self.assertTrue(User.objects.filter(username="admin_real").exists())

    def test_access_control_only_dev_can_access_mock_dashboard(self):
        """Valida que usuários não-DEV recebem 403 Forbidden e DEV recebe 200 OK."""
        # 1. Usuário ADMIN -> 403 Forbidden
        self.client.login(username='admin_real', password='password123')
        res_admin = self.client.get(reverse('mockar_dados_dashboard'))
        self.assertEqual(res_admin.status_code, 403)

        # 2. Usuário DEV -> 200 OK
        self.client.login(username=self.dev_user, password=self.dev_pass)
        res_dev = self.client.get(reverse('mockar_dados_dashboard'))
        self.assertEqual(res_dev.status_code, 200)
        self.assertContains(res_dev, "Atenção: Este módulo é de uso estrito para testes e desenvolvimento")

    def test_view_post_actions_gerar_and_excluir(self):
        """Valida o fluxo completo de POST na view para gerar e depois excluir dados mockados."""
        self.client.login(username=self.dev_user, password=self.dev_pass)

        # POST acao=gerar
        res_gerar = self.client.post(reverse('mockar_dados_dashboard'), {'acao': 'gerar'})
        self.assertEqual(res_gerar.status_code, 302)
        self.assertTrue(MockDataService.tem_dados_mockados())

        # POST acao=excluir
        res_excluir = self.client.post(reverse('mockar_dados_dashboard'), {'acao': 'excluir'})
        self.assertEqual(res_excluir.status_code, 302)
        self.assertFalse(MockDataService.tem_dados_mockados())

    @override_settings(DEBUG=True, LOGIN_DEBUG=True, LOGIN_DEBUG_USERNAME='devmaster_test', LOGIN_DEBUG_PASSWORD='test_secret_pass_456')
    def test_login_screen_debug_injection_active(self):
        """Valida que a tela de login exibe o badge e credenciais quando DEBUG e LOGIN_DEBUG são True."""
        res_login = self.client.get(reverse('login'))
        self.assertEqual(res_login.status_code, 200)
        self.assertContains(res_login, "Modo Debug: Credenciais de teste injetadas automaticamente (LoginDebug=True)")
        self.assertContains(res_login, 'devmaster_test')
        self.assertContains(res_login, 'test_secret_pass_456')

        # Valida que o usuário e perfil DEV foram provisionados no banco
        self.assertTrue(User.objects.filter(username='devmaster_test').exists())
        user_obj = User.objects.get(username='devmaster_test')
        self.assertTrue(user_obj.check_password('test_secret_pass_456'))
        self.assertEqual(user_obj.perfil.papel, PapelUsuarioEnum.DEV)

    @override_settings(DEBUG=False, LOGIN_DEBUG=False, LOGIN_DEBUG_USERNAME='devmaster_test', LOGIN_DEBUG_PASSWORD='test_secret_pass_456')
    def test_login_screen_debug_injection_inactive(self):
        """Valida que a tela de login NÃO exibe credenciais nem badge quando em produção (DEBUG=False)."""
        res_login = self.client.get(reverse('login'))
        self.assertEqual(res_login.status_code, 200)
        self.assertNotContains(res_login, "Modo Debug: Credenciais de teste injetadas automaticamente")
        self.assertNotContains(res_login, 'devmaster_test')
        self.assertNotContains(res_login, 'test_secret_pass_456')

    @override_settings(DEBUG=True, LOGIN_DEBUG=True, LOGIN_DEBUG_USERNAME='devmaster_sync', LOGIN_DEBUG_PASSWORD='pass_inicial_123')
    def test_garantir_usuario_devmaster_creates_and_updates_password(self):
        """Valida que garantir_usuario_devmaster cria o usuário e atualiza sua senha quando o .env/settings mudar."""
        # 1. Criação inicial
        user = garantir_usuario_devmaster()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'devmaster_sync')
        self.assertTrue(user.check_password('pass_inicial_123'))
        self.assertEqual(user.perfil.papel, PapelUsuarioEnum.DEV)

        # 2. Atualização de senha refletindo nova configuração
        with override_settings(LOGIN_DEBUG_PASSWORD='pass_alterada_789'):
            user_atualizado = garantir_usuario_devmaster()
            self.assertEqual(user_atualizado.id, user.id)
            self.assertTrue(user_atualizado.check_password('pass_alterada_789'))
            self.assertFalse(user_atualizado.check_password('pass_inicial_123'))
