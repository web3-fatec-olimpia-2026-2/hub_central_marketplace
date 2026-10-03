# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Suíte de testes unitários e de integração para autenticação, salvaguardas RBAC e Matriz Dinâmica (Doc ① §16.2, §17.4 e §17.5).
COBERTURA:
  - Ordem do DOM no login (§16.2).
  - 4 permissões reservadas do ecossistema (§17.5).
  - Controle de acesso à Matriz RBAC (Grupos 0 e 1 recebem 403; Grupos 3 e 4 recebem 200).
  - Persistência dinâmica e reatividade dos switches (toggles).
  - Salvaguardas mandatórias (não-delegação de governança a 0 e 1, bloqueio de auto-revogação de DEV, proteção de DEV contra ADMIN).
  - Geração de registro em LogAuditoria.
  - Renderização do dropdown 'Gestão de Identidade' na NAVBAR conforme perfil.
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from apps.accounts.models import RegraRBAC
from apps.accounts.rbac import (
    tem_funcionalidade, get_grupo_usuario, invalidar_cache_rbac,
    FUNC_ACCOUNTS_MATRIZ, FUNC_ACCOUNTS_ATRIBUIR_PERFIS,
    FUNC_SITE_TEMA_EDITAR, FUNC_SITE_VISIBILIDADE_PUBLICA,
    CATALOGO_FUNCIONALIDADES_RBAC
)
from apps.tenancy.models import Loja, PerfilUsuario, PapelUsuarioEnum
from apps.marketplaces.models import LogAuditoria


