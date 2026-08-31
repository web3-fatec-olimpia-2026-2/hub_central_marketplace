import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import requests
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import (
    Loja, PerfilUsuario, LogAuditoria, Categoria, Produto, HistoricoPreco,
    LogSincronizacao, PedidoVenda, ItemPedidoVenda
)
from .enums import (
    PapelUsuarioEnum, EventoAuditoriaEnum, StatusProdutoEnum,
    StatusSincronizacaoEnum, TipoAjusteEstoqueEnum, MarketplaceEnum, StatusPedidoEnum
)
from .forms import (
    LojaForm, UsuarioCreateForm, UsuarioUpdateForm, UsuarioPasswordResetAdminForm,
    CategoriaForm, ProdutoForm, ProdutoBaixaAvariaForm, ProdutoAjusteEstoqueForm,
    LojaIntegracaoMeliForm, ProdutoSincronizacaoLoteForm, ProdutoBroadcastLoteForm
)
from .permissions import (
    pode_visualizar_usuarios, pode_gerenciar_usuarios, pode_criar_usuario,
    pode_editar_usuario, pode_alterar_papel, pode_alterar_preco,
    pode_ajustar_estoque_geral, pode_excluir_catalogo, pode_dar_baixa_avaria,
    pode_acessar_objeto_loja, pode_configurar_integracao, pode_disparar_sincronizacao
)
from .services import MercadoLivreService, BroadcastEstoqueService


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
        self.assertTrue(pode_criar_usuario(self.dev, PapelUsuarioEnum.DEV, None))
        self.assertTrue(pode_criar_usuario(self.dev, PapelUsuarioEnum.ADMIN, self.loja_a))
        self.assertTrue(pode_criar_usuario(self.dev, PapelUsuarioEnum.USUARIO, self.loja_b))

        self.assertTrue(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.SUPERVISOR, self.loja_a))
        self.assertTrue(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.USUARIO, self.loja_a))
        self.assertFalse(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.ADMIN, self.loja_a))
        self.assertFalse(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.DEV, None))
        self.assertFalse(pode_criar_usuario(self.admin_a, PapelUsuarioEnum.USUARIO, self.loja_b))

    def test_pode_editar_usuario_ownership_check(self):
        self.assertTrue(pode_editar_usuario(self.dev, self.admin_a))
        self.assertTrue(pode_editar_usuario(self.dev, self.usr_b))
        self.assertTrue(pode_editar_usuario(self.admin_a, self.sup_a))
        self.assertTrue(pode_editar_usuario(self.admin_a, self.usr_a))
        self.assertFalse(pode_editar_usuario(self.admin_a, self.usr_b))
        self.assertFalse(pode_editar_usuario(self.admin_a, self.dev))

    def test_pode_alterar_papel_regras(self):
        self.assertFalse(pode_alterar_papel(self.dev, self.dev, PapelUsuarioEnum.ADMIN))
        self.assertFalse(pode_alterar_papel(self.admin_a, self.admin_a, PapelUsuarioEnum.SUPERVISOR))
        self.assertTrue(pode_alterar_papel(self.admin_a, self.usr_a, PapelUsuarioEnum.SUPERVISOR))
        self.assertFalse(pode_alterar_papel(self.admin_a, self.usr_a, PapelUsuarioEnum.ADMIN))
        self.assertFalse(pode_alterar_papel(self.admin_a, self.usr_a, PapelUsuarioEnum.DEV))

    def test_catalogo_guards_regras_rn_09(self):
        # Alterar preço (DEV, ADMIN, SUPERVISOR = True; USUARIO = False)
        self.assertTrue(pode_alterar_preco(self.dev))
        self.assertTrue(pode_alterar_preco(self.admin_a))
        self.assertTrue(pode_alterar_preco(self.sup_a))
        self.assertFalse(pode_alterar_preco(self.usr_a))

        # Ajustar estoque geral
        self.assertTrue(pode_ajustar_estoque_geral(self.dev))
        self.assertTrue(pode_ajustar_estoque_geral(self.admin_a))
        self.assertTrue(pode_ajustar_estoque_geral(self.sup_a))
        self.assertFalse(pode_ajustar_estoque_geral(self.usr_a))

        # Excluir catálogo
        self.assertTrue(pode_excluir_catalogo(self.dev))
        self.assertTrue(pode_excluir_catalogo(self.admin_a))
        self.assertTrue(pode_excluir_catalogo(self.sup_a))
        self.assertFalse(pode_excluir_catalogo(self.usr_a))

        # Baixa de avaria (todos autenticados com loja = True)
        self.assertTrue(pode_dar_baixa_avaria(self.dev))
        self.assertTrue(pode_dar_baixa_avaria(self.admin_a))
        self.assertTrue(pode_dar_baixa_avaria(self.sup_a))
        self.assertTrue(pode_dar_baixa_avaria(self.usr_a))


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


class CatalogoModelTestCase(TestCase):
    """
    Testes de integridade dos modelos Categoria, Produto e HistoricoPreco (RN-01, RN-02, RN-06).
    """
    def setUp(self):
        self.loja_a = Loja.objects.create(nome='Loja Alfa', cnpj='11.222.333/0001-44')
        self.loja_b = Loja.objects.create(nome='Loja Beta', cnpj='22.333.444/0001-55')

        self.cat_a = Categoria.objects.create(loja=self.loja_a, nome='Eletrônicos')
        self.cat_b = Categoria.objects.create(loja=self.loja_b, nome='Eletrônicos')

        self.dev_user = User.objects.create_user(username='dev_catalog_test', password='password123')
        PerfilUsuario.objects.create(usuario=self.dev_user, papel=PapelUsuarioEnum.DEV)

    def test_rn_02_unicidade_sku_por_loja_permite_mesmo_sku_em_lojas_diferentes(self):
        prod_a = Produto.objects.create(
            loja=self.loja_a, categoria=self.cat_a, sku='FONE-BT-01',
            nome='Fone Bluetooth Alfa', preco=Decimal('99.90'), estoque=10
        )
        prod_b = Produto.objects.create(
            loja=self.loja_b, categoria=self.cat_b, sku='FONE-BT-01',
            nome='Fone Bluetooth Beta', preco=Decimal('120.00'), estoque=5
        )
        self.assertEqual(prod_a.sku, 'FONE-BT-01')
        self.assertEqual(prod_b.sku, 'FONE-BT-01')
        self.assertNotEqual(prod_a.loja, prod_b.loja)

    def test_rn_02_duplicidade_sku_mesma_loja_rejeitada(self):
        Produto.objects.create(
            loja=self.loja_a, categoria=self.cat_a, sku='MOUSE-01',
            nome='Mouse Alfa', preco=Decimal('49.90'), estoque=15
        )
        with self.assertRaises(IntegrityError):
            Produto.objects.create(
                loja=self.loja_a, categoria=self.cat_a, sku='MOUSE-01',
                nome='Mouse Alfa Duplicado', preco=Decimal('59.90'), estoque=5
            )

    def test_rn_06_preco_negativo_bloqueado(self):
        prod = Produto(
            loja=self.loja_a, categoria=self.cat_a, sku='TECL-01',
            nome='Teclado', preco=Decimal('-10.00'), estoque=5
        )
        with self.assertRaises(ValidationError):
            prod.clean()

    def test_rn_06_estoque_negativo_bloqueado_em_formulario_manual(self):
        # Formulário manual bloqueia estoque negativo
        form = ProdutoForm(
            data={
                'loja': self.loja_a.id,
                'categoria': self.cat_a.id,
                'sku': 'TECL-02',
                'nome': 'Teclado Mecânico',
                'preco': '199.90',
                'estoque': '-1',
                'status': 'ATIVO'
            },
            autor=self.dev_user
        )
        self.assertFalse(form.is_valid())
        self.assertIn('estoque', form.errors)

    def test_modelo_produto_admite_estoque_negativo_para_vendas_externas(self):
        # Modelo interno admite estoque negativo gerado por webhooks assíncronos
        prod = Produto(
            loja=self.loja_a, categoria=self.cat_a, sku='TECL-03',
            nome='Teclado Sem Fio', preco=Decimal('199.90'), estoque=-3
        )
        prod.clean()
        prod.save()
        self.assertEqual(prod.estoque, -3)

    def test_categoria_deve_pertencer_a_mesma_loja(self):
        prod_incompativel = Produto(
            loja=self.loja_a, categoria=self.cat_b, sku='CABO-01',
            nome='Cabo USB', preco=Decimal('19.90'), estoque=50
        )
        with self.assertRaises(ValidationError):
            prod_incompativel.clean()


