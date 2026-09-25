# Os códigos foram gerados com auxilio de I.A.

# Importa a classe TestCase para isolamento transacional de banco e Client para simulação de requisições HTTP
from django.test import TestCase, Client

# Importa o modelo User nativo do Django para criação e autenticação de usuários nos testes
from django.contrib.auth.models import User

# Importa a função reverse para resolução dinâmica e resolução reversa de URLs nomeadas
from django.urls import reverse

# Importa a exceção PermissionDenied para validação de bloqueios esperados
from django.core.exceptions import PermissionDenied

# Importa as entidades de modelo Loja (tenant), PerfilUsuario (RBAC) e ModuloLoja (feature flags)
from apps.tenancy.models import Loja, PerfilUsuario, ModuloLoja

# Importa os enums de papéis de usuários (RBAC) e de módulos do sistema
from apps.tenancy.enums import PapelUsuarioEnum, ModuloSistemaEnum

# Importa as funções puras de checagem e matrizes de permissões de RBAC e Tenancy
from apps.tenancy.permissions import (
    usuario_is_dev, usuario_is_admin, pode_criar_usuario, pode_editar_usuario, pode_alterar_papel
)

# Importa a função do context processor que injeta o dicionário de módulos ativos nos templates
from apps.tenancy.context_processors import modulos_loja_context


