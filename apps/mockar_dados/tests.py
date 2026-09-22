# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta os objetivos da suíte de testes e as premissas de segurança
"""
O QUE FAZ: Suíte de testes automatizados para a aplicação mockar_dados.
POR QUE FAZ: Valida a injeção de credenciais em modo debug, o provisionamento/exclusão de dados mockados, a preservação do devmaster e os bloqueios de segurança RBAC.
REGRAS DE SEGURANÇA E AMBIENTE:
- Acesso à view restrito exclusivamente ao perfil DEV (403 Forbidden para outros papéis).
- O usuário devmaster NUNCA pode ser excluído pelas rotinas de mock.
"""
# Fim do bloco de docstring descritivo da suíte

# Importa as classes TestCase para testes transacionais de banco, Client para simular requisições HTTP e o decorador override_settings
from django.test import TestCase, Client, override_settings

# Importa o modelo User nativo do Django para criação e validação de autenticação
from django.contrib.auth.models import User

# Importa a função reverse para resolução dinâmica de rotas nomeadas
from django.urls import reverse

# Importa os modelos Loja e PerfilUsuario para configuração de tenants e papéis de acesso
from apps.tenancy.models import Loja, PerfilUsuario

# Importa a enumeração que define os papéis RBAC suportados pelo sistema
from apps.tenancy.enums import PapelUsuarioEnum

# Importa as entidades de catálogo Produto, Categoria e AnuncioMarketplace
from apps.catalogo.models import Produto, Categoria, AnuncioMarketplace

# Importa o enum de status dos produtos (ATIVO, RASCUNHO, etc.)
from apps.catalogo.enums import StatusProdutoEnum

# Importa o modelo ContaMarketplace para checagem de conexões sintéticas
from apps.marketplaces.models import ContaMarketplace

# Importa as funções para resolução dinâmica das credenciais do usuário DEV
from .conf import (
    get_dev_debug_username,
    get_dev_debug_password,
    get_dev_debug_email,
)

# Importa o serviço central de dados de teste e a rotina de provisionamento do usuário devmaster
from .services import MockDataService, garantir_usuario_devmaster

# Importa a função do context processor que injeta credenciais em tempo de renderização
from .context_processors import login_debug_context