class LoginDOMOrderTests(TestCase):
    """Garante que a ordem no DOM do formulário de login atenda ao Doc ① §16.2."""

    def test_ordem_estrita_do_dom_no_login(self):
        """O link 'Esqueci minha senha' deve estar obrigatoriamente ABAIXO do botão Entrar no DOM."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')

        pos_username = html.find('name="username"')
        pos_password = html.find('name="password"')
        pos_submit = html.find('type="submit"')
        pos_forgot_pass = html.find('Esqueci minha senha')

        self.assertNotEqual(pos_username, -1, "Campo username não encontrado")
        self.assertNotEqual(pos_password, -1, "Campo password não encontrado")
        self.assertNotEqual(pos_submit, -1, "Botão submit não encontrado")
        self.assertNotEqual(pos_forgot_pass, -1, "Link 'Esqueci minha senha' não encontrado")

        self.assertTrue(
            pos_username < pos_password < pos_submit < pos_forgot_pass,
            f"Ordem do DOM incorreta! Esperado: username ({pos_username}) < password ({pos_password}) < submit ({pos_submit}) < forgot ({pos_forgot_pass})"
        )


class RBACFuncionalidadesReservadasTests(TestCase):
    """Validação das 4 permissões reservadas do ecossistema (Doc ① §17.5)."""

    def setUp(self):
        self.loja = Loja.objects.create(
            nome="Loja Teste RBAC",
            slug="loja-teste-rbac",
            cnpj="22.333.444/0001-55"
        )
        self.user_dev = User.objects.create_user(username="dev_rbac", password="Password123!")
        self.perfil_dev = PerfilUsuario.objects.create(
            usuario=self.user_dev,
            loja=None,
            papel=PapelUsuarioEnum.DEV
        )

        self.user_admin = User.objects.create_user(username="admin_rbac", password="Password123!")
        self.perfil_admin = PerfilUsuario.objects.create(
            usuario=self.user_admin,
            loja=self.loja,
            papel=PapelUsuarioEnum.ADMIN
        )

        self.user_op = User.objects.create_user(username="usuario_rbac", password="Password123!")
        self.perfil_op = PerfilUsuario.objects.create(
            usuario=self.user_op,
            loja=self.loja,
            papel=PapelUsuarioEnum.USUARIO
        )

    def test_desenvolvedor_possui_todas_as_funcionalidades_reservadas(self):
        """Perfil DEV (Grupo 4) tem acesso irrestrito às 4 permissões reservadas."""
        self.assertEqual(get_grupo_usuario(self.user_dev), 4)
        for func in [FUNC_ACCOUNTS_MATRIZ, FUNC_ACCOUNTS_ATRIBUIR_PERFIS, FUNC_SITE_TEMA_EDITAR, FUNC_SITE_VISIBILIDADE_PUBLICA]:
            self.assertTrue(tem_funcionalidade(self.user_dev, func))

    def test_administrador_possui_funcionalidades_padrao_grupos_3_e_4(self):
        """Perfil ADMIN (Grupo 3) possui as 4 permissões do ecossistema por padrão."""
        self.assertEqual(get_grupo_usuario(self.user_admin), 3)
        for func in [FUNC_ACCOUNTS_MATRIZ, FUNC_ACCOUNTS_ATRIBUIR_PERFIS, FUNC_SITE_TEMA_EDITAR, FUNC_SITE_VISIBILIDADE_PUBLICA]:
            self.assertTrue(tem_funcionalidade(self.user_admin, func))

    def test_usuario_operacional_nao_possui_funcionalidades_reservadas(self):
        """Perfil USUARIO (Grupo 0) não possui acesso às funcionalidades administrativas."""
        self.assertEqual(get_grupo_usuario(self.user_op), 0)
        for func in [FUNC_ACCOUNTS_MATRIZ, FUNC_ACCOUNTS_ATRIBUIR_PERFIS, FUNC_SITE_TEMA_EDITAR, FUNC_SITE_VISIBILIDADE_PUBLICA]:
            self.assertFalse(tem_funcionalidade(self.user_op, func))


class MatrizRBACAccessAndNavbarTests(TestCase):
    """Testes de acesso à View da Matriz RBAC e exibição do dropdown na NAVBAR."""

    def setUp(self):
        self.loja = Loja.objects.create(
            nome="Loja Matriz Test",
            slug="loja-matriz-test",
            cnpj="55.666.777/0001-88"
        )
        self.user_dev = User.objects.create_user(username="dev_matriz", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PapelUsuarioEnum.DEV, loja=None)

        self.user_admin = User.objects.create_user(username="admin_matriz", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.user_supervisor = User.objects.create_user(username="sup_matriz", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_supervisor, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja)

        self.user_usuario = User.objects.create_user(username="user_matriz", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_usuario, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

    def test_usuario_nao_autenticado_redireciona_login(self):
        """Acesso anônimo à matriz redireciona para a página de login."""
        response = self.client.get(reverse('accounts:matriz'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_usuario_padrao_grupo_0_recebe_403_na_matriz(self):
        """Usuário Padrão (Grupo 0) recebe HTTP 403 Forbidden ao acessar /accounts/matriz/."""
        self.client.force_login(self.user_usuario)
        response = self.client.get(reverse('accounts:matriz'))
        self.assertEqual(response.status_code, 403)

    def test_supervisor_grupo_1_recebe_403_na_matriz(self):
        """Supervisor (Grupo 1) recebe HTTP 403 Forbidden ao acessar /accounts/matriz/."""
        self.client.force_login(self.user_supervisor)
        response = self.client.get(reverse('accounts:matriz'))
        self.assertEqual(response.status_code, 403)

    def test_administrador_grupo_3_acessa_matriz_com_sucesso(self):
        """Administrador (Grupo 3) acessa a Matriz RBAC com HTTP 200 OK."""
        self.client.force_login(self.user_admin)
        response = self.client.get(reverse('accounts:matriz'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matriz RBAC de Governança")
        self.assertContains(response, "accounts.matriz")

    def test_desenvolvedor_grupo_4_acessa_matriz_com_sucesso(self):
        """Desenvolvedor (Grupo 4) acessa a Matriz RBAC com HTTP 200 OK."""
        self.client.force_login(self.user_dev)
        response = self.client.get(reverse('accounts:matriz'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matriz RBAC de Governança")

    def test_rota_alias_usuarios_matriz_funciona_identicamente(self):
        """A rota alternativa /usuarios/matriz/ funciona e protege conforme RBAC."""
        self.client.force_login(self.user_usuario)
        res_user = self.client.get('/usuarios/matriz/')
        self.assertEqual(res_user.status_code, 403)

        self.client.force_login(self.user_admin)
        res_admin = self.client.get('/usuarios/matriz/')
        self.assertEqual(res_admin.status_code, 200)

    def test_dropdown_gestao_identidade_na_navbar(self):
        """Valida que a NAVBAR renderiza 'Gestão de Identidade' com os itens protegidos."""
        # 1. ADMIN vê tanto 'Usuários' quanto 'Matriz RBAC'
        self.client.force_login(self.user_admin)
        resp_admin = self.client.get(reverse('usuario_list'))
        html_admin = resp_admin.content.decode('utf-8')
        self.assertIn("Gestão de Identidade", html_admin)
        self.assertIn("Matriz RBAC", html_admin)

        # 2. SUPERVISOR vê 'Gestão de Identidade' com 'Usuários', mas NÃO vê 'Matriz RBAC'
        self.client.force_login(self.user_supervisor)
        resp_sup = self.client.get(reverse('usuario_list'))
        html_sup = resp_sup.content.decode('utf-8')
        self.assertIn("Gestão de Identidade", html_sup)
        self.assertNotIn("Matriz RBAC", html_sup)

        # 3. USUÁRIO comum (Grupo 0) não vê 'Gestão de Identidade'
        self.client.force_login(self.user_usuario)
        resp_op = self.client.get(reverse('home'))
        html_op = resp_op.content.decode('utf-8')
        self.assertNotIn("Gestão de Identidade", html_op)


class MatrizRBACTogglePersistenceAndSafeguardsTests(TestCase):
    """Testes de persistência dinâmica dos switches, salvaguardas mandatórias e auditoria."""

    def setUp(self):
        self.loja = Loja.objects.create(
            nome="Loja Teste Persistencia",
            slug="loja-teste-persistencia",
            cnpj="99.888.777/0001-66"
        )
        self.user_dev = User.objects.create_user(username="dev_toggle", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PapelUsuarioEnum.DEV, loja=None)

        self.user_admin = User.objects.create_user(username="admin_toggle", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        self.user_supervisor = User.objects.create_user(username="sup_toggle", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_supervisor, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja)

        self.user_op = User.objects.create_user(username="user_toggle", password="Password123!")
        PerfilUsuario.objects.create(usuario=self.user_op, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

    def test_persistencia_toggle_concessao_dinamica(self):
        """Conceder uma funcionalidade operacional ao Usuário Padrão via switch deve persistir em banco e atualizar tem_funcionalidade."""
        self.client.force_login(self.user_admin)
        invalidar_cache_rbac()

        # Antes: USUARIO não pode gerenciar categorias
        self.assertFalse(tem_funcionalidade(self.user_op, 'catalogo.categoria_gerenciar'))

        payload = {
            'funcionalidade': 'catalogo.categoria_gerenciar',
            'papel': 'USUARIO',
            'concedido': True
        }
        response = self.client.post(
            reverse('accounts:matriz_toggle'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])

        # Registro persistido no banco de dados
        regra = RegraRBAC.objects.get(funcionalidade='catalogo.categoria_gerenciar', papel='USUARIO')
        self.assertTrue(regra.concedido)

        # Checagem em tempo real via tem_funcionalidade
        self.assertTrue(tem_funcionalidade(self.user_op, 'catalogo.categoria_gerenciar'))

    def test_persistencia_toggle_revogacao_dinamica(self):
        """Revogar uma permissão de Supervisor deve ser persistida com sucesso."""
        self.client.force_login(self.user_admin)
        invalidar_cache_rbac()

        # Por padrão Supervisor pode ver logs
        self.assertTrue(tem_funcionalidade(self.user_supervisor, 'core.logs_ver'))

        payload = {
            'funcionalidade': 'core.logs_ver',
            'papel': 'SUPERVISOR',
            'concedido': False
        }
        response = self.client.post(
            reverse('accounts:matriz_toggle'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['sucesso'])

        # Checagem em tempo real
        self.assertFalse(tem_funcionalidade(self.user_supervisor, 'core.logs_ver'))

    def test_geracao_de_log_de_auditoria_ao_alterar_matriz(self):
        """Cada alternância na matriz deve gerar um registro correspondente em LogAuditoria."""
        self.client.force_login(self.user_admin)

        qtd_inicial = LogAuditoria.objects.count()

        payload = {
            'funcionalidade': 'financeiro.simulador_acessar',
            'papel': 'USUARIO',
            'concedido': True
        }
        self.client.post(
            reverse('accounts:matriz_toggle'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(LogAuditoria.objects.count(), qtd_inicial + 1)
        ultimo_log = LogAuditoria.objects.first()
        self.assertEqual(ultimo_log.autor, self.user_admin)
        self.assertIn("financeiro.simulador_acessar", ultimo_log.detalhes)
        self.assertIn("CONCEDIDA", ultimo_log.detalhes)

    def test_salvaguarda_nao_delega_matriz_e_perfis_a_operacionais(self):
        """Salvaguarda Doc ① §17.4: accounts.matriz e accounts.atribuir_perfis não podem ser concedidos a Grupos 0 e 1."""
        self.client.force_login(self.user_admin)

        # 1. Tentativa de conceder accounts.matriz ao USUARIO
        payload1 = {'funcionalidade': 'accounts.matriz', 'papel': 'USUARIO', 'concedido': True}
        resp1 = self.client.post(reverse('accounts:matriz_toggle'), data=json.dumps(payload1), content_type='application/json')
        self.assertEqual(resp1.status_code, 400)
        self.assertFalse(resp1.json()['sucesso'])
        self.assertIn("Salvaguarda de Segurança", resp1.json()['erro'])

        # 2. Tentativa de conceder accounts.atribuir_perfis ao SUPERVISOR
        payload2 = {'funcionalidade': 'accounts.atribuir_perfis', 'papel': 'SUPERVISOR', 'concedido': True}
        resp2 = self.client.post(reverse('accounts:matriz_toggle'), data=json.dumps(payload2), content_type='application/json')
        self.assertEqual(resp2.status_code, 400)
        self.assertFalse(resp2.json()['sucesso'])

    def test_salvaguarda_coluna_dev_bloqueada_contra_alteracao(self):
        """A coluna do Desenvolvedor (Grupo 4) é fixa e protegida contra revogação/bloqueio."""
        self.client.force_login(self.user_dev)

        payload = {'funcionalidade': 'site.tema_editar', 'papel': 'DEV', 'concedido': False}
        response = self.client.post(reverse('accounts:matriz_toggle'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['sucesso'])
        self.assertIn("protegidas contra bloqueio acidental", response.json()['erro'])

    def test_salvaguarda_admin_nao_altera_permissao_de_desenvolvedor(self):
        """Administrador (Grupo 3) não pode alterar permissões da coluna do Desenvolvedor (Grupo 4)."""
        self.client.force_login(self.user_admin)

        payload = {'funcionalidade': 'catalogo.produto_criar', 'papel': 'DEV', 'concedido': True}
        response = self.client.post(reverse('accounts:matriz_toggle'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['sucesso'])

    def test_perfil_operacional_bloqueado_no_endpoint_toggle(self):
        """Usuário comum (Grupo 0) ou Supervisor (Grupo 1) que tente fazer POST em /toggle recebe 403."""
        self.client.force_login(self.user_op)

        payload = {'funcionalidade': 'catalogo.produto_ver', 'papel': 'USUARIO', 'concedido': True}
        response = self.client.post(reverse('accounts:matriz_toggle'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['sucesso'])
