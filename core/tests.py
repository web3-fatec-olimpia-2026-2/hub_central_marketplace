from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from .models import Loja, PerfilUsuario, LogAuditoria
from .enums import PapelUsuarioEnum, EventoAuditoriaEnum
from .forms import LojaForm, UsuarioCreateForm, UsuarioUpdateForm, UsuarioPasswordResetAdminForm
from .permissions import (
    pode_visualizar_usuarios, pode_gerenciar_usuarios, pode_criar_usuario,
    pode_editar_usuario, pode_alterar_papel
)


class LojaModelTestCase(TestCase):
    """
    Testes de integridade do modelo Loja e seus métodos.
    """
    def setUp(self):
        self.loja_data = {
            'nome': 'Loja Matriz E-commerce',
            'cnpj': '12.345.678/0001-90',
            'inscricao_estadual': '123.456.789.111',
            'telefone': '(11) 98765-4321',
            'email': 'contato@lojamt.com.br',
            'cep': '01310-100',
            'endereco': 'Avenida Paulista',
            'numero': '1000',
            'complemento': 'Conjunto 501',
            'bairro': 'Bela Vista',
            'cidade': 'São Paulo',
            'estado': 'SP',
            'pais': 'Brasil',
            'ativo': True,
            'meli_client_id': 'app-meli-123456',
            'meli_client_secret': 'sec-meli-abcdef',
        }

    def test_criar_loja_com_todos_os_campos(self):
        loja = Loja.objects.create(**self.loja_data)
        self.assertEqual(loja.nome, 'Loja Matriz E-commerce')
        self.assertEqual(loja.slug, 'loja-matriz-e-commerce')
        self.assertEqual(loja.cnpj, '12.345.678/0001-90')
        self.assertEqual(loja.cidade, 'São Paulo')
        self.assertEqual(loja.estado, 'SP')
        self.assertTrue(loja.ativo)
        self.assertIn('Avenida Paulista, 1000', loja.endereco_completo)
        self.assertIn('São Paulo/SP', loja.endereco_completo)
        self.assertIn('CEP: 01310-100', loja.endereco_completo)

    def test_geracao_slug_automatico_e_unicidade(self):
        loja1 = Loja.objects.create(nome='Loja Teste', cnpj='11.111.111/0001-11')
        loja2 = Loja.objects.create(nome='Loja Teste', cnpj='22.222.222/0001-22')
        self.assertEqual(loja1.slug, 'loja-teste')
        self.assertEqual(loja2.slug, 'loja-teste-1')

    def test_str_representation(self):
        loja = Loja.objects.create(nome='Loja Alpha', cnpj='33.333.333/0001-33')
        self.assertEqual(str(loja), 'Loja Alpha (33.333.333/0001-33)')


class PerfilUsuarioModelTestCase(TestCase):
    """
    Testes de integridade do modelo PerfilUsuario e regras de multi-tenant / RBAC.
    """
    def setUp(self):
        self.loja = Loja.objects.create(nome='Loja Tenant', cnpj='44.444.444/0001-44')
        self.user_dev = User.objects.create_user(username='user_dev', password='password123')
        self.user_admin = User.objects.create_user(username='user_admin', password='password123')
        self.user_sem_loja = User.objects.create_user(username='user_sem_loja', password='password123')

    def test_perfil_dev_pode_ter_loja_nula(self):
        perfil_dev = PerfilUsuario.objects.create(
            usuario=self.user_dev, papel=PapelUsuarioEnum.DEV, loja=None
        )
        self.assertTrue(perfil_dev.is_dev)
        self.assertFalse(perfil_dev.is_admin)
        self.assertIsNone(perfil_dev.loja)

    def test_perfil_admin_vinculado_a_loja(self):
        perfil_admin = PerfilUsuario.objects.create(
            usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja
        )
        self.assertTrue(perfil_admin.is_admin)
        self.assertFalse(perfil_admin.is_dev)
        self.assertEqual(perfil_admin.loja, self.loja)

    def test_clean_bloqueia_perfil_nao_dev_sem_loja(self):
        perfil = PerfilUsuario(
            usuario=self.user_sem_loja, papel=PapelUsuarioEnum.ADMIN, loja=None
        )
        with self.assertRaises(ValidationError):
            perfil.clean()