class CatalogoViewsRBACMultiTenantTestCase(TestCase):
    """
    Testes de integração das Views de Categorias, Produtos, Baixa de Estoque e RBAC (RN-09).
    """
    def setUp(self):
        self.client = Client()
        self.loja_a = Loja.objects.create(nome='Loja A', cnpj='55.555.555/0001-55')
        self.loja_b = Loja.objects.create(nome='Loja B', cnpj='66.666.666/0001-66')

        # Usuários
        self.dev = User.objects.create_user(username='user_dev', password='password123')
        PerfilUsuario.objects.create(usuario=self.dev, papel=PapelUsuarioEnum.DEV, loja=None)

        self.admin_a = User.objects.create_user(username='admin_a', password='password123')
        PerfilUsuario.objects.create(usuario=self.admin_a, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_a)

        self.sup_a = User.objects.create_user(username='sup_a', password='password123')
        PerfilUsuario.objects.create(usuario=self.sup_a, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja_a)

        self.usr_a = User.objects.create_user(username='usr_a', password='password123')
        PerfilUsuario.objects.create(usuario=self.usr_a, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_a)

        # Categorias
        self.cat_a = Categoria.objects.create(loja=self.loja_a, nome='Móveis A')
        self.cat_b = Categoria.objects.create(loja=self.loja_b, nome='Móveis B')

        # Produtos
        self.prod_a = Produto.objects.create(
            loja=self.loja_a, categoria=self.cat_a, sku='CAD-001',
            nome='Cadeira de Escritório', preco=Decimal('350.00'), estoque=20
        )
        self.prod_b = Produto.objects.create(
            loja=self.loja_b, categoria=self.cat_b, sku='MES-001',
            nome='Mesa de Reunião', preco=Decimal('800.00'), estoque=5
        )

    # --------------------------------------------------------------------------
    # 1. CATEGORIAS (LISTA, CRIAÇÃO, EXCLUSÃO)
    # --------------------------------------------------------------------------
    def test_listagem_categorias_multi_tenant(self):
        self.client.login(username='admin_a', password='password123')
        response = self.client.get(reverse('categoria_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Móveis A')
        self.assertNotContains(response, 'Móveis B')

    def test_usuario_padrao_bloqueado_de_excluir_categoria(self):
        self.client.login(username='usr_a', password='password123')
        cat_sem_produtos = Categoria.objects.create(loja=self.loja_a, nome='Sem Produtos')
        response = self.client.post(reverse('categoria_delete', kwargs={'pk': cat_sem_produtos.pk}))
        self.assertEqual(response.status_code, 403)  # RN-09 bloqueia!

    def test_admin_exclui_categoria_sem_produtos_com_sucesso(self):
        self.client.login(username='admin_a', password='password123')
        cat_sem_produtos = Categoria.objects.create(loja=self.loja_a, nome='Categoria Vazia')
        response = self.client.post(reverse('categoria_delete', kwargs={'pk': cat_sem_produtos.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Categoria.objects.filter(pk=cat_sem_produtos.pk).exists())

    # --------------------------------------------------------------------------
    # 2. PRODUTOS (CRIAÇÃO, HISTÓRICO DE PREÇO, RESTRIÇÃO DE USUÁRIO)
    # --------------------------------------------------------------------------
    def test_admin_cria_produto_e_grava_historico_preco(self):
        self.client.login(username='admin_a', password='password123')
        post_data = {
            'categoria': self.cat_a.id,
            'sku': 'ARM-001',
            'nome': 'Armário Alto 2 Portas',
            'descricao': 'Armário em aço para escritório',
            'preco': '499.90',
            'estoque': '8',
            'status': StatusProdutoEnum.ATIVO,
        }
        response = self.client.post(reverse('produto_create'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        novo_prod = Produto.objects.get(sku='ARM-001', loja=self.loja_a)
        self.assertEqual(novo_prod.preco, Decimal('499.90'))

        # Valida primeiro registro em HistoricoPreco
        hist = HistoricoPreco.objects.filter(produto=novo_prod).first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.preco_novo, Decimal('499.90'))
        self.assertEqual(hist.usuario, self.admin_a)

    def test_admin_altera_preco_e_registra_historico_e_auditoria(self):
        self.client.login(username='admin_a', password='password123')
        post_data = {
            'categoria': self.cat_a.id,
            'sku': self.prod_a.sku,
            'nome': self.prod_a.nome,
            'descricao': 'Descrição atualizada',
            'preco': '399.90',  # Preço alterado de 350.00 para 399.90
            'estoque': self.prod_a.estoque,
            'status': StatusProdutoEnum.ATIVO,
        }
        response = self.client.post(
            reverse('produto_update', kwargs={'pk': self.prod_a.pk}),
            data=post_data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.prod_a.refresh_from_db()
        self.assertEqual(self.prod_a.preco, Decimal('399.90'))

        # Valida registro de mutação de preço
        hist = HistoricoPreco.objects.filter(
            produto=self.prod_a, preco_anterior=Decimal('350.00'), preco_novo=Decimal('399.90')
        ).first()
        self.assertIsNotNone(hist)

    def test_usuario_padrao_edita_descritivo_mas_preco_permanece_inalterado_rn_09(self):
        self.client.login(username='usr_a', password='password123')
        preco_original = self.prod_a.preco

        # USUARIO tenta enviar preço adulterado no POST
        post_data = {
            'categoria': self.cat_a.id,
            'sku': self.prod_a.sku,
            'nome': 'Cadeira de Escritório Ergonômica (Nome Atualizado)',
            'descricao': 'Nova descrição feita por usuário padrão',
            'preco': '1.99',  # Tentativa fraudulenta de alterar preço
            'estoque': '999', # Tentativa fraudulenta de alterar estoque
            'status': StatusProdutoEnum.ATIVO,
        }
        response = self.client.post(
            reverse('produto_update', kwargs={'pk': self.prod_a.pk}),
            data=post_data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.prod_a.refresh_from_db()
        self.assertEqual(self.prod_a.nome, 'Cadeira de Escritório Ergonômica (Nome Atualizado)')
        self.assertEqual(self.prod_a.preco, preco_original)  # Preço permaneceu 350.00 (RN-09)!
        self.assertEqual(self.prod_a.estoque, 20)           # Estoque permaneceu 20 (RN-09)!

    def test_usuario_padrao_bloqueado_de_excluir_produto(self):
        self.client.login(username='usr_a', password='password123')
        response = self.client.post(reverse('produto_delete', kwargs={'pk': self.prod_a.pk}))
        self.assertEqual(response.status_code, 403)  # RN-09 bloqueia!

    # --------------------------------------------------------------------------
    # 3. FLUXO DE BAIXA DE ESTOQUE POR AVARIA / PERDA (RN-09)
    # --------------------------------------------------------------------------
    def test_usuario_padrao_realiza_baixa_por_avaria_com_sucesso(self):
        self.client.login(username='usr_a', password='password123')
        saldo_inicial = self.prod_a.estoque  # 20

        post_data = {
            'quantidade': 3,
            'tipo_baixa': TipoAjusteEstoqueEnum.SAIDA_AVARIA,
            'justificativa': 'Braço da cadeira quebrado durante transporte no galpão',
        }
        response = self.client.post(
            reverse('produto_baixa_estoque', kwargs={'pk': self.prod_a.pk}),
            data=post_data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.prod_a.refresh_from_db()
        self.assertEqual(self.prod_a.estoque, saldo_inicial - 3)  # 17

        # Valida gravação compulsória em LogAuditoria
        log = LogAuditoria.objects.filter(
            evento=EventoAuditoriaEnum.BAIXA_AVARIA_ESTOQUE, loja=self.loja_a
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.autor, self.usr_a)
        self.assertIn('Baixa de 3 un.', log.detalhes)

    def test_baixa_por_avaria_com_quantidade_superior_ao_saldo_rejeitada(self):
        self.client.login(username='usr_a', password='password123')
        post_data = {
            'quantidade': 999,  # Saldo é apenas 20
            'tipo_baixa': TipoAjusteEstoqueEnum.SAIDA_PERDA,
            'justificativa': 'Tentativa de baixa excessiva',
        }
        response = self.client.post(
            reverse('produto_baixa_estoque', kwargs={'pk': self.prod_a.pk}),
            data=post_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'quantidade',
            f"A quantidade informada (999) é maior do que o saldo atual ({self.prod_a.estoque})."
        )

    # --------------------------------------------------------------------------
    # 4. AJUSTE GERAL DE ESTOQUE POR GESTORES
    # --------------------------------------------------------------------------
    def test_supervisor_ajusta_saldo_geral_de_estoque(self):
        self.client.login(username='sup_a', password='password123')
        post_data = {
            'novo_estoque': 50,
            'tipo_ajuste': TipoAjusteEstoqueEnum.ENTRADA,
            'justificativa': 'Entrada de lote novo do fornecedor',
        }
        response = self.client.post(
            reverse('produto_ajuste_estoque', kwargs={'pk': self.prod_a.pk}),
            data=post_data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.prod_a.refresh_from_db()
        self.assertEqual(self.prod_a.estoque, 50)

    def test_usuario_padrao_bloqueado_de_ajustar_estoque_geral(self):
        self.client.login(username='usr_a', password='password123')
        response = self.client.get(reverse('produto_ajuste_estoque', kwargs={'pk': self.prod_a.pk}))
        self.assertEqual(response.status_code, 403)  # RN-09 bloqueia!

    # --------------------------------------------------------------------------
    # 5. OWNERSHIP CHECKS CROSS-TENANT EM CATÁLOGO
    # --------------------------------------------------------------------------
    def test_admin_loja_a_bloqueado_ao_tentar_acessar_produto_loja_b(self):
        self.client.login(username='admin_a', password='password123')
        
        # Tentativa de GET em detalhe de produto de outra loja
        response_detail = self.client.get(reverse('produto_detail', kwargs={'pk': self.prod_b.pk}))
        self.assertEqual(response_detail.status_code, 403)

        # Tentativa de POST em baixa de estoque de outra loja
        response_baixa = self.client.post(
            reverse('produto_baixa_estoque', kwargs={'pk': self.prod_b.pk}),
            data={'quantidade': 1, 'tipo_baixa': TipoAjusteEstoqueEnum.SAIDA_AVARIA, 'justificativa': 'Ataque'}
        )
        self.assertEqual(response_baixa.status_code, 403)


# ==============================================================================
# TESTES DE SERVIÇOS DE INTEGRAÇÃO MERCADO LIVRE COM MOCKS (RF-05 / RN-01 / RN-04)
# ==============================================================================

class MercadoLivreServiceTestCase(TestCase):
    """
    Testes unitários e comportamentais de MercadoLivreService utilizando unittest.mock.
    Simula chamadas HTTP sem realizar conexões com a API externa real.
    """
    def setUp(self):
        self.loja = Loja.objects.create(
            nome='Loja Teste ML',
            cnpj='11.222.333/0001-44',
            inscricao_estadual='ISENTO',
            telefone='(11) 99999-1111',
            email='contato@lojameli.com',
            cep='01001-000',
            endereco='Praça da Sé',
            numero='10',
            bairro='Sé',
            cidade='São Paulo',
            estado='SP',
            pais='Brasil',
            ativo=True,
            meli_client_id='app-meli-12345',
            meli_client_secret='sec-meli-abcde',
            meli_access_token='APP_USR-test-token-active',
            meli_refresh_token='TG-test-refresh-token',
        )
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome='Informática',
            slug='informatica'
        )
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku='NOTE-DELL-G15',
            nome='Notebook Dell G15 16GB',
            preco=Decimal('5499.90'),
            estoque=10,
            meli_item_id='MLB9988776655',
            status=StatusProdutoEnum.ATIVO
        )
        self.user = User.objects.create_user(username='admin_meli', password='password123')
        self.perfil = PerfilUsuario.objects.create(
            usuario=self.user,
            papel=PapelUsuarioEnum.ADMIN,
            loja=self.loja
        )

    @patch('requests.put')
    def test_sincronizar_preco_produto_sucesso_200(self, mock_put):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'MLB9988776655',
            'price': 5499.90,
            'status': 'active'
        }
        mock_put.return_value = mock_response

        sucesso, msg, log = MercadoLivreService.sincronizar_preco_produto(self.produto, usuario=self.user)

        self.assertTrue(sucesso)
        self.assertIn('sincronizado com sucesso', msg)
        self.assertIsNotNone(log)
        self.assertTrue(log.sucesso)
        self.assertEqual(log.status_http, 200)
        self.assertEqual(log.payload_enviado, {'price': 5499.90})

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.status_sincronizacao, StatusSincronizacaoEnum.SINCRONIZADO)

        # Valida Log de Auditoria
        audit = LogAuditoria.objects.filter(evento=EventoAuditoriaEnum.SYNC_PRECO_MELI).first()
        self.assertIsNotNone(audit)
        self.assertIn('NOTE-DELL-G15', audit.detalhes)

    @patch('requests.put')
    @patch('requests.post')
    def test_sincronizar_preco_com_renovacao_automatica_de_token_401(self, mock_post, mock_put):
        # 1ª chamada PUT retorna 401 Unauthorized
        res_401 = MagicMock()
        res_401.status_code = 401
        res_401.json.return_value = {'message': 'expired token', 'error': 'unauthorized'}

        # 2ª chamada PUT após refresh retorna 200 OK
        res_200 = MagicMock()
        res_200.status_code = 200
        res_200.json.return_value = {'id': 'MLB9988776655', 'price': 5499.90}

        mock_put.side_effect = [res_401, res_200]

        # Resposta do endpoint /oauth/token
        mock_oauth_res = MagicMock()
        mock_oauth_res.status_code = 200
        mock_oauth_res.json.return_value = {
            'access_token': 'APP_USR-novo-token-renovado',
            'refresh_token': 'TG-novo-refresh-token',
            'expires_in': 21600
        }
        mock_post.return_value = mock_oauth_res

        sucesso, msg, log = MercadoLivreService.sincronizar_preco_produto(self.produto, usuario=self.user)

        self.assertTrue(sucesso)
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.meli_access_token, 'APP_USR-novo-token-renovado')
        self.assertEqual(self.loja.meli_refresh_token, 'TG-novo-refresh-token')

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.status_sincronizacao, StatusSincronizacaoEnum.SINCRONIZADO)

    def test_sincronizar_preco_sem_item_id_externo(self):
        self.produto.meli_item_id = ''
        self.produto.save()

        sucesso, msg, log = MercadoLivreService.sincronizar_preco_produto(self.produto)
        self.assertFalse(sucesso)
        self.assertIn('não possui identificador de anúncio', msg)
        self.assertIsNone(log)

    def test_sincronizar_preco_sem_token_na_loja(self):
        self.loja.meli_access_token = ''
        self.loja.save()

        sucesso, msg, log = MercadoLivreService.sincronizar_preco_produto(self.produto)
        self.assertFalse(sucesso)
        self.assertIn('não possui Access Token', msg)
        self.assertIsNotNone(log)
        self.assertFalse(log.sucesso)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.status_sincronizacao, StatusSincronizacaoEnum.ERRO)

    @patch('requests.put')
    def test_sincronizar_preco_falha_400_bad_request(self, mock_put):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'message': 'Price cannot be lower than 10.0',
            'error': 'bad_request',
            'cause': [{'message': 'min_price_violation'}]
        }
        mock_put.return_value = mock_response

        sucesso, msg, log = MercadoLivreService.sincronizar_preco_produto(self.produto, usuario=self.user)

        self.assertFalse(sucesso)
        self.assertIn('Mercado Livre rejeitou a sincronização', msg)
        self.assertIsNotNone(log)
        self.assertFalse(log.sucesso)
        self.assertEqual(log.status_http, 400)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.status_sincronizacao, StatusSincronizacaoEnum.ERRO)

    @patch('requests.put')
    def test_sincronizar_preco_timeout(self, mock_put):
        mock_put.side_effect = requests.exceptions.Timeout("Connection timed out")

        sucesso, msg, log = MercadoLivreService.sincronizar_preco_produto(self.produto)

        self.assertFalse(sucesso)
        self.assertIn('Tempo limite', msg)
        self.assertIsNotNone(log)
        self.assertEqual(log.status_http, 408)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.status_sincronizacao, StatusSincronizacaoEnum.ERRO)

    @patch('requests.put')
    def test_sincronizar_precos_lote(self, mock_put):
        prod2 = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku='MOUSE-LOGI-G502',
            nome='Mouse Gamer Logitech G502',
            preco=Decimal('299.90'),
            estoque=15,
            meli_item_id='MLB1122334455',
            status=StatusProdutoEnum.ATIVO
        )

        res_ok = MagicMock()
        res_ok.status_code = 200
        res_ok.json.return_value = {'status': 'active'}
        mock_put.return_value = res_ok

        produtos = Produto.objects.filter(loja=self.loja)
        res = MercadoLivreService.sincronizar_precos_lote(produtos, usuario=self.user)

        self.assertEqual(res['total'], 2)
        self.assertEqual(res['sucessos'], 2)
        self.assertEqual(res['erros'], 0)

        logs_count = LogSincronizacao.objects.filter(loja=self.loja, sucesso=True).count()
        self.assertEqual(logs_count, 2)


