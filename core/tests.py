from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import Loja, PerfilUsuario, LogAuditoria, Categoria, Produto, HistoricoPreco
from .enums import (
    PapelUsuarioEnum, EventoAuditoriaEnum, StatusProdutoEnum,
    StatusSincronizacaoEnum, TipoAjusteEstoqueEnum
)
from .forms import (
    LojaForm, UsuarioCreateForm, UsuarioUpdateForm, UsuarioPasswordResetAdminForm,
    CategoriaForm, ProdutoForm, ProdutoBaixaAvariaForm, ProdutoAjusteEstoqueForm
)
from .permissions import (
    pode_visualizar_usuarios, pode_gerenciar_usuarios, pode_criar_usuario,
    pode_editar_usuario, pode_alterar_papel, pode_alterar_preco,
    pode_ajustar_estoque_geral, pode_excluir_catalogo, pode_dar_baixa_avaria,
    pode_acessar_objeto_loja
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

    def test_rn_06_estoque_negativo_bloqueado(self):
        prod = Produto(
            loja=self.loja_a, categoria=self.cat_a, sku='TECL-02',
            nome='Teclado Mecânico', preco=Decimal('199.90'), estoque=-1
        )
        with self.assertRaises(ValidationError):
            prod.clean()

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