# Declaração da classe de testes para governança de Tenancy, Feature Flags por loja e integridade RBAC
class TenancyFeatureFlagAndRBACTestCase(TestCase):
    # Início do bloco de docstring estrutural documentando os objetivos da suíte e o isolamento entre tenants
    """
    O QUE FAZ: Suíte de testes automatizados para validação de Tenancy, RBAC e Feature Flags por Loja.
    POR QUE FAZ: Garante que os módulos inativos retornem HTTP 403, que usuários DEV possuam bypass irrestrito e que a matriz de permissões seja cumprida integralmente.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR, USUARIO.
    MULTI-TENANCY: Isolamento horizontal entre Loja 1 e Loja 2.
    """
    # Fim da docstring explicativa da classe de testes

    # Prepara o cenário de teste inicial executado antes de cada método
    def setUp(self):
        # Instancia o cliente HTTP para envio de requisições de teste
        self.client = Client()

        # 1. Criação das Lojas (Tenants)
        # Cria a primeira organização tenant: Loja Alpha em SP
        self.loja_alpha = Loja.objects.create(
            nome="Loja Alpha E-commerce",
            slug="loja-alpha",
            cnpj="11.111.111/0001-11",
            cidade="São Paulo",
            estado="SP"
        )
        # Cria a segunda organização tenant: Loja Beta no RJ para testes de concorrência e isolamento horizontal
        self.loja_beta = Loja.objects.create(
            nome="Loja Beta Varejo",
            slug="loja-beta",
            cnpj="22.222.222/0001-22",
            cidade="Rio de Janeiro",
            estado="RJ"
        )

        # 2. Provisiona módulos para as lojas
        # Garante que ambas as lojas recebam todos os módulos de sistema ativados como padrão inicial
        self.loja_alpha.garantir_modulos_padrao()
        self.loja_beta.garantir_modulos_padrao()

        # 3. Usuários da Loja Alpha
        # Cria o usuário Desenvolvedor (DEV) global, sem vínculo com loja específica
        self.user_dev = User.objects.create_user(username='dev_root', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PapelUsuarioEnum.DEV, loja=None)

        # Cria o Administrador (ADMIN) restrito à Loja Alpha
        self.user_admin_alpha = User.objects.create_user(username='admin_alpha', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin_alpha, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_alpha)

        # Cria o Supervisor (SUPERVISOR) restrito à Loja Alpha
        self.user_supervisor_alpha = User.objects.create_user(username='sup_alpha', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_supervisor_alpha, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja_alpha)

        # Cria o Usuário Operacional comum (USUARIO) restrito à Loja Alpha
        self.user_padrao_alpha = User.objects.create_user(username='user_alpha', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao_alpha, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_alpha)

        # 4. Usuários da Loja Beta
        # Cria o Administrador (ADMIN) restrito à Loja Beta para testes de fronteira de tenant
        self.user_admin_beta = User.objects.create_user(username='admin_beta', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin_beta, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_beta)

    # Valida que o papel DEV possui privilégios de bypass irrestrito e visualiza todas as flags de módulos ativas
    def test_dev_has_global_bypass_and_sees_all_modules_active(self):
        """Valida que o usuário DEV tem bypass e visualiza todos os módulos ativos."""
        # Valida que a função e a propriedade identificam o usuário como DEV
        self.assertTrue(usuario_is_dev(self.user_dev))
        self.assertTrue(self.user_dev.perfil.is_dev)

        # Autentica o usuário DEV no cliente HTTP
        self.client.login(username='dev_root', password='password123')
        # Acessa a tela inicial
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        # Confirma que a flag is_dev injetada pelo context processor está True
        self.assertTrue(response.context['is_dev'])
        # Assegura que todos os módulos do sistema constam como True no dicionário modulos_ativos
        for mod in ModuloSistemaEnum.values:
            self.assertTrue(response.context['modulos_ativos'][mod])

    # Valida o bloqueio estrito com HTTP 403 quando um módulo contratável é desativado para a loja do usuário
    def test_loja_module_toggle_blocks_access_with_403(self):
        """Valida que desativar um módulo para a loja bloqueia o acesso dos seus usuários com HTTP 403."""
        # Desativa o módulo 'financeiro' para a Loja Alpha
        # Recupera o registro da feature flag do módulo financeiro da Loja Alpha e desativa
        mod_fin = ModuloLoja.objects.get(loja=self.loja_alpha, modulo=ModuloSistemaEnum.FINANCEIRO)
        mod_fin.ativo = False
        mod_fin.save()

        # Confirma no modelo que o módulo financeiro da Loja Alpha está inativo
        self.assertFalse(self.loja_alpha.tem_modulo_ativo(ModuloSistemaEnum.FINANCEIRO))

        # Usuário Admin da Loja Alpha tenta acessar a rota do simulador financeiro -> Espera 403
        # Efetua login com o administrador da Loja Alpha
        self.client.login(username='admin_alpha', password='password123')
        # Tenta carregar a view protegida pelo ModuloRequeridoMixin('financeiro')
        response = self.client.get(reverse('simulador_promocional'))
        # Valida que o acesso foi sumariamente barrado com HTTP 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Usuário DEV acessa a mesma rota -> Sucesso 200 (Bypass global)
        # Efetua login com o usuário DEV
        self.client.login(username='dev_root', password='password123')
        # Tenta acessar a mesma rota da qual o lojista foi barrado
        response_dev = self.client.get(reverse('simulador_promocional'))
        # Valida que o desenvolvedor possui bypass irrestrito e obtém HTTP 200 OK
        self.assertEqual(response_dev.status_code, 200)

        # Reativa o módulo financeiro para a Loja Alpha
        # Restaura o status ativo da feature flag do tenant
        mod_fin.ativo = True
        mod_fin.save()

        # Agora o Admin da Loja Alpha consegue acessar com sucesso -> 200
        # Reautentica o administrador da Loja Alpha
        self.client.login(username='admin_alpha', password='password123')
        # Reenvia a requisição HTTP GET para o simulador
        response_reaberto = self.client.get(reverse('simulador_promocional'))
        # Valida que o acesso foi liberado com HTTP 200 OK
        self.assertEqual(response_reaberto.status_code, 200)

    # Valida todas as combinações da matriz de permissões para criação hierárquica de usuários
    def test_rbac_user_creation_matrix(self):
        """Valida a hierarquia de criação de usuários por papel e loja."""
        # DEV pode criar qualquer usuário para qualquer loja
        # Confirma que DEV pode criar ADMIN para a Loja Alpha
        self.assertTrue(pode_criar_usuario(self.user_dev, PapelUsuarioEnum.ADMIN, self.loja_alpha))
        # Confirma que DEV pode criar outro DEV sem loja associada
        self.assertTrue(pode_criar_usuario(self.user_dev, PapelUsuarioEnum.DEV, None))

        # ADMIN pode criar apenas SUPERVISOR e USUARIO na sua própria loja
        # Confirma permissão do ADMIN Alpha para criar SUPERVISOR em sua própria loja
        self.assertTrue(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.SUPERVISOR, self.loja_alpha))
        # Confirma permissão do ADMIN Alpha para criar USUARIO em sua própria loja
        self.assertTrue(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.USUARIO, self.loja_alpha))
        # Bloqueia ADMIN Alpha de criar outro ADMIN (prevenção de escalonamento de privilégios)
        self.assertFalse(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.ADMIN, self.loja_alpha))
        # Bloqueia ADMIN Alpha de criar conta DEV
        self.assertFalse(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.DEV, None))
        # Bloqueia ADMIN Alpha de criar qualquer usuário para a Loja Beta (fronteira multi-tenant)
        self.assertFalse(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.USUARIO, self.loja_beta))

    # Valida as regras de edição e validação de propriedade (ownership check) sobre contas de usuários
    def test_rbac_user_edit_and_ownership(self):
        """Valida que ADMIN edita apenas subordinados da própria loja."""
        # DEV pode editar qualquer usuário
        # Confirma que DEV pode editar o administrador da Loja Alpha
        self.assertTrue(pode_editar_usuario(self.user_dev, self.user_admin_alpha))
        # Confirma que DEV pode editar o administrador da Loja Beta
        self.assertTrue(pode_editar_usuario(self.user_dev, self.user_admin_beta))

        # ADMIN Alpha edita SUPERVISOR e USUARIO da Loja Alpha
        # Autoriza ADMIN Alpha a editar o supervisor de sua própria loja
        self.assertTrue(pode_editar_usuario(self.user_admin_alpha, self.user_supervisor_alpha))
        # Autoriza ADMIN Alpha a editar o operador operacional de sua própria loja
        self.assertTrue(pode_editar_usuario(self.user_admin_alpha, self.user_padrao_alpha))

        # ADMIN Alpha NÃO pode editar DEV, outro ADMIN nem usuários da Loja Beta
        # Bloqueia ADMIN de editar contas de desenvolvedores
        self.assertFalse(pode_editar_usuario(self.user_admin_alpha, self.user_dev))
        # Bloqueia ADMIN de editar o próprio papel de ADMIN (RN de hierarquia administrativa)
        self.assertFalse(pode_editar_usuario(self.user_admin_alpha, self.user_admin_alpha))  # Papel ADMIN bloqueado para ADMIN
        # Bloqueia categoricamente ADMIN Alpha de editar operadores da Loja Beta
        self.assertFalse(pode_editar_usuario(self.user_admin_alpha, self.user_admin_beta))

    # Valida a restrição exclusiva do perfil DEV no acesso à tela de gerenciamento de módulos do tenant
    def test_loja_modulos_view_exclusive_for_dev(self):
        """Valida que a view de configuração de feature flags de loja é restrita ao perfil DEV."""
        # Autentica como ADMIN da Loja Alpha e tenta acessar a rota de feature flags da sua loja
        self.client.login(username='admin_alpha', password='password123')
        res_admin = self.client.get(reverse('loja_modulos', kwargs={'slug': self.loja_alpha.slug}))
        # Assegura que o lojista recebe HTTP 403 Forbidden
        self.assertEqual(res_admin.status_code, 403)

        # Autentica como DEV e acessa a mesma tela de configuração de módulos
        self.client.login(username='dev_root', password='password123')
        res_dev = self.client.get(reverse('loja_modulos', kwargs={'slug': self.loja_alpha.slug}))
        # Valida que o desenvolvedor possui permissão com HTTP 200 OK
        self.assertEqual(res_dev.status_code, 200)

    # Valida que as rotas de CRUD de tenants (Lojas) são acessíveis exclusivamente por desenvolvedores
    def test_loja_crud_views_access_control(self):
        """Valida que apenas DEV pode listar, criar e editar lojas."""
        # Autentica como ADMIN de loja
        self.client.login(username='admin_alpha', password='password123')
        # Assegura que a listagem de lojas e a criação de lojas retornam HTTP 403 Forbidden para administradores comuns
        self.assertEqual(self.client.get(reverse('loja_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('loja_create')).status_code, 403)

        # Autentica como desenvolvedor DEV
        self.client.login(username='dev_root', password='password123')
        # Valida que o DEV consegue acessar a listagem e o formulário de cadastro de novos tenants com HTTP 200 OK
        self.assertEqual(self.client.get(reverse('loja_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('loja_create')).status_code, 200)

        # Criação de nova loja por DEV
        # Submete formulário de criação de nova organização tenant
        res_create = self.client.post(reverse('loja_create'), {
            'nome': 'Loja Gama Express',
            'cnpj': '77.777.777/0001-77',
            'ativo': True
        })
        # Valida redirecionamento pós-criação (HTTP 302) e persistência do registro no banco
        self.assertEqual(res_create.status_code, 302)
        self.assertTrue(Loja.objects.filter(cnpj='77.777.777/0001-77').exists())

    # Valida as operações administrativas de alternância de status ativo/inativo e redefinição de senhas de subordinados
    def test_usuario_toggle_status_and_password_reset(self):
        """Valida a ativação/desativação de usuário e redefinição de senha por gestor."""
        # Autentica como ADMIN da Loja Alpha
        self.client.login(username='admin_alpha', password='password123')

        # Alterna status do subordinado
        # Emite requisição POST para desativar a conta do operador padrão da mesma loja
        res_toggle = self.client.post(reverse('usuario_toggle_status', kwargs={'pk': self.user_padrao_alpha.pk}))
        self.assertEqual(res_toggle.status_code, 302)
        # Recarrega o usuário do banco e valida que a conta foi efetivamente inativada
        self.user_padrao_alpha.refresh_from_db()
        self.assertFalse(self.user_padrao_alpha.is_active)

        # Redefinição de senha
        # Submete formulário com nova senha administrativa para o subordinado
        res_pwd = self.client.post(reverse('usuario_password_reset', kwargs={'pk': self.user_padrao_alpha.pk}), {
            'nova_senha1': 'NovaSenhaForte123',
            'nova_senha2': 'NovaSenhaForte123'
        })
        self.assertEqual(res_pwd.status_code, 302)
        # Recarrega a conta e valida a correspondência do novo hash de senha
        self.user_padrao_alpha.refresh_from_db()
        self.assertTrue(self.user_padrao_alpha.check_password('NovaSenhaForte123'))