# ==============================================================================
# TESTES DE VIEWS, ROTAS E RBAC PARA INTEGRAÇÃO MERCADO LIVRE (RF-05)
# ==============================================================================

class MercadoLivreViewsAndRBACTestCase(TestCase):
    """
    Testes de integração das Views, RBAC e Multi-Tenancy para o módulo de integração Mercado Livre.
    """
    def setUp(self):
        self.client = Client()

        # Loja A
        self.loja_a = Loja.objects.create(
            nome='Loja Alfa', cnpj='11.111.111/0001-11', inscricao_estadual='ISENTO',
            telefone='(11) 1111-1111', email='alfa@loja.com', cep='01001-000', endereco='Rua A',
            numero='1', bairro='Centro', cidade='SP', estado='SP', pais='Brasil', ativo=True,
            meli_client_id='app-alfa', meli_client_secret='sec-alfa',
            meli_access_token='tok-alfa', meli_refresh_token='ref-alfa'
        )
        self.cat_a = Categoria.objects.create(loja=self.loja_a, nome='Cat A', slug='cat-a')
        self.prod_a = Produto.objects.create(
            loja=self.loja_a, categoria=self.cat_a, sku='SKU-ALFA-01', nome='Produto Alfa',
            preco=Decimal('150.00'), estoque=10, meli_item_id='MLB-ALFA-01', status=StatusProdutoEnum.ATIVO
        )

        # Loja B
        self.loja_b = Loja.objects.create(
            nome='Loja Beta', cnpj='22.222.222/0001-22', inscricao_estadual='ISENTO',
            telefone='(11) 2222-2222', email='beta@loja.com', cep='01002-000', endereco='Rua B',
            numero='2', bairro='Centro', cidade='SP', estado='SP', pais='Brasil', ativo=True,
            meli_client_id='app-beta', meli_client_secret='sec-beta',
            meli_access_token='tok-beta', meli_refresh_token='ref-beta'
        )
        self.cat_b = Categoria.objects.create(loja=self.loja_b, nome='Cat B', slug='cat-b')
        self.prod_b = Produto.objects.create(
            loja=self.loja_b, categoria=self.cat_b, sku='SKU-BETA-01', nome='Produto Beta',
            preco=Decimal('250.00'), estoque=5, meli_item_id='MLB-BETA-01', status=StatusProdutoEnum.ATIVO
        )

        # Usuários
        self.dev = User.objects.create_user(username='dev_user', password='password123')
        PerfilUsuario.objects.create(usuario=self.dev, papel=PapelUsuarioEnum.DEV, loja=None)

        self.admin_a = User.objects.create_user(username='admin_alfa', password='password123')
        PerfilUsuario.objects.create(usuario=self.admin_a, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_a)

        self.sup_a = User.objects.create_user(username='sup_alfa', password='password123')
        PerfilUsuario.objects.create(usuario=self.sup_a, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja_a)

        self.usr_a = User.objects.create_user(username='usr_alfa', password='password123')
        PerfilUsuario.objects.create(usuario=self.usr_a, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_a)

    # 1. CONFIGURAÇÃO DE CREDENCIAIS
    def test_admin_configura_credenciais_sua_loja(self):
        self.client.login(username='admin_alfa', password='password123')
        response = self.client.get(reverse('loja_integracao_meli'))
        self.assertEqual(response.status_code, 200)

        post_data = {
            'meli_client_id': 'app-alfa-novo',
            'meli_client_secret': 'sec-alfa-novo',
            'meli_access_token': 'tok-alfa-novo',
            'meli_refresh_token': 'ref-alfa-novo',
        }
        res_post = self.client.post(reverse('loja_integracao_meli'), data=post_data, follow=True)
        self.assertEqual(res_post.status_code, 200)

        self.loja_a.refresh_from_db()
        self.assertEqual(self.loja_a.meli_client_id, 'app-alfa-novo')

    def test_supervisor_e_usuario_bloqueados_de_configurar_credenciais(self):
        # Supervisor
        self.client.login(username='sup_alfa', password='password123')
        res_sup = self.client.get(reverse('loja_integracao_meli'))
        self.assertEqual(res_sup.status_code, 403)

        # Usuário
        self.client.login(username='usr_alfa', password='password123')
        res_usr = self.client.get(reverse('loja_integracao_meli'))
        self.assertEqual(res_usr.status_code, 403)

    def test_dev_configura_credenciais_de_qualquer_loja(self):
        self.client.login(username='dev_user', password='password123')
        res = self.client.get(reverse('loja_integracao_meli_slug', kwargs={'slug': self.loja_b.slug}))
        self.assertEqual(res.status_code, 200)

    # 2. SINCRONIZAÇÃO UNITÁRIA DE PREÇOS
    @patch('core.services.MercadoLivreService.sincronizar_preco_produto')
    def test_admin_e_supervisor_disparam_sincronizacao_unitaria(self, mock_sync):
        mock_sync.return_value = (True, "Preço sincronizado!", None)

        # ADMIN
        self.client.login(username='admin_alfa', password='password123')
        res_adm = self.client.post(
            reverse('produto_sincronizar_preco_meli', kwargs={'pk': self.prod_a.pk}),
            follow=True
        )
        self.assertEqual(res_adm.status_code, 200)
        self.assertTrue(mock_sync.called)

        # SUPERVISOR
        mock_sync.reset_mock()
        self.client.login(username='sup_alfa', password='password123')
        res_sup = self.client.post(
            reverse('produto_sincronizar_preco_meli', kwargs={'pk': self.prod_a.pk}),
            follow=True
        )
        self.assertEqual(res_sup.status_code, 200)
        self.assertTrue(mock_sync.called)

    def test_usuario_padrao_bloqueado_de_disparar_sincronizacao_unitaria(self):
        self.client.login(username='usr_alfa', password='password123')
        res = self.client.post(
            reverse('produto_sincronizar_preco_meli', kwargs={'pk': self.prod_a.pk})
        )
        self.assertEqual(res.status_code, 403)  # Bloqueado com 403!

    def test_admin_loja_a_bloqueado_ao_tentar_sincronizar_produto_loja_b(self):
        self.client.login(username='admin_alfa', password='password123')
        res = self.client.post(
            reverse('produto_sincronizar_preco_meli', kwargs={'pk': self.prod_b.pk})
        )
        self.assertEqual(res.status_code, 403)  # Cross-tenant ownership check!

    # 3. SINCRONIZAÇÃO EM LOTE
    @patch('core.services.MercadoLivreService.sincronizar_precos_lote')
    def test_admin_dispara_sincronizacao_em_lote(self, mock_lote):
        mock_lote.return_value = {
            'total': 1, 'sucessos': 1, 'erros': 0, 'detalhes': []
        }
        self.client.login(username='admin_alfa', password='password123')
        res = self.client.post(
            reverse('produto_sincronizar_lote_meli'),
            data={'produtos_ids': f"{self.prod_a.id}"},
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(mock_lote.called)

    def test_usuario_padrao_bloqueado_de_disparar_sincronizacao_em_lote(self):
        self.client.login(username='usr_alfa', password='password123')
        res = self.client.post(
            reverse('produto_sincronizar_lote_meli'),
            data={'produtos_ids': f"{self.prod_a.id}"}
        )
        self.assertEqual(res.status_code, 403)

    # 4. LISTAGEM E MULTI-TENANT DE LOGS
    def test_listagem_logs_multi_tenant(self):
        # Log da Loja A
        LogSincronizacao.objects.create(
            loja=self.loja_a, produto=self.prod_a, marketplace=MarketplaceEnum.MERCADO_LIVRE,
            evento=EventoAuditoriaEnum.SYNC_PRECO_MELI, sucesso=True, status_http=200
        )
        # Log da Loja B
        LogSincronizacao.objects.create(
            loja=self.loja_b, produto=self.prod_b, marketplace=MarketplaceEnum.MERCADO_LIVRE,
            evento=EventoAuditoriaEnum.SYNC_PRECO_MELI, sucesso=True, status_http=200
        )

        # ADMIN Loja A deve ver apenas 1 log (da loja A)
        self.client.login(username='admin_alfa', password='password123')
        res_adm = self.client.get(reverse('log_sincronizacao_list'))
        self.assertEqual(res_adm.status_code, 200)
        self.assertEqual(len(res_adm.context['logs']), 1)

        # DEV deve ver os 2 logs
        self.client.login(username='dev_user', password='password123')
        res_dev = self.client.get(reverse('log_sincronizacao_list'))
        self.assertEqual(res_dev.status_code, 200)
        self.assertEqual(len(res_dev.context['logs']), 2)


class MercadoLivreWebhookServiceTestCase(TestCase):
    """
    Testes unitários e de integração para o serviço de Webhook e Baixa de Estoque (RF-06 / RF-07).
    """
    def setUp(self):
        self.loja = Loja.objects.create(
            nome='Loja Webhook Test',
            cnpj='11.222.333/0001-44',
            meli_client_id='123456789',
            meli_client_secret='secret123',
            meli_access_token='APP_USR-test-token',
            meli_refresh_token='TG-refresh-token',
            ativo=True
        )
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome='Gamer',
            slug='gamer'
        )
        self.produto_1 = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome='Teclado Mecânico RGB',
            sku='TEC-MEC-RGB',
            preco=Decimal('250.00'),
            estoque=10,
            meli_item_id='MLB1000000001',
            status_sincronizacao=StatusSincronizacaoEnum.SINCRONIZADO
        )
        self.produto_2 = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome='Mouse Óptico Pro',
            sku='MOU-OPT-PRO',
            preco=Decimal('120.00'),
            estoque=2,
            meli_item_id='MLB1000000002',
            status_sincronizacao=StatusSincronizacaoEnum.SINCRONIZADO
        )

    @patch('core.services.MercadoLivreService.consultar_pedido')
    def test_baixa_estoque_venda_normal(self, mock_consultar):
        mock_consultar.return_value = (True, {
            'id': 200000111,
            'status': 'paid',
            'buyer': {'nickname': 'COMPRADOR_TESTE', 'billing_info': {'doc_number': '12345678900'}},
            'total_amount': 500.00,
            'shipping_cost': 0.00,
            'date_created': '2026-08-31T00:00:00.000-04:00',
            'order_items': [
                {
                    'item': {'id': 'MLB1000000001', 'seller_sku': 'TEC-MEC-RGB', 'title': 'Teclado Mecânico RGB'},
                    'quantity': 2,
                    'unit_price': 250.00
                }
            ]
        }, "")

        payload = {
            'resource': '/orders/200000111',
            'topic': 'orders_v2',
            'application_id': '123456789'
        }

        sucesso, msg, pedido = MercadoLivreService.processar_webhook_venda(payload)
        self.assertTrue(sucesso)
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.pedido_id_externo, '200000111')
        self.assertFalse(pedido.teve_ruptura_estoque)
        self.assertTrue(pedido.processado_com_sucesso)

        # Verifica estoque baixado de 10 para 8
        self.produto_1.refresh_from_db()
        self.assertEqual(self.produto_1.estoque, 8)

        # Verifica ItemPedidoVenda
        item = pedido.itens.first()
        self.assertEqual(item.quantidade, 2)
        self.assertEqual(item.estoque_anterior, 10)
        self.assertEqual(item.estoque_posterior, 8)
        self.assertFalse(item.ruptura_estoque)

    @patch('core.services.MercadoLivreService.consultar_pedido')
    def test_baixa_estoque_venda_com_ruptura_estoque_negativo(self, mock_consultar):
        # Produto 2 tem estoque = 2, venda solicita 5 unidades -> saldo deve ficar -3
        mock_consultar.return_value = (True, {
            'id': 200000222,
            'status': 'paid',
            'buyer': {'nickname': 'COMPRADOR_RUPTURA'},
            'total_amount': 600.00,
            'order_items': [
                {
                    'item': {'id': 'MLB1000000002', 'seller_sku': 'MOU-OPT-PRO', 'title': 'Mouse Óptico Pro'},
                    'quantity': 5,
                    'unit_price': 120.00
                }
            ]
        }, "")

        payload = {
            'resource': '/orders/200000222',
            'topic': 'orders_v2',
            'application_id': '123456789'
        }

        sucesso, msg, pedido = MercadoLivreService.processar_webhook_venda(payload)
        self.assertTrue(sucesso)
        self.assertTrue(pedido.teve_ruptura_estoque)

        # Saldo físico fiel: 2 - 5 = -3
        self.produto_2.refresh_from_db()
        self.assertEqual(self.produto_2.estoque, -3)

        item = pedido.itens.first()
        self.assertEqual(item.estoque_anterior, 2)
        self.assertEqual(item.estoque_posterior, -3)
        self.assertTrue(item.ruptura_estoque)

        # Auditoria de alerta de ruptura gerada
        alerta = LogAuditoria.objects.filter(
            loja=self.loja, evento=EventoAuditoriaEnum.ALERTA_ESTOQUE_NEGATIVO_VENDA
        ).first()
        self.assertIsNotNone(alerta)
        self.assertIn('ALERTA DE RUPTURA', alerta.detalhes)
        self.assertIn('-3 un', alerta.detalhes)

    @patch('requests.put')
    def test_sincronizacao_estoque_com_clamping_max_0_ao_marketplace(self, mock_put):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {'id': 'MLB1000000002', 'available_quantity': 0}
        mock_put.return_value = mock_res

        # Produto com saldo negativo (-3)
        self.produto_2.estoque = -3
        self.produto_2.save(update_fields=['estoque'])

        sucesso, msg, log = MercadoLivreService.sincronizar_estoque_produto(self.produto_2)
        self.assertTrue(sucesso)

        # O payload enviado ao Mercado Livre DEVE SER clampado em 0 e nunca menor que 0!
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        payload_enviado = kwargs.get('json', {})
        self.assertEqual(payload_enviado.get('available_quantity'), 0)

    @patch('core.services.MercadoLivreService.consultar_pedido')
    def test_idempotencia_webhook_venda_duplicada(self, mock_consultar):
        mock_consultar.return_value = (True, {
            'id': 200000333,
            'status': 'paid',
            'buyer': {'nickname': 'COMPRADOR_IDEMPOTENTE'},
            'total_amount': 250.00,
            'order_items': [
                {
                    'item': {'id': 'MLB1000000001', 'seller_sku': 'TEC-MEC-RGB', 'title': 'Teclado Mecânico RGB'},
                    'quantity': 2,
                    'unit_price': 250.00
                }
            ]
        }, "")

        payload = {'resource': '/orders/200000333', 'topic': 'orders_v2', 'application_id': '123456789'}

        # 1º processamento
        sucesso_1, _, _ = MercadoLivreService.processar_webhook_venda(payload)
        self.assertTrue(sucesso_1)
        self.produto_1.refresh_from_db()
        self.assertEqual(self.produto_1.estoque, 8)  # 10 - 2 = 8

        # 2º processamento do mesmo webhook / order_id
        sucesso_2, msg_2, _ = MercadoLivreService.processar_webhook_venda(payload)
        self.assertTrue(sucesso_2)
        self.assertIn('Idempotência garantida', msg_2)

        # O estoque NÃO pode ser decrementado novamente (deve permanecer 8)
        self.produto_1.refresh_from_db()
        self.assertEqual(self.produto_1.estoque, 8)
        self.assertEqual(PedidoVenda.objects.filter(pedido_id_externo='200000333').count(), 1)