class RBACGuardsTestCase(TestCase):
    """
    Testes das funções puras de autorização em core/permissions.py.
    """
    def setUp(self):
        self.loja_a = Loja.objects.create(nome='Loja A', cnpj='11.111.111/0001-11')
        self.loja_b = Loja.objects.create(nome='Loja B', cnpj='22.222.222/0001-22')

        # DEV
        self.dev = User.objects.create_user(username='dev_guard', password='123')
        PerfilUsuario.objects.create(usuario=self.dev, papel=PapelUsuarioEnum.DEV, loja=None)

        # ADMIN A
        self.admin_a = User.objects.create_user(username='admin_a_guard', password='123')
        PerfilUsuario.objects.create(usuario=self.admin_a, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_a)

        # SUPERVISOR A
        self.sup_a = User.objects.create_user(username='sup_a_guard', password='123')
        PerfilUsuario.objects.create(usuario=self.sup_a, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja_a)

        # USUARIO A
        self.usr_a = User.objects.create_user(username='usr_a_guard', password='123')
        PerfilUsuario.objects.create(usuario=self.usr_a, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_a)

        # USUARIO B
        self.usr_b = User.objects.create_user(username='usr_b_guard', password='123')
        PerfilUsuario.objects.create(usuario=self.usr_b, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_b)

    def test_pode_visualizar_usuarios_regras(self):
        self.assertTrue(pode_visualizar_usuarios(self.dev))
        self.assertTrue(pode_visualizar_usuarios(self.admin_a))
        self.assertTrue(pode_visualizar_usuarios(self.sup_a))
        self.assertFalse(pode_visualizar_usuarios(self.usr_a))

    def test_pode_gerenciar_usuarios_regras(self):
        self.assertTrue(pode_gerenciar_usuarios(self.dev))
        self.assertTrue(pode_gerenciar_usuarios(self.admin_a))
        self.assertFalse(pode_gerenciar_usuarios(self.sup_a))
        self.assertFalse(pode_gerenciar_usuarios(self.usr_a))

    def test_pode_criar_usuario_regras(self):
        # DEV pode criar tudo
        self.assertTrue(pode_criar_usuario(self.dev, PapelUsuarioEnum.DEV, None))
        self.assertTrue(pode_criar_usuario(self.dev, PapelUsuarioEnum.ADMIN, self.loja_a))
        self.assertTrue(pode_criar_usuario(self.dev, PapelUsuarioEnum.USUARIO, self.loja_b))

        # ADMIN A só pode criar SUPERVISOR/USUARIO para Loja A
        self.assertTrue(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.SUPERVISOR, self.loja_a))
        self.assertTrue(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.USUARIO, self.loja_a))
        self.assertFalse(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.ADMIN, self.loja_a))
        self.assertFalse(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.DEV, None))
        self.assertFalse(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.USUARIO, self.loja_b))

    def test_pode_editar_usuario_ownership_check(self):
        # DEV pode editar qualquer um
        self.assertTrue(pode_editar_usuario(self.dev, self.admin_a))
        self.assertTrue(pode_editar_usuario(self.dev, self.usr_b))

        # ADMIN A pode editar subordinados da Loja A
        self.assertTrue(pode_editar_usuario(self.admin_a, self.sup_a))
        self.assertTrue(pode_editar_usuario(self.admin_a, self.usr_a))

        # ADMIN A NÃO pode editar usuário da Loja B
        self.assertFalse(pode_editar_usuario(self.admin_a, self.usr_b))

        # ADMIN A NÃO pode editar DEV
        self.assertFalse(pode_editar_usuario(self.admin_a, self.dev))

    def test_pode_alterar_papel_regras(self):
        # Ninguém pode alterar o próprio papel
        self.assertFalse(pode_alterar_papel(self.dev, self.dev, PapelUsuarioEnum.ADMIN))
        self.assertFalse(pode_alterar_papel(self.admin_a, self.admin_a, PapelUsuarioEnum.SUPERVISOR))

        # ADMIN A pode alternar subordinado entre SUPERVISOR e USUARIO
        self.assertTrue(pode_alterar_papel(self.admin_a, self.usr_a, PapelUsuarioEnum.SUPERVISOR))
        self.assertFalse(pode_alterar_papel(self.admin_a, self.usr_a, PapelUsuarioEnum.ADMIN))
        self.assertFalse(pode_alterar_papel(self.admin_a, self.usr_a, PapelUsuarioEnum.DEV))