# Declaração da classe de testes de integridade e governança para a aplicação mockar_dados
class MockarDadosTestCase(TestCase):
    # Início do bloco de docstring que descreve a finalidade dos casos de teste
    """
    Testes de integridade, governança e execução do gerador de dados mockados.
    """
    # Fim da docstring explicativa da classe

    # Prepara o cenário inicial executado antes de cada método de teste
    def setUp(self):
        # Instancia o cliente HTTP de testes do Django
        self.client = Client()

        # Criação do DEV Master
        # Recupera as credenciais de teste configuradas dinamicamente
        self.dev_user = get_dev_debug_username()
        self.dev_pass = get_dev_debug_password() or 'test_password_123'
        self.dev_email = get_dev_debug_email()

        # Cria o usuário mestre de desenvolvimento no banco de dados de testes
        self.user_dev = User.objects.create_user(
            username=self.dev_user,
            email=self.dev_email,
            password=self.dev_pass
        )
        # Cria o perfil correspondente atribuindo o papel DEV sem vinculação a nenhuma loja (acesso global)
        PerfilUsuario.objects.create(
            usuario=self.user_dev,
            papel=PapelUsuarioEnum.DEV,
            loja=None
        )

        # Criação de um usuário comum (não-DEV)
        # Cria uma organização tenant legítima que não faz parte do conjunto de mocks
        self.loja_real = Loja.objects.create(
            nome="Loja Real de Produção",
            slug="loja-real",
            cnpj="99.999.999/0001-99"
        )
        # Cria usuário administrador restrito à loja real
        self.user_admin = User.objects.create_user(
            username="admin_real",
            password="password123"
        )
        # Vincula o usuário ao perfil ADMIN da loja real
        PerfilUsuario.objects.create(
            usuario=self.user_admin,
            papel=PapelUsuarioEnum.ADMIN,
            loja=self.loja_real
        )

    # Valida o provisionamento completo dos dados sintéticos e o equilíbrio de status dos produtos
    def test_mock_data_generation_and_product_status_balance(self):
        """Valida que gerar dados mockados cria as 3 lojas, 15 produtos com status equilibrados e anúncios."""
        # Executa o serviço de geração de massa de testes
        resultado = MockDataService.gerar_dados_mockados()
        # Valida que a rotina retornou sucesso e os quantitativos globais esperados
        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['lojas_criadas'], 3)
        self.assertEqual(resultado['produtos_criados'], 15)

        # Valida que as 3 lojas sintéticas existem com os CNPJs anticoincidência
        # Consulta as lojas registradas a partir da lista padrão de slugs mockados
        lojas = Loja.objects.filter(slug__in=MockDataService.MOCK_SLUGS)
        self.assertEqual(lojas.count(), 3)
        # Verifica a presença dos CNPJs sintéticos configurados
        self.assertTrue(Loja.objects.filter(cnpj='11.111.111/0001-11').exists())
        self.assertTrue(Loja.objects.filter(cnpj='22.222.222/0001-22').exists())
        self.assertTrue(Loja.objects.filter(cnpj='33.333.333/0001-33').exists())

        # Valida que cada loja possui 5 produtos e que o status está balanceado (ATIVO vs RASCUNHO)
        # Itera por cada loja validando a proporção de produtos ativos (3) e em rascunho (2)
        for loja in lojas:
            prods = Produto.objects.filter(loja=loja)
            self.assertEqual(prods.count(), 5)
            prods_ativos = prods.filter(status=StatusProdutoEnum.ATIVO).count()
            prods_rascunho = prods.filter(status=StatusProdutoEnum.RASCUNHO).count()
            self.assertEqual(prods_ativos, 3)
            self.assertEqual(prods_rascunho, 2)

        # Valida criação de contas e anúncios
        # Confirma que cada loja recebeu 3 contas integradas (totalizando 9 conexões)
        contas_mock = ContaMarketplace.objects.filter(loja__in=lojas)
        self.assertEqual(contas_mock.count(), 9)  # 3 contas por loja
        # Valida que anúncios foram gerados e vinculados aos produtos ativos
        anuncios_mock = AnuncioMarketplace.objects.filter(produto__loja__in=lojas)
        self.assertGreater(anuncios_mock.count(), 0)

    # Valida a regra de segurança que protege o usuário devmaster contra deleção ao expurgar dados
    def test_mock_data_exclusion_safeguards_devmaster(self):
        """Valida que a exclusão apaga os dados mockados sem alterar ou deletar o devmaster."""
        # Popula o banco com os dados mockados
        MockDataService.gerar_dados_mockados()
        self.assertTrue(MockDataService.tem_dados_mockados())

        # Executa a exclusão dos dados mockados
        # Dispara o método de exclusão atômico
        res_del = MockDataService.excluir_dados_mockados()
        self.assertTrue(res_del['sucesso'])
        self.assertEqual(res_del['lojas_excluidas'], 3)
        self.assertFalse(MockDataService.tem_dados_mockados())

        # devmaster continua existindo e com papel DEV
        # Assegura categoricamente que o devmaster permaneceu intacto na base
        self.assertTrue(User.objects.filter(username=self.dev_user).exists())
        dev_user = User.objects.get(username=self.dev_user)
        self.assertEqual(dev_user.perfil.papel, PapelUsuarioEnum.DEV)

        # Loja real e usuários de fora do mock continuam intactos
        # Valida que dados reais pertencentes a outros tenants não sofreram efeito colateral
        self.assertTrue(Loja.objects.filter(slug="loja-real").exists())
        self.assertTrue(User.objects.filter(username="admin_real").exists())

    # Valida restrições de permissão RBAC no acesso ao dashboard de dados mockados
    def test_access_control_only_dev_can_access_mock_dashboard(self):
        """Valida que usuários não-DEV recebem 403 Forbidden e DEV recebe 200 OK."""
        # 1. Usuário ADMIN -> 403 Forbidden
        # Autentica o usuário administrador da loja real
        self.client.login(username='admin_real', password='password123')
        # Tenta acessar o painel de mockar dados e valida a negação com HTTP 403
        res_admin = self.client.get(reverse('mockar_dados_dashboard'))
        self.assertEqual(res_admin.status_code, 403)

        # 2. Usuário DEV -> 200 OK
        # Autentica o superusuário de desenvolvimento
        self.client.login(username=self.dev_user, password=self.dev_pass)
        # Acessa o painel e valida o sucesso HTTP 200
        res_dev = self.client.get(reverse('mockar_dados_dashboard'))
        self.assertEqual(res_dev.status_code, 200)
        # Confirma que a mensagem de aviso de ambiente está contida no HTML renderizado
        self.assertContains(res_dev, "Atenção: Este módulo é de uso estrito para testes e desenvolvimento")

    # Valida a execução das ações de gerar e excluir via submissão POST na view do dashboard
    def test_view_post_actions_gerar_and_excluir(self):
        """Valida o fluxo completo de POST na view para gerar e depois excluir dados mockados."""
        # Efetua login com o usuário DEV
        self.client.login(username=self.dev_user, password=self.dev_pass)

        # POST acao=gerar
        # Submete requisição POST com a ação 'gerar'
        res_gerar = self.client.post(reverse('mockar_dados_dashboard'), {'acao': 'gerar'})
        # Valida redirecionamento pós-operação (PRG pattern) e existência dos dados no banco
        self.assertEqual(res_gerar.status_code, 302)
        self.assertTrue(MockDataService.tem_dados_mockados())

        # POST acao=excluir
        # Submete requisição POST com a ação 'excluir'
        res_excluir = self.client.post(reverse('mockar_dados_dashboard'), {'acao': 'excluir'})
        # Valida redirecionamento e confirma que a base sintética foi totalmente limpa
        self.assertEqual(res_excluir.status_code, 302)
        self.assertFalse(MockDataService.tem_dados_mockados())

    # Valida injeção visual de credenciais no template de login quando as flags de debug estão ativas
    @override_settings(DEBUG=True, LOGIN_DEBUG=True, LOGIN_DEBUG_USERNAME='devmaster_test', LOGIN_DEBUG_PASSWORD='test_secret_pass_456')
    def test_login_screen_debug_injection_active(self):
        """Valida que a tela de login exibe o badge e credenciais quando DEBUG e LOGIN_DEBUG são True."""
        # Realiza requisição GET na tela de login
        res_login = self.client.get(reverse('login'))
        self.assertEqual(res_login.status_code, 200)
        # Verifica a presença do aviso de debug e das credenciais injetadas na resposta
        self.assertContains(res_login, "Modo Debug: Credenciais de teste injetadas automaticamente (LoginDebug=True)")
        self.assertContains(res_login, 'devmaster_test')
        self.assertContains(res_login, 'test_secret_pass_456')

        # Valida que o usuário e perfil DEV foram provisionados no banco
        # Assegura que o context processor provisionou o usuário no banco de dados
        self.assertTrue(User.objects.filter(username='devmaster_test').exists())
        user_obj = User.objects.get(username='devmaster_test')
        self.assertTrue(user_obj.check_password('test_secret_pass_456'))
        self.assertEqual(user_obj.perfil.papel, PapelUsuarioEnum.DEV)

    # Valida omissão de credenciais e badges na tela de login quando as flags de debug estão desativadas
    @override_settings(DEBUG=False, LOGIN_DEBUG=False, LOGIN_DEBUG_USERNAME='devmaster_test', LOGIN_DEBUG_PASSWORD='test_secret_pass_456')
    def test_login_screen_debug_injection_inactive(self):
        """Valida que a tela de login NÃO exibe credenciais nem badge quando em produção (DEBUG=False)."""
        # Realiza requisição GET na tela de login simulando ambiente produtivo
        res_login = self.client.get(reverse('login'))
        self.assertEqual(res_login.status_code, 200)
        # Assegura que nenhum texto ou credencial sensível de debug foi vazado no HTML
        self.assertNotContains(res_login, "Modo Debug: Credenciais de teste injetadas automaticamente")
        self.assertNotContains(res_login, 'devmaster_test')
        self.assertNotContains(res_login, 'test_secret_pass_456')

    # Valida criação idempotente e atualização automática de senha ao alterar as configurações
    @override_settings(DEBUG=True, LOGIN_DEBUG=True, LOGIN_DEBUG_USERNAME='devmaster_sync', LOGIN_DEBUG_PASSWORD='pass_inicial_123')
    def test_garantir_usuario_devmaster_creates_and_updates_password(self):
        """Valida que garantir_usuario_devmaster cria o usuário e atualiza sua senha quando o .env/settings mudar."""
        # 1. Criação inicial
        # Executa o provisionamento e valida criação do usuário com a senha inicial
        user = garantir_usuario_devmaster()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'devmaster_sync')
        self.assertTrue(user.check_password('pass_inicial_123'))
        self.assertEqual(user.perfil.papel, PapelUsuarioEnum.DEV)

        # 2. Atualização de senha refletindo nova configuração
        # Sobrescreve a configuração de senha e reexecuta o provisionamento
        with override_settings(LOGIN_DEBUG_PASSWORD='pass_alterada_789'):
            user_atualizado = garantir_usuario_devmaster()
            # Valida que o mesmo registro foi reaproveitado e a senha foi alterada com sucesso
            self.assertEqual(user_atualizado.id, user.id)
            self.assertTrue(user_atualizado.check_password('pass_alterada_789'))
            self.assertFalse(user_atualizado.check_password('pass_inicial_123'))
