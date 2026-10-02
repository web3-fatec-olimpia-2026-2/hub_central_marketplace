# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Suíte de testes automatizados de segurança, contraste WCAG 2.1, prevenção de CSS Injection e chaveamento de visibilidade pública (Doc ① §22.1 itens 13, 14, 17 e §11.1).
POR QUE FAZ: Garante que as proteções arquiteturais e contratos visuais do ecossistema Django funcionem sem regressões.
"""

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from .models import ConfigTema, ConfigSite
from .utils_tema import (
    calcular_razao_contraste, validar_cor_hex, validar_contraste_wcag,
    gerar_css_tema, PRESETS_MODELOS
)
from apps.tenancy.models import Loja, PerfilUsuario, PapelUsuarioEnum


class TemaContrasteESegurancaTests(TestCase):
    """Validações de contraste WCAG 2.1 e blindagem contra injeção de CSS (Doc ① §22.1 item 13)."""

    def test_presets_canonicos_possuem_contraste_valido(self):
        """Todos os 10 modelos canônicos (T01 a T10) devem cumprir WCAG 2.1 estrito."""
        for modelo_id, p in PRESETS_MODELOS.items():
            with self.subTest(modelo=modelo_id):
                res = validar_contraste_wcag(
                    cor_fundos=p['fundos'],
                    cor_destaques=p['destaques'],
                    cor_escritas=p['escritas'],
                    modelo=modelo_id
                )
                self.assertTrue(res['valido'], f"Modelo {modelo_id} reprovou no teste de contraste")

    def test_contraste_insuficiente_diagnosticado_sem_bloquear(self):
        """Cores com contraste baixo retornam valido=False de forma consultiva sem lançar ValidationError."""
        fundo_branco = "#FFFFFF"
        cinza_muito_claro = "#DDDDDD"

        res = validar_contraste_wcag(
            cor_fundos=fundo_branco,
            cor_destaques=cinza_muito_claro,
            cor_escritas=cinza_muito_claro,
            modelo='T05'
        )
        self.assertFalse(res['valido'])
        self.assertLess(res['ratio_escritas'], res['min_escritas'])

    def test_rejeicao_estrita_de_css_injection(self):
        """Valores que tentam injetar regras CSS arbitrárias devem ser sumariamente rejeitados."""
        payloads_maliciosos = [
            "#FFF; background: url('https://evil.com/leak');",
            "red; } body { display: none; } /*",
            "#123456; color: red;",
            "<script>alert(1)</script>",
            "#GGGGGG",
            "rgb(0,0,0)",
            "transparent",
        ]

        for payload in payloads_maliciosos:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    validar_cor_hex(payload, "cor_teste")

    def test_endpoint_tema_css_retorna_200_e_content_type_correto(self):
        """A rota /tema.css deve ser pública, retornar 200, text/css e headers de cache (Doc ① §22.1 item 14)."""
        response = self.client.get(reverse('site:tema_css'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/css'))
        self.assertIn('max-age=31536000', response.get('Cache-Control', ''))
        self.assertIn('--tema-fundo:', response.content.decode('utf-8'))
        self.assertIn('.btn-primary', response.content.decode('utf-8'))

    def test_context_processor_tema_resiliente(self):
        """O context processor deve fornecer tema padrão sem levantar exceção sob qualquer condição."""
        from .context_processors import tema
        request = self.client.get('/').wsgi_request
        ctx = tema(request)

        self.assertIn('tema', ctx)
        self.assertIn('tema_versao', ctx)
        self.assertIn('shell_template', ctx)
        self.assertIn('menu_grupos', ctx)
        self.assertEqual(ctx['shell_template'], 'layouts/shell/topo.html')


class VisibilidadePublicaTests(TestCase):
    """Testes de chaveamento de rota raiz e política anti-enumeração de rotas (Doc ① §11.1, §17.2 e §22.1 item 17)."""

    def setUp(self):
        self.client = Client()
        self.loja = Loja.objects.create(
            nome="Loja Matriz Teste",
            slug="loja-matriz-teste",
            cnpj="11.222.333/0001-44"
        )
        self.user = User.objects.create_user(
            username="operador_teste",
            password="Password123!"
        )
        self.perfil = PerfilUsuario.objects.create(
            usuario=self.user,
            loja=self.loja,
            papel=PapelUsuarioEnum.USUARIO
        )

    def test_visibilidade_ativa_serve_landing_page_para_anonimo(self):
        """Com visibilidade ativa, anônimo que acessa '/' recebe a Landing Page com status 200."""
        ConfigSite.objects.update_or_create(
            loja=None,
            defaults={'visibilidade_publica': True}
        )
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fonte Única da Verdade")
        self.assertContains(response, reverse('login'))

    def test_visibilidade_desativada_serve_login_para_anonimo(self):
        """Com visibilidade desativada, anônimo que acessa '/' recebe a tela de login."""
        ConfigSite.objects.update_or_create(
            loja=None,
            defaults={'visibilidade_publica': False}
        )
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acesso ao Sistema")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_pagina_publica_controlavel_retorna_404_quando_desativada(self):
        """Quando a visibilidade estiver desativada, /apresentacao/ responde HTTP 404 estrito (anti-enumeração §17.2)."""
        ConfigSite.objects.update_or_create(
            loja=None,
            defaults={'visibilidade_publica': False}
        )
        response = self.client.get(reverse('site:landing'))
        self.assertEqual(response.status_code, 404)

    def test_usuario_autenticado_no_raiz_acessa_area_logada(self):
        """Usuário autenticado que acessa '/' vai diretamente para o Dashboard (área logada)."""
        self.client.login(username="operador_teste", password="Password123!")
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # Deve exibir a navegação interna e a tela de visão geral/dashboard
        self.assertContains(response, "Visão geral")


class NavbarOperacionalTests(TestCase):
    """Testa se a barra de navegação completa e todos os módulos operacionais são renderizados no shell."""

    def setUp(self):
        self.client = Client()
        self.loja = Loja.objects.create(
            nome="Loja Teste Hub",
            slug="loja-teste-hub",
            cnpj="99.888.777/0001-66"
        )
        self.dev_user = User.objects.create_superuser(
            username="dev_admin",
            password="DevPassword123!",
            email="dev@hub.local"
        )
        self.perfil_dev = PerfilUsuario.objects.create(
            usuario=self.dev_user,
            loja=self.loja,
            papel=PapelUsuarioEnum.DEV
        )

    def test_navbar_completa_com_todos_modulos_para_usuario_logado(self):
        """A navbar deve exibir Catálogo, Marketplaces, Pedidos, Financeiro, Lojas, Simulador, Logs, Usuários e Tema."""
        self.client.login(username="dev_admin", password="DevPassword123!")
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        # Módulos operacionais obrigatórios
        self.assertContains(response, 'Hub Marketplaces')
        self.assertContains(response, 'Início')
        self.assertContains(response, 'Lojas')
        self.assertContains(response, 'Catálogo')
        self.assertContains(response, 'Categorias')
        self.assertContains(response, 'Produtos')
        self.assertContains(response, 'Marketplaces')
        self.assertContains(response, 'Canais / Contas')
        self.assertContains(response, 'Anúncios')
        self.assertContains(response, 'Pedidos')
        self.assertContains(response, 'Simulador')
        self.assertContains(response, 'Logs')
        self.assertContains(response, 'Usuários')
        self.assertContains(response, 'Testes')

        # Controles de tema e ambiente
        self.assertContains(response, 'Tema')
        self.assertContains(response, 'Mockar dados')
        self.assertContains(response, 'Superusuário')
        self.assertContains(response, 'dev_admin')
        self.assertContains(response, 'Sair do Sistema')

    def test_navbar_contem_10_modelos_de_tema_e_modal_t10(self):
        """A navbar deve apresentar as opções T01 a T10 e o modal de 3 cores."""
        self.client.login(username="dev_admin", password="DevPassword123!")
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        # 10 modelos canônicos
        self.assertContains(response, 'T01 — Alegre')
        self.assertContains(response, 'T02 — Sofisticado')
        self.assertContains(response, 'T03 — Sóbrio')
        self.assertContains(response, 'T04 — Animado')
        self.assertContains(response, 'T05 — Profissional')
        self.assertContains(response, 'T06 — Luxuoso')
        self.assertContains(response, 'T07 — SoftClean')
        self.assertContains(response, 'T08 — Noturno')
        self.assertContains(response, 'T09 — Acessível')
        self.assertContains(response, 'T10 — Personalizado (3 Cores)')

        # Modal T10
        self.assertContains(response, 'modalTemaPersonalizado')
        self.assertContains(response, 'name="cor_fundos"')
        self.assertContains(response, 'name="cor_destaques"')
        self.assertContains(response, 'name="cor_escritas"')

    def test_alternar_tema_presets_canonicos(self):
        """Alternar para T08 Noturno deve persistir no banco e refletir no endpoint /tema.css."""
        self.client.login(username="dev_admin", password="DevPassword123!")
        response = self.client.post(reverse('site:tema_alternar'), {'modelo': 'T08'}, follow=True)
        self.assertEqual(response.status_code, 200)

        config = ConfigTema.get_tema_ativo(loja=self.loja)
        self.assertEqual(config.modelo, 'T08')
        self.assertEqual(config.cor_fundos, '#12141A')
        self.assertEqual(config.cor_destaques, '#4FA3FF')

        # O CSS dinâmico deve incorporar as novas cores do T08
        resp_css = self.client.get(reverse('site:tema_css'))
        self.assertContains(resp_css, '#4FA3FF')
        self.assertContains(resp_css, '.navbar-app')

    def test_alternar_tema_t10_personalizado_3_cores(self):
        """O modelo T10 deve permitir salvar 3 cores personalizadas com validação estrita."""
        self.client.login(username="dev_admin", password="DevPassword123!")
        dados_t10 = {
            'modelo': 'T10',
            'cor_fundos': '#0A0A0F',
            'cor_destaques': '#00F0FF',
            'cor_escritas': '#F0F0FF',
            'raio': 'arredondado',
            'sombra': 'marcada'
        }
        response = self.client.post(reverse('site:tema_alternar'), dados_t10, follow=True)
        self.assertEqual(response.status_code, 200)

        config = ConfigTema.get_tema_ativo(loja=self.loja)
        self.assertEqual(config.modelo, 'T10')
        self.assertEqual(config.cor_fundos, '#0A0A0F')
        self.assertEqual(config.cor_destaques, '#00F0FF')
        self.assertEqual(config.cor_escritas, '#F0F0FF')
        self.assertEqual(config.raio, 'arredondado')

        resp_css = self.client.get(reverse('site:tema_css'))
        self.assertContains(resp_css, '#00F0FF')

    def test_arquivos_estaticos_admin_e_hub_respondem_200(self):
        """Verifica se os arquivos estáticos nativos do Django Admin e do Hub retornam 200."""
        self.client.login(username="dev_admin", password="DevPassword123!")
        resp_admin_css = self.client.get('/static/admin/css/base.css')
        self.assertEqual(resp_admin_css.status_code, 200)

        resp_base_css = self.client.get('/static/css/base.css')
        self.assertEqual(resp_base_css.status_code, 200)

        resp_app_js = self.client.get('/static/js/app.js')
        self.assertEqual(resp_app_js.status_code, 200)

    def test_gerar_css_tema_inclui_inversao_para_modo_escuro(self):
        """A rota /tema.css deve emitir regras separadas para [data-bs-theme='dark'] com inversão."""
        css = gerar_css_tema(cor_fundos='#F8FAFC', cor_destaques='#1E3A8A', cor_escritas='#0F172A')
        self.assertIn('[data-bs-theme="light"]', css)
        self.assertIn('[data-bs-theme="dark"]', css)
        self.assertIn('#12141A', css)  # Fundo invertido escuro
        self.assertIn('#FFFFFF', css)  # Escrita invertida clara

    def test_alternar_iluminacao_persiste_em_sessao_e_cookies(self):
        """Alternar a iluminação para 'dark' deve gravar na sessão e nos cookies."""
        self.client.login(username="dev_admin", password="DevPassword123!")
        resp = self.client.post(
            reverse('site:tema_alternar'),
            {'iluminacao': 'dark'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.session.get('hub_iluminacao'), 'dark')
        self.assertIn('hub_iluminacao', resp.cookies)
        self.assertEqual(resp.cookies['hub_iluminacao'].value, 'dark')

    def test_alternar_tema_t10_com_fallback_de_pickers(self):
        """Se cor_fundos vier vazio, deve utilizar o valor de picker_fundos."""
        self.client.login(username="dev_admin", password="DevPassword123!")
        dados_pickers = {
            'modelo': 'T10',
            'picker_fundos': '#FFFBEB',
            'picker_destaques': '#D97706',
            'picker_escritas': '#78350F',
        }
        resp = self.client.post(reverse('site:tema_alternar'), dados_pickers, follow=True)
        self.assertEqual(resp.status_code, 200)

        config = ConfigTema.get_tema_ativo(loja=self.loja)
        self.assertEqual(config.modelo, 'T10')
        self.assertEqual(config.cor_fundos, '#FFFBEB')
        self.assertEqual(config.cor_destaques, '#D97706')
        self.assertEqual(config.cor_escritas, '#78350F')