class UsuarioFormsTestCase(TestCase):
    """
    Testes dos formulários de usuário com controle dinâmico.
    """
    def setUp(self):
        self.loja_a = Loja.objects.create(nome='Loja Form A', cnpj='33.333.333/0001-33')
        self.loja_b = Loja.objects.create(nome='Loja Form B', cnpj='44.444.444/0001-44')

        self.dev = User.objects.create_user(username='dev_form', password='123')
        PerfilUsuario.objects.create(usuario=self.dev, papel=PapelUsuarioEnum.DEV, loja=None)

        self.admin_a = User.objects.create_user(username='admin_form_a', password='123')
        PerfilUsuario.objects.create(usuario=self.admin_a, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_a)

    def test_dev_cria_usuario_com_sucesso(self):
        form_data = {
            'username': 'novo_admin_b',
            'first_name': 'Carlos',
            'last_name': 'Admin',
            'email': 'carlos@loja.com',
            'password1': 'senhaSegura123',
            'password2': 'senhaSegura123',
            'papel': PapelUsuarioEnum.ADMIN,
            'loja': self.loja_b.id,
            'is_active': True,
        }
        form = UsuarioCreateForm(data=form_data, autor=self.dev)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.username, 'novo_admin_b')
        self.assertEqual(user.perfil.papel, PapelUsuarioEnum.ADMIN)
        self.assertEqual(user.perfil.loja, self.loja_b)

    def test_admin_cria_supervisor_com_loja_automatica(self):
        form_data = {
            'username': 'novo_sup_a',
            'first_name': 'Maria',
            'last_name': 'Supervisor',
            'email': 'maria@loja.com',
            'password1': 'senhaSegura123',
            'password2': 'senhaSegura123',
            'papel': PapelUsuarioEnum.SUPERVISOR,
            'is_active': True,
        }
        form = UsuarioCreateForm(data=form_data, autor=self.admin_a)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.perfil.loja, self.loja_a)
        self.assertEqual(user.perfil.papel, PapelUsuarioEnum.SUPERVISOR)

    def test_admin_rejeitado_ao_tentar_forcar_papel_admin(self):
        form_data = {
            'username': 'tentativa_admin',
            'password1': 'senhaSegura123',
            'password2': 'senhaSegura123',
            'papel': PapelUsuarioEnum.ADMIN,
        }
        form = UsuarioCreateForm(data=form_data, autor=self.admin_a)
        self.assertFalse(form.is_valid())


