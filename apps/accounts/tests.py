# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Testes de integridade de autenticação, ordem do formulário de login e RBAC reservado (Doc ① §16.2, §17.4 e §17.5).
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from apps.accounts.rbac import (
    tem_funcionalidade, get_grupo_usuario,
    FUNC_ACCOUNTS_MATRIZ, FUNC_ACCOUNTS_ATRIBUIR_PERFIS,
    FUNC_SITE_TEMA_EDITAR, FUNC_SITE_VISIBILIDADE_PUBLICA
)
from apps.tenancy.models import Loja, PerfilUsuario, PapelUsuarioEnum


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

        # Verifica sequência estrita: username -> password -> submit -> esqueci minha senha
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
