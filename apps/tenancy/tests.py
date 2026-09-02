# Os códigos foram gerados com auxilio de I.A.
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from apps.tenancy.models import Loja, PerfilUsuario, ModuloLoja
from apps.tenancy.enums import PapelUsuarioEnum, ModuloSistemaEnum
from apps.tenancy.permissions import (
    usuario_is_dev, usuario_is_admin, pode_criar_usuario, pode_editar_usuario, pode_alterar_papel
)
from apps.tenancy.context_processors import modulos_loja_context


class TenancyFeatureFlagAndRBACTestCase(TestCase):
    """
    O QUE FAZ: Suíte de testes automatizados para validação de Tenancy, RBAC e Feature Flags por Loja.
    POR QUE FAZ: Garante que os módulos inativos retornem HTTP 403, que usuários DEV possuam bypass irrestrito e que a matriz de permissões seja cumprida integralmente.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR, USUARIO.
    MULTI-TENANCY: Isolamento horizontal entre Loja 1 e Loja 2.
    """

    def setUp(self):
        self.client = Client()

        # 1. Criação das Lojas (Tenants)
        self.loja_alpha = Loja.objects.create(
            nome="Loja Alpha E-commerce",
            slug="loja-alpha",
            cnpj="11.111.111/0001-11",
            cidade="São Paulo",
            estado="SP"
        )
        self.loja_beta = Loja.objects.create(
            nome="Loja Beta Varejo",
            slug="loja-beta",
            cnpj="22.222.222/0001-22",
            cidade="Rio de Janeiro",
            estado="RJ"
        )

        # 2. Provisiona módulos para as lojas
        self.loja_alpha.garantir_modulos_padrao()
        self.loja_beta.garantir_modulos_padrao()

        # 3. Usuários da Loja Alpha
        self.user_dev = User.objects.create_user(username='dev_root', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PapelUsuarioEnum.DEV, loja=None)

        self.user_admin_alpha = User.objects.create_user(username='admin_alpha', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin_alpha, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_alpha)

        self.user_supervisor_alpha = User.objects.create_user(username='sup_alpha', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_supervisor_alpha, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja_alpha)

        self.user_padrao_alpha = User.objects.create_user(username='user_alpha', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao_alpha, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_alpha)

        # 4. Usuários da Loja Beta
        self.user_admin_beta = User.objects.create_user(username='admin_beta', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin_beta, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_beta)

    def test_dev_has_global_bypass_and_sees_all_modules_active(self):
        """Valida que o usuário DEV tem bypass e visualiza todos os módulos ativos."""
        self.assertTrue(usuario_is_dev(self.user_dev))
        self.assertTrue(self.user_dev.perfil.is_dev)

        self.client.login(username='dev_root', password='password123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_dev'])
        for mod in ModuloSistemaEnum.values:
            self.assertTrue(response.context['modulos_ativos'][mod])

    def test_loja_module_toggle_blocks_access_with_403(self):
        """Valida que desativar um módulo para a loja bloqueia o acesso dos seus usuários com HTTP 403."""
        # Desativa o módulo 'financeiro' para a Loja Alpha
        mod_fin = ModuloLoja.objects.get(loja=self.loja_alpha, modulo=ModuloSistemaEnum.FINANCEIRO)
        mod_fin.ativo = False
        mod_fin.save()

        self.assertFalse(self.loja_alpha.tem_modulo_ativo(ModuloSistemaEnum.FINANCEIRO))

        # Usuário Admin da Loja Alpha tenta acessar a rota do simulador financeiro -> Espera 403
        self.client.login(username='admin_alpha', password='password123')
        response = self.client.get(reverse('simulador_promocional'))
        self.assertEqual(response.status_code, 403)

        # Usuário DEV acessa a mesma rota -> Sucesso 200 (Bypass global)
        self.client.login(username='dev_root', password='password123')
        response_dev = self.client.get(reverse('simulador_promocional'))
        self.assertEqual(response_dev.status_code, 200)

        # Reativa o módulo financeiro para a Loja Alpha
        mod_fin.ativo = True
        mod_fin.save()

        # Agora o Admin da Loja Alpha consegue acessar com sucesso -> 200
        self.client.login(username='admin_alpha', password='password123')
        response_reaberto = self.client.get(reverse('simulador_promocional'))
        self.assertEqual(response_reaberto.status_code, 200)

    def test_rbac_user_creation_matrix(self):
        """Valida a hierarquia de criação de usuários por papel e loja."""
        # DEV pode criar qualquer usuário para qualquer loja
        self.assertTrue(pode_criar_usuario(self.user_dev, PapelUsuarioEnum.ADMIN, self.loja_alpha))
        self.assertTrue(pode_criar_usuario(self.user_dev, PapelUsuarioEnum.DEV, None))

        # ADMIN pode criar apenas SUPERVISOR e USUARIO na sua própria loja
        self.assertTrue(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.SUPERVISOR, self.loja_alpha))
        self.assertTrue(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.USUARIO, self.loja_alpha))
        self.assertFalse(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.ADMIN, self.loja_alpha))
        self.assertFalse(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.DEV, None))
        self.assertFalse(pode_criar_usuario(self.user_admin_alpha, PapelUsuarioEnum.USUARIO, self.loja_beta))

    def test_rbac_user_edit_and_ownership(self):
        """Valida que ADMIN edita apenas subordinados da própria loja."""
        # DEV pode editar qualquer usuário
        self.assertTrue(pode_editar_usuario(self.user_dev, self.user_admin_alpha))
        self.assertTrue(pode_editar_usuario(self.user_dev, self.user_admin_beta))

        # ADMIN Alpha edita SUPERVISOR e USUARIO da Loja Alpha
        self.assertTrue(pode_editar_usuario(self.user_admin_alpha, self.user_supervisor_alpha))
        self.assertTrue(pode_editar_usuario(self.user_admin_alpha, self.user_padrao_alpha))

        # ADMIN Alpha NÃO pode editar DEV, outro ADMIN nem usuários da Loja Beta
        self.assertFalse(pode_editar_usuario(self.user_admin_alpha, self.user_dev))
        self.assertFalse(pode_editar_usuario(self.user_admin_alpha, self.user_admin_alpha))  # Papel ADMIN bloqueado para ADMIN
        self.assertFalse(pode_editar_usuario(self.user_admin_alpha, self.user_admin_beta))

    def test_loja_modulos_view_exclusive_for_dev(self):
        """Valida que a view de configuração de feature flags de loja é restrita ao perfil DEV."""
        self.client.login(username='admin_alpha', password='password123')
        res_admin = self.client.get(reverse('loja_modulos', kwargs={'slug': self.loja_alpha.slug}))
        self.assertEqual(res_admin.status_code, 403)

        self.client.login(username='dev_root', password='password123')
        res_dev = self.client.get(reverse('loja_modulos', kwargs={'slug': self.loja_alpha.slug}))
        self.assertEqual(res_dev.status_code, 200)

    def test_loja_crud_views_access_control(self):
        """Valida que apenas DEV pode listar, criar e editar lojas."""
        self.client.login(username='admin_alpha', password='password123')
        self.assertEqual(self.client.get(reverse('loja_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('loja_create')).status_code, 403)

        self.client.login(username='dev_root', password='password123')
        self.assertEqual(self.client.get(reverse('loja_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('loja_create')).status_code, 200)

        # Criação de nova loja por DEV
        res_create = self.client.post(reverse('loja_create'), {
            'nome': 'Loja Gama Express',
            'cnpj': '77.777.777/0001-77',
            'ativo': True
        })
        self.assertEqual(res_create.status_code, 302)
        self.assertTrue(Loja.objects.filter(cnpj='77.777.777/0001-77').exists())

    def test_usuario_toggle_status_and_password_reset(self):
        """Valida a ativação/desativação de usuário e redefinição de senha por gestor."""
        self.client.login(username='admin_alpha', password='password123')

        # Alterna status do subordinado
        res_toggle = self.client.post(reverse('usuario_toggle_status', kwargs={'pk': self.user_padrao_alpha.pk}))
        self.assertEqual(res_toggle.status_code, 302)
        self.user_padrao_alpha.refresh_from_db()
        self.assertFalse(self.user_padrao_alpha.is_active)

        # Redefinição de senha
        res_pwd = self.client.post(reverse('usuario_password_reset', kwargs={'pk': self.user_padrao_alpha.pk}), {
            'nova_senha1': 'NovaSenhaForte123',
            'nova_senha2': 'NovaSenhaForte123'
        })
        self.assertEqual(res_pwd.status_code, 302)
        self.user_padrao_alpha.refresh_from_db()
        self.assertTrue(self.user_padrao_alpha.check_password('NovaSenhaForte123'))
