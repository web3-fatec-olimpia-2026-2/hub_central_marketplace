from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from .models import Loja, PerfilUsuario
from .forms import LojaForm


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
            usuario=self.user_dev, papel=PerfilUsuario.PAPEL_DEV, loja=None
        )
        self.assertTrue(perfil_dev.is_dev)
        self.assertFalse(perfil_dev.is_admin)
        self.assertIsNone(perfil_dev.loja)

    def test_perfil_admin_vinculado_a_loja(self):
        perfil_admin = PerfilUsuario.objects.create(
            usuario=self.user_admin, papel=PerfilUsuario.PAPEL_ADMIN, loja=self.loja
        )
        self.assertTrue(perfil_admin.is_admin)
        self.assertFalse(perfil_admin.is_dev)
        self.assertEqual(perfil_admin.loja, self.loja)

    def test_clean_bloqueia_perfil_nao_dev_sem_loja(self):
        perfil = PerfilUsuario(
            usuario=self.user_sem_loja, papel=PerfilUsuario.PAPEL_ADMIN, loja=None
        )
        with self.assertRaises(ValidationError):
            perfil.clean()


class LojaFormTestCase(TestCase):
    """
    Testes do formulário LojaForm.
    """
    def test_form_valido(self):
        form_data = {
            'nome': 'Loja Beta Tech',
            'cnpj': '55.555.555/0001-55',
            'inscricao_estadual': 'ISENTO',
            'telefone': '(21) 99999-8888',
            'email': 'beta@tech.com.br',
            'cep': '20000-000',
            'endereco': 'Rua do Ouvidor',
            'numero': '50',
            'complemento': '',
            'bairro': 'Centro',
            'cidade': 'Rio de Janeiro',
            'estado': 'RJ',
            'pais': 'Brasil',
            'ativo': True,
        }
        form = LojaForm(data=form_data)
        self.assertTrue(form.is_valid())
        loja = form.save()
        self.assertEqual(loja.slug, 'loja-beta-tech')


class LojaRBACSecurityTestCase(TestCase):
    """
    Testes de segurança e isolamento de acesso (RBAC / RN-07) nas telas de gestão de Lojas.
    """
    def setUp(self):
        self.client = Client()
        self.loja = Loja.objects.create(nome='Loja Existente', cnpj='66.666.666/0001-66')

        # Usuário DEV
        self.user_dev = User.objects.create_user(username='dev_user', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PerfilUsuario.PAPEL_DEV, loja=None)

        # Usuário ADMIN de loja
        self.user_admin = User.objects.create_user(username='admin_user', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PerfilUsuario.PAPEL_ADMIN, loja=self.loja)

        # Usuário Padrão de loja
        self.user_padrao = User.objects.create_user(username='padrao_user', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PerfilUsuario.PAPEL_USUARIO, loja=self.loja)

    def test_usuario_anonimo_redireciona_para_login(self):
        response_list = self.client.get(reverse('loja_list'))
        self.assertEqual(response_list.status_code, 302)
        self.assertIn(reverse('login'), response_list.url)

        response_create = self.client.get(reverse('loja_create'))
        self.assertEqual(response_create.status_code, 302)
        self.assertIn(reverse('login'), response_create.url)

    def test_usuario_admin_bloqueado_de_acessar_gestao_de_lojas(self):
        self.client.login(username='admin_user', password='password123')
        
        response_list = self.client.get(reverse('loja_list'))
        self.assertEqual(response_list.status_code, 403)

        response_create = self.client.get(reverse('loja_create'))
        self.assertEqual(response_create.status_code, 403)

    def test_usuario_padrao_bloqueado_de_acessar_gestao_de_lojas(self):
        self.client.login(username='padrao_user', password='password123')
        
        response_list = self.client.get(reverse('loja_list'))
        self.assertEqual(response_list.status_code, 403)

        response_create = self.client.get(reverse('loja_create'))
        self.assertEqual(response_create.status_code, 403)

    def test_usuario_dev_acessa_lista_e_cadastro_com_sucesso(self):
        self.client.login(username='dev_user', password='password123')
        
        # Acesso à lista
        response_list = self.client.get(reverse('loja_list'))
        self.assertEqual(response_list.status_code, 200)
        self.assertContains(response_list, 'Loja Existente')

        # Acesso ao formulário de criação
        response_create = self.client.get(reverse('loja_create'))
        self.assertEqual(response_create.status_code, 200)
        self.assertContains(response_create, 'Cadastro de Nova Loja (Tenant)')

    def test_usuario_dev_cria_nova_loja_com_todos_os_campos(self):
        self.client.login(username='dev_user', password='password123')
        
        post_data = {
            'nome': 'Nova Loja E-commerce Hub',
            'cnpj': '77.777.777/0001-77',
            'inscricao_estadual': '987.654.321',
            'telefone': '(31) 98888-7777',
            'email': 'contato@novaloja.com',
            'cep': '30100-000',
            'endereco': 'Avenida Afonso Pena',
            'numero': '1500',
            'complemento': 'Andar 8',
            'bairro': 'Centro',
            'cidade': 'Belo Horizonte',
            'estado': 'MG',
            'pais': 'Brasil',
            'ativo': 'on',
            'meli_client_id': 'meli-app-bh-01',
            'meli_client_secret': 'meli-sec-bh-01',
        }
        response = self.client.post(reverse('loja_create'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nova Loja E-commerce Hub')

        # Verifica se gravou no banco de dados com todos os dados
        loja = Loja.objects.get(cnpj='77.777.777/0001-77')
        self.assertEqual(loja.nome, 'Nova Loja E-commerce Hub')
        self.assertEqual(loja.cidade, 'Belo Horizonte')
        self.assertEqual(loja.estado, 'MG')
        self.assertEqual(loja.endereco, 'Avenida Afonso Pena')
        self.assertEqual(loja.numero, '1500')
        self.assertEqual(loja.bairro, 'Centro')
        self.assertEqual(loja.cep, '30100-000')
        self.assertEqual(loja.meli_client_id, 'meli-app-bh-01')
        self.assertTrue(loja.ativo)

    def test_usuario_dev_edita_loja(self):
        self.client.login(username='dev_user', password='password123')
        
        edit_data = {
            'nome': 'Loja Existente Renomeada',
            'slug': self.loja.slug,
            'cnpj': self.loja.cnpj,
            'inscricao_estadual': '123456',
            'telefone': '(11) 91111-2222',
            'email': 'editada@loja.com',
            'cep': '04500-000',
            'endereco': 'Rua Funchal',
            'numero': '200',
            'complemento': '',
            'bairro': 'Vila Olímpia',
            'cidade': 'São Paulo',
            'estado': 'SP',
            'pais': 'Brasil',
            'ativo': 'on',
        }
        response = self.client.post(
            reverse('loja_update', kwargs={'slug': self.loja.slug}),
            data=edit_data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.nome, 'Loja Existente Renomeada')
        self.assertEqual(self.loja.cidade, 'São Paulo')