class MercadoLivreWebhookViewTestCase(TestCase):
    """
    Testes de integração HTTP do endpoint público /webhook/mercadolivre/.
    """
    def setUp(self):
        self.client = Client()
        self.loja = Loja.objects.create(
            nome='Loja Webhook HTTP',
            cnpj='55.666.777/0001-88',
            slug='loja-webhook-http',
            meli_client_id='987654321',
            meli_access_token='APP_USR-token-http',
            ativo=True
        )

    def test_webhook_endpoint_get_healthcheck(self):
        res = self.client.get(reverse('webhook_mercadolivre'))
        self.assertEqual(res.status_code, 200)
        dados = res.json()
        self.assertEqual(dados.get('status'), 'active')

    @patch('core.services.MercadoLivreService.processar_webhook_venda')
    def test_webhook_endpoint_post_sucesso(self, mock_processar):
        mock_pedido = MagicMock()
        mock_pedido.pedido_id_externo = '200000555'
        mock_pedido.teve_ruptura_estoque = False
        mock_processar.return_value = (True, "Pedido processado com sucesso!", mock_pedido)

        payload = {'resource': '/orders/200000555', 'topic': 'orders_v2', 'application_id': '987654321'}
        res = self.client.post(
            reverse('webhook_mercadolivre'),
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        dados = res.json()
        self.assertEqual(dados.get('status'), 'success')
        self.assertEqual(dados.get('pedido_id'), '200000555')


class PedidoVendaViewsTestCase(TestCase):
    """
    Testes de RBAC e isolamento multi-tenant para as views de Pedido de Venda.
    """
    def setUp(self):
        self.client = Client()
        self.loja_a = Loja.objects.create(nome='Loja Alfa Pedidos', cnpj='11.111.111/0001-11', slug='loja-alfa')
        self.loja_b = Loja.objects.create(nome='Loja Beta Pedidos', cnpj='22.222.222/0001-22', slug='loja-beta')

        # Usuários
        self.dev_user = User.objects.create_user(username='dev_orders', password='password123')
        PerfilUsuario.objects.create(usuario=self.dev_user, papel=PapelUsuarioEnum.DEV, loja=self.loja_a)

        self.admin_a = User.objects.create_user(username='admin_a_orders', password='password123')
        PerfilUsuario.objects.create(usuario=self.admin_a, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_a)

        # Pedidos
        self.ped_a = PedidoVenda.objects.create(
            loja=self.loja_a, marketplace=MarketplaceEnum.MERCADO_LIVRE, pedido_id_externo='1001',
            valor_total=Decimal('100.00'), processado_com_sucesso=True
        )
        self.ped_b = PedidoVenda.objects.create(
            loja=self.loja_b, marketplace=MarketplaceEnum.MERCADO_LIVRE, pedido_id_externo='2002',
            valor_total=Decimal('200.00'), processado_com_sucesso=True
        )

    def test_admin_visualiza_apenas_pedidos_da_propria_loja(self):
        self.client.login(username='admin_a_orders', password='password123')
        res = self.client.get(reverse('pedido_list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['pedidos']), 1)
        self.assertEqual(res.context['pedidos'][0].pedido_id_externo, '1001')

    def test_dev_visualiza_pedidos_de_todas_as_lojas(self):
        self.client.login(username='dev_orders', password='password123')
        res = self.client.get(reverse('pedido_list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['pedidos']), 2)

    def test_cross_tenant_bloqueado_detalhes_pedido(self):
        self.client.login(username='admin_a_orders', password='password123')
        # Admin A tentando ver pedido da Loja B
        res = self.client.get(reverse('pedido_detail', kwargs={'pk': self.ped_b.pk}))
        self.assertEqual(res.status_code, 403)


class BroadcastEstoqueServiceTestCase(TestCase):
    """
    Testes unitários para o BroadcastEstoqueService e adaptadores multi-canal (RF-08).
    """
    def setUp(self):
        self.loja = Loja.objects.create(
            nome='Loja MultiCanal Test',
            cnpj='33.444.555/0001-66',
            meli_client_id='12345',
            meli_access_token='APP_USR-token-meli',
            shopee_ativo=True,
            magalu_ativo=True,
            sincronizar_canal_origem_venda=False,
            ativo=True
        )
        self.categoria = Categoria.objects.create(loja=self.loja, nome='Informática', slug='info')
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome='Monitor Gamer 144Hz',
            sku='MON-144-GAMER',
            preco=Decimal('1200.00'),
            estoque=15,
            meli_item_id='MLB999888777',
            status_sincronizacao=StatusSincronizacaoEnum.SINCRONIZADO
        )
        self.user = User.objects.create_user(username='admin_multicanal', password='password123')
        PerfilUsuario.objects.create(usuario=self.user, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

    @patch('core.services.MercadoLivreService.sincronizar_estoque_produto')
    def test_broadcast_multi_canal_com_saldo_positivo(self, mock_meli_stock):
        mock_meli_stock.return_value = (True, "Estoque sincronizado no ML: 15 un.", None)

        resultado = BroadcastEstoqueService.disparar_broadcast_produto(self.produto, usuario=self.user)

        self.assertEqual(resultado['estoque_hub'], 15)
        self.assertEqual(resultado['estoque_transmitido'], 15)
        self.assertEqual(resultado['canais_tentados'], 3)
        self.assertEqual(resultado['sucessos'], 3)
        self.assertEqual(resultado['falhas'], 0)

        # Verifica criação do LogAuditoria consolidado
        log_auditoria = LogAuditoria.objects.filter(
            loja=self.loja, evento=EventoAuditoriaEnum.BROADCAST_ESTOQUE
        ).first()
        self.assertIsNotNone(log_auditoria)
        self.assertIn('Broadcast de estoque disparado', log_auditoria.detalhes)
        self.assertIn('15 un', log_auditoria.detalhes)

    @patch('core.services.MercadoLivreService.sincronizar_estoque_produto')
    def test_broadcast_multi_canal_com_saldo_negativo_clamping_zero(self, mock_meli_stock):
        mock_meli_stock.return_value = (True, "Estoque sincronizado no ML: 0 un.", None)

        # Produto em ruptura (estoque = -5)
        self.produto.estoque = -5
        self.produto.save(update_fields=['estoque'])

        resultado = BroadcastEstoqueService.disparar_broadcast_produto(self.produto, usuario=self.user)

        # Clamping mandatório: transmitido DEVE ser 0
        self.assertEqual(resultado['estoque_hub'], -5)
        self.assertEqual(resultado['estoque_transmitido'], 0)
        self.assertEqual(resultado['sucessos'], 3)

        # Telemetria dos canais Shopee e Magalu deve ter registrado estoque 0
        log_shopee = LogSincronizacao.objects.filter(
            loja=self.loja, marketplace=MarketplaceEnum.SHOPEE, produto=self.produto
        ).first()
        self.assertIsNotNone(log_shopee)
        self.assertEqual(log_shopee.payload_enviado.get('stock'), 0)

        log_magalu = LogSincronizacao.objects.filter(
            loja=self.loja, marketplace=MarketplaceEnum.MAGALU, produto=self.produto
        ).first()
        self.assertIsNotNone(log_magalu)
        self.assertEqual(log_magalu.payload_enviado.get('quantity'), 0)

    @patch('core.services.MercadoLivreService.sincronizar_estoque_produto')
    def test_venda_webhook_pula_canal_origem_quando_sincronizar_canal_origem_false(self, mock_meli_stock):
        self.loja.sincronizar_canal_origem_venda = False
        self.loja.save()

        # Venda veio do Mercado Livre (canal_origem = MERCADO_LIVRE)
        resultado = BroadcastEstoqueService.disparar_broadcast_produto(
            self.produto, canal_origem=MarketplaceEnum.MERCADO_LIVRE, usuario=self.user
        )

        # Deve disparar apenas para Shopee e Magalu (2 canais), pulando Mercado Livre
        self.assertEqual(resultado['canais_tentados'], 2)
        mock_meli_stock.assert_not_called()

        canais_notificados = [d['marketplace'] for d in resultado['detalhes']]
        self.assertIn('Shopee', str(canais_notificados))
        self.assertIn('Magazine Luiza', str(canais_notificados))
        self.assertNotIn('Mercado Livre', str(canais_notificados))

    @patch('core.services.MercadoLivreService.sincronizar_estoque_produto')
    def test_venda_webhook_forca_canal_origem_quando_sincronizar_canal_origem_true(self, mock_meli_stock):
        mock_meli_stock.return_value = (True, "Estoque sincronizado no ML: 15 un.", None)
        self.loja.sincronizar_canal_origem_venda = True
        self.loja.save()

        # Venda veio do Mercado Livre, mas a loja configurou para enviar ao canal de origem também
        resultado = BroadcastEstoqueService.disparar_broadcast_produto(
            self.produto, canal_origem=MarketplaceEnum.MERCADO_LIVRE, usuario=self.user
        )

        # Deve disparar para TODOS os 3 canais, incluindo Mercado Livre
        self.assertEqual(resultado['canais_tentados'], 3)
        mock_meli_stock.assert_called_once()


class BroadcastEstoqueViewsTestCase(TestCase):
    """
    Testes de integração das Views de disparo manual e em lote de Broadcast (RF-08).
    """
    def setUp(self):
        self.client = Client()
        self.loja_a = Loja.objects.create(
            nome='Loja Alfa Broadcast', cnpj='11.111.111/0001-11',
            meli_access_token='APP_USR-token-a', shopee_ativo=True, ativo=True
        )
        self.loja_b = Loja.objects.create(
            nome='Loja Beta Broadcast', cnpj='22.222.222/0001-22',
            meli_access_token='APP_USR-token-b', ativo=True
        )
        self.cat_a = Categoria.objects.create(loja=self.loja_a, nome='Hardware')
        self.cat_b = Categoria.objects.create(loja=self.loja_b, nome='Hardware')

        self.prod_a = Produto.objects.create(
            loja=self.loja_a, categoria=self.cat_a, sku='SSD-500GB',
            nome='SSD 500GB NVMe', preco=Decimal('300.00'), estoque=20, meli_item_id='MLB111'
        )
        self.prod_b = Produto.objects.create(
            loja=self.loja_b, categoria=self.cat_b, sku='SSD-1TB',
            nome='SSD 1TB NVMe', preco=Decimal('550.00'), estoque=10, meli_item_id='MLB222'
        )

        # Usuários
        self.admin_a = User.objects.create_user(username='admin_a_broad', password='password123')
        PerfilUsuario.objects.create(usuario=self.admin_a, papel=PapelUsuarioEnum.ADMIN, loja=self.loja_a)

        self.supervisor_a = User.objects.create_user(username='sup_a_broad', password='password123')
        PerfilUsuario.objects.create(usuario=self.supervisor_a, papel=PapelUsuarioEnum.SUPERVISOR, loja=self.loja_a)

        self.usuario_a = User.objects.create_user(username='usr_a_broad', password='password123')
        PerfilUsuario.objects.create(usuario=self.usuario_a, papel=PapelUsuarioEnum.USUARIO, loja=self.loja_a)

    @patch('core.services.MercadoLivreService.sincronizar_estoque_produto')
    def test_admin_dispara_broadcast_unitario(self, mock_meli):
        mock_meli.return_value = (True, "OK", None)
        self.client.login(username='admin_a_broad', password='password123')
        res = self.client.post(
            reverse('produto_broadcast_estoque', kwargs={'pk': self.prod_a.pk}),
            follow=True
        )
        self.assertEqual(res.status_code, 200)

    @patch('core.services.MercadoLivreService.sincronizar_estoque_produto')
    def test_supervisor_dispara_broadcast_unitario(self, mock_meli):
        mock_meli.return_value = (True, "OK", None)
        self.client.login(username='sup_a_broad', password='password123')
        res = self.client.post(
            reverse('produto_broadcast_estoque', kwargs={'pk': self.prod_a.pk}),
            follow=True
        )
        self.assertEqual(res.status_code, 200)

    def test_usuario_padrao_bloqueado_de_disparar_broadcast(self):
        self.client.login(username='usr_a_broad', password='password123')
        res = self.client.post(
            reverse('produto_broadcast_estoque', kwargs={'pk': self.prod_a.pk})
        )
        self.assertEqual(res.status_code, 403)

    def test_cross_tenant_broadcast_bloqueado(self):
        self.client.login(username='admin_a_broad', password='password123')
        # Admin A tenta disparar broadcast no produto da Loja B
        res = self.client.post(
            reverse('produto_broadcast_estoque', kwargs={'pk': self.prod_b.pk})
        )
        self.assertEqual(res.status_code, 403)

    @patch('core.services.MercadoLivreService.sincronizar_estoque_produto')
    def test_broadcast_em_lote(self, mock_meli):
        mock_meli.return_value = (True, "OK", None)
        self.client.login(username='admin_a_broad', password='password123')
        res = self.client.post(
            reverse('produto_broadcast_estoque_lote'),
            data={'produtos_ids': f"{self.prod_a.id}"},
            follow=True
        )
        self.assertEqual(res.status_code, 200)


class ErrorPagesTestCase(TestCase):
    """
    Testes de renderização de páginas customizadas de erro (404.html).
    """
    @override_settings(DEBUG=False)
    def test_custom_404_template_renders(self):
        response = self.client.get('/endereco-inexistente-404-rota-teste/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Página não encontrada', status_code=404)
        self.assertContains(response, '404', status_code=404)
        self.assertContains(response, 'Voltar ao Início', status_code=404)