class UsuarioViewsRBACMultiTenantTestCase(TestCase):
    """
    Testes de integração das Views cobrindo a matriz RBAC completa,
    Ownership Checks e registros em LogAuditoria.
    """
    def setUp(self):
        self.client = Client()
        self.loja_a = Loja.objects.create(nome='Loja Alpha', cnpj='55.555.555/0001-55')
        self.loja_b = Loja.objects.create(nome='Loja Beta', cnpj='66.666.666/0001-66')

        # Usuário DEV
        self.dev = User.objects.create_user(username='user_dev_view', password='password123')
        PerfilUsuario.objects.create(usuario=self.dev, papel=PapelUsuarioEnum.DEV, loja=None)

        # ADMIN Loja A
        self.admin_a = User.objects.create_user(username='admin_a_view', password='password123')
        PerfilUsuario.objects.create(usuario=self.admin_a, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_a)

        # SUPERVISOR Loja A
        self.sup_a = User.objects.create_user(username='sup_a_view', password='password123')
        PerfilUsuario.objects.create(usuario=self.sup_a, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja_a)

        # USUARIO Loja A
        self.usr_a = User.objects.create_user(username='usr_a_view', password='password123')
        PerfilUsuario.objects.create(usuario=self.usr_a, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_a)

        # USUARIO Loja B
        self.usr_b = User.objects.create_user(username='usr_b_view', password='password123')
        PerfilUsuario.objects.create(usuario=self.usr_b, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_b)

    # --------------------------------------------------------------------------
    # 1. TESTES DE LISTAGEM (GET /usuarios/)
    # --------------------------------------------------------------------------
    def test_dev_visualiza_usuarios_de_todas_as_lojas(self):
        self.client.login(username='user_dev_view', password='password123')
        response = self.client.get(reverse('usuario_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin_a_view')
        self.assertContains(response, 'usr_b_view')

    def test_admin_visualiza_apenas_usuarios_da_sua_loja(self):
        self.client.login(username='admin_a_view', password='password123')
        response = self.client.get(reverse('usuario_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'usr_a_view')
        self.assertNotContains(response, 'usr_b_view')  # Ownership check no queryset

    def test_supervisor_visualiza_em_modo_leitura(self):
        self.client.login(username='sup_a_view', password='password123')
        response = self.client.get(reverse('usuario_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Modo Somente Leitura')
        self.assertNotContains(response, 'Novo Usuário')

    def test_usuario_padrao_bloqueado_de_acessar_lista(self):
        self.client.login(username='usr_a_view', password='password123')
        response = self.client.get(reverse('usuario_list'))
        self.assertEqual(response.status_code, 403)

    # --------------------------------------------------------------------------
    # 2. TESTES DE CRIAÇÃO (POST /usuarios/novo/)
    # --------------------------------------------------------------------------
    def test_dev_cria_usuario_com_log_de_auditoria(self):
        self.client.login(username='user_dev_view', password='password123')
        post_data = {
            'username': 'novo_usuario_dev_created',
            'first_name': 'Novo',
            'last_name': 'DEV User',
            'email': 'devcreated@test.com',
            'password1': 'senhaForte123',
            'password2': 'senhaForte123',
            'papel': PapelUsuarioEnum.ADMIN,
            'loja': self.loja_b.id,
            'is_active': 'on',
        }
        response = self.client.post(reverse('usuario_create'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        novo_user = User.objects.get(username='novo_usuario_dev_created')
        self.assertEqual(novo_user.perfil.loja, self.loja_b)

        # Verifica gravação em LogAuditoria
        log = LogAuditoria.objects.filter(
            usuario_afetado=novo_user, evento=EventoAuditoriaEnum.CRIACAO_USUARIO
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.autor, self.dev)
        self.assertEqual(log.loja, self.loja_b)

    def test_admin_cria_usuario_subordinado(self):
        self.client.login(username='admin_a_view', password='password123')
        post_data = {
            'username': 'subordinado_loja_a',
            'password1': 'senhaForte123',
            'password2': 'senhaForte123',
            'papel': PapelUsuarioEnum.USUARIO,
            'is_active': 'on',
        }
        response = self.client.post(reverse('usuario_create'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        novo_user = User.objects.get(username='subordinado_loja_a')
        self.assertEqual(novo_user.perfil.loja, self.loja_a)

    def test_supervisor_bloqueado_de_criar_usuario(self):
        self.client.login(username='sup_a_view', password='password123')
        response_get = self.client.get(reverse('usuario_create'))
        self.assertEqual(response_get.status_code, 403)

        response_post = self.client.post(reverse('usuario_create'), data={})
        self.assertEqual(response_post.status_code, 403)

    # --------------------------------------------------------------------------
    # 3. TESTES DE OWNERSHIP CHECK EM EDIÇÃO, STATUS E SENHA
    # --------------------------------------------------------------------------
    def test_admin_loja_a_bloqueado_ao_tentar_editar_usuario_loja_b(self):
        self.client.login(username='admin_a_view', password='password123')
        response = self.client.get(reverse('usuario_update', kwargs={'pk': self.usr_b.pk}))
        self.assertEqual(response.status_code, 403)  # Ownership Check bloqueia!

    def test_admin_loja_a_bloqueado_ao_tentar_desativar_usuario_loja_b(self):
        self.client.login(username='admin_a_view', password='password123')
        response = self.client.post(reverse('usuario_toggle_status', kwargs={'pk': self.usr_b.pk}))
        self.assertEqual(response.status_code, 403)  # Ownership Check bloqueia!

    def test_admin_loja_a_bloqueado_ao_tentar_resetar_senha_usuario_loja_b(self):
        self.client.login(username='admin_a_view', password='password123')
        response = self.client.post(
            reverse('usuario_password_reset', kwargs={'pk': self.usr_b.pk}),
            data={'nova_senha1': 'nova12345', 'nova_senha2': 'nova12345'}
        )
        self.assertEqual(response.status_code, 403)  # Ownership Check bloqueia!

    def test_admin_loja_a_edita_subordinado_e_troca_papel_com_auditoria(self):
        self.client.login(username='admin_a_view', password='password123')
        post_data = {
            'username': self.usr_a.username,
            'first_name': 'Nome Atualizado',
            'last_name': 'Silva',
            'email': 'usr_a@loja.com',
            'papel': PapelUsuarioEnum.SUPERVISOR,  # Promoveu para supervisor
            'is_active': 'on',
        }
        response = self.client.post(
            reverse('usuario_update', kwargs={'pk': self.usr_a.pk}),
            data=post_data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.usr_a.refresh_from_db()
        self.assertEqual(self.usr_a.first_name, 'Nome Atualizado')
        self.assertEqual(self.usr_a.perfil.papel, PapelUsuarioEnum.SUPERVISOR)

        # Valida registro de troca de papel em LogAuditoria
        log = LogAuditoria.objects.filter(
            usuario_afetado=self.usr_a, evento=EventoAuditoriaEnum.TROCA_PAPEL
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.autor, self.admin_a)


