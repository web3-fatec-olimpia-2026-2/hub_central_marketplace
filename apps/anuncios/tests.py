# Os códigos foram gerados com auxilio de I.A.

# Importa a classe Decimal para manipulação precisa de moeda sem discrepâncias de ponto flutuante
from decimal import Decimal

# Importa as ferramentas de simulação e substituição de chamadas externas do módulo padrão unittest.mock
from unittest.mock import patch, MagicMock

# Importa a classe base de casos de teste com isolamento transacional e o cliente HTTP de testes do Django
from django.test import TestCase, Client

# Importa o modelo padrão User do Django para simulação de usuários autenticados
from django.contrib.auth.models import User

# Importa o resolvedor reverso de URLs do Django para obter rotas a partir dos nomes
from django.urls import reverse

# Importa os modelos de Loja (tenant) e Perfil de Usuário da aplicação tenancy
from apps.tenancy.models import Loja, PerfilUsuario

# Importa o enum que padroniza os papéis de controle de acesso (DEV, ADMIN, SUPERVISOR, USUARIO)
from apps.tenancy.enums import PapelUsuarioEnum

# Importa os modelos de credenciais de marketplace e as tabelas de auditoria de eventos
from apps.marketplaces.models import ContaMarketplace, LogSincronizacao, LogAuditoria

# Importa os enums que definem os marketplaces suportados e os tipos de eventos auditáveis
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum

# Importa a classe do conector da API do Mercado Livre para interceptação de métodos via mocks
from apps.marketplaces.connectors.mercadolivre import MercadoLivreConnector

# Importa os modelos de Categoria e Produto gerenciados pelo catálogo físico
from apps.catalogo.models import Categoria, Produto

# Importa os modelos de Anúncio e a tabela de composição/ficha técnica (kits e combos)
from apps.anuncios.models import Anuncio, AnuncioComposicao

# Importa os serviços de importação e sincronização de anúncios para testes unitários diretos
from apps.anuncios.services import AnuncioImportacaoService, SincronizacaoAnuncioService, AnuncioSincronizacaoService


# Classe de testes focada na importação de anúncios externos, regras de cota de kits e paginação da API
class AnunciosMarketplaceTestCase(TestCase):
    # Docstring que resume a abrangência da primeira fase de testes do ciclo de vida de anúncios
    """
    Suíte de testes para a Fase 1: Importação de Anúncios, Ficha Técnica / Kits e Paginação Scan & Bulk.
    """

    # Método de preparação do fixture executado antes de cada teste unitário desta classe
    def setUp(self):
        # Instancia o cliente simulador de requisições HTTP do Django
        self.client = Client()

        # Cria a loja matriz que representará o tenant principal nos cenários de teste
        self.loja = Loja.objects.create(
            nome="Loja Matriz",
            slug="loja-matriz",
            cnpj="11.111.111/0001-11"
        )
        # Assegura a habilitação de todos os módulos contratuais padrões para este tenant
        self.loja.garantir_modulos_padrao()

        # Cria uma categoria de informática associada ao tenant atual
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Informática",
            slug="informatica"
        )

        # Produto 1: Mouse Óptico (Estoque: 10)
        # Cria o produto físico de teste representando 10 unidades de estoque real
        self.produto_mouse = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="MOUSE-OPT-01",
            nome="Mouse Óptico USB",
            preco=Decimal('50.00'),
            estoque=10
        )

        # Produto 2: Teclado Mecânico (Estoque: 4)
        # Cria o produto físico de teste com estoque menor para simular gargalos em kits
        self.produto_teclado = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="TEC-MEC-01",
            nome="Teclado Mecânico RGB",
            preco=Decimal('200.00'),
            estoque=4
        )

        # Usuários RBAC
        # Cria usuário comum com privilégios administrativos
        self.user_admin = User.objects.create_user(username='admin_loja', password='password123')
        # Anexa o perfil administrativo vinculado ao tenant atual
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        # Cria usuário restrito com permissão de operador padrão
        self.user_padrao = User.objects.create_user(username='usuario_loja', password='password123')
        # Associa o perfil de leitura/operação básica sem permissões executivas
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

        # Conta Mercado Livre
        # Registra uma conta de integração ativa para o canal Mercado Livre vinculada à loja matriz
        self.conta_meli = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Matriz",
            access_token="APP_USR_TEST_VALID_TOKEN",
            refresh_token="REFRESH_VALID_TOKEN",
            seller_id_externo="86176658"
        )

    # Teste para validação do algoritmo de cota gargalo para itens simples e kits
    def test_calculo_cota_disponivel_unitario_e_kit(self):
        """Valida o cálculo da cota máxima vendável para anúncio unitário e para kit."""
        # 1. Anúncio Unitário (Mouse - 1x)
        # Cria anúncio unitário correspondente a 1 unidade física de mouse
        anuncio_unit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB1001",
            titulo="Mouse Óptico Unitário",
            preco_venda=Decimal('55.00'),
            estoque_publicado=10,
            sku_vendedor="MOUSE-OPT-01"
        )
        # Cria a composição unitária vinculando 1 unidade do mouse físico ao anúncio
        AnuncioComposicao.objects.create(
            anuncio=anuncio_unit,
            produto=self.produto_mouse,
            quantidade=1
        )
        # Cota deve ser igual ao estoque do mouse (10)
        # Valida se a cota do anúncio unitário espelha fielmente o saldo físico de 10 unidades
        self.assertEqual(anuncio_unit.calcular_cota_disponivel(), 10)
        # Confirma que um anúncio unitário com multiplicador 1 não é classificado como kit
        self.assertFalse(anuncio_unit.eh_kit)

        # 2. Anúncio Kit 3x Mouse
        # Cria anúncio de kit composto por 3 unidades do mesmo produto físico
        anuncio_kit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB1002",
            titulo="Kit 3x Mouse Óptico",
            preco_venda=Decimal('140.00'),
            estoque_publicado=3,
            sku_vendedor="KIT-MOUSE-3X"
        )
        # Cria o registro de composição do pacote com multiplicador 3
        AnuncioComposicao.objects.create(
            anuncio=anuncio_kit,
            produto=self.produto_mouse,
            quantidade=3
        )
        # Cota deve ser floor(10 / 3) = 3
        # Valida o cálculo matemático floor(10/3) resultando em 3 kits completos
        self.assertEqual(anuncio_kit.calcular_cota_disponivel(), 3)
        # Valida que o multiplicador maior que 1 ativa a flag de kit
        self.assertTrue(anuncio_kit.eh_kit)

        # 3. Anúncio Combo (2x Mouse + 1x Teclado)
        # Cria anúncio representando um combo multiproduto com dois itens diferentes
        anuncio_combo = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB1003",
            titulo="Combo Gamer (2 Mouse + 1 Teclado)",
            preco_venda=Decimal('280.00'),
            estoque_publicado=4,
            sku_vendedor="COMBO-GAMER"
        )
        # Associa 2 mouses ao combo
        AnuncioComposicao.objects.create(anuncio=anuncio_combo, produto=self.produto_mouse, quantidade=2)
        # Associa 1 teclado ao combo
        AnuncioComposicao.objects.create(anuncio=anuncio_combo, produto=self.produto_teclado, quantidade=1)

        # Mouse: 10 // 2 = 5; Teclado: 4 // 1 = 4. Cota = min(5, 4) = 4
        # Valida a cota gargalo: o menor entre 10//2=5 e 4//1=4 deve ser 4
        self.assertEqual(anuncio_combo.calcular_cota_disponivel(), 4)
        # Confirma que composição heterogênea é classificada como kit/combo
        self.assertTrue(anuncio_combo.eh_kit)

        # Se estoque do teclado zerar, cota vai a zero
        # Zera deliberadamente o estoque de um dos componentes do combo
        self.produto_teclado.estoque = 0
        # Persiste o saldo zerado
        self.produto_teclado.save()
        # Valida que a indisponibilidade de um item zera a cota do combo inteiro
        self.assertEqual(anuncio_combo.calcular_cota_disponivel(), 0)

    # Intercepta as chamadas HTTP GET realizadas pela biblioteca requests
    @patch('requests.get')
    def test_importar_anuncios_paginacao_normal_e_bulk_chunking(self, mock_get):
        """Valida paginação comum e fatiamento correto em lotes de até 20 itens para /items/bulk."""
        # 25 IDs para testar chunking (20 + 5)
        # Gera 25 IDs de anúncios para testar a divisão do limite de 20 por requisição bulk
        item_ids = [f"MLB{i:05d}" for i in range(1, 26)]

        # Mock 1: /items/search com 25 resultados
        # Prepara a simulação da resposta da busca de anúncios do vendedor no Mercado Livre
        resp_search = MagicMock()
        resp_search.status_code = 200
        resp_search.json.return_value = {
            "paging": {"total": 25, "offset": 0, "limit": 100},
            "results": item_ids
        }

        # Mock 2: /items/bulk chunk 1 (20 itens)
        # Monta a resposta em lote para os primeiros 20 anúncios
        bulk_items_1 = [
            {"code": 200, "body": {"id": item_id, "title": f"Produto {item_id}", "price": 99.90, "available_quantity": 10, "status": "active", "seller_custom_field": "MOUSE-OPT-01"}}
            for item_id in item_ids[:20]
        ]
        resp_bulk_1 = MagicMock()
        resp_bulk_1.status_code = 200
        resp_bulk_1.json.return_value = bulk_items_1

        # Mock 3: /items/bulk chunk 2 (5 itens)
        # Monta a resposta em lote para os 5 anúncios excedentes restantes
        bulk_items_2 = [
            {"code": 200, "body": {"id": item_id, "title": f"Produto {item_id}", "price": 49.90, "available_quantity": 5, "status": "active", "seller_custom_field": "TEC-MEC-01"}}
            for item_id in item_ids[20:]
        ]
        resp_bulk_2 = MagicMock()
        resp_bulk_2.status_code = 200
        resp_bulk_2.json.return_value = bulk_items_2

        # Define a sequência de retornos para as 3 chamadas consecutivas de GET
        mock_get.side_effect = [resp_search, resp_bulk_1, resp_bulk_2]

        # Obtém a instância do conector associado à conta do Mercado Livre
        connector = self.conta_meli.get_connector()
        # Força requisição HTTP
        # Desativa retornos sintéticos locais para forçar o conector a chamar os mocks do requests
        connector._forcar_http_real = True

        # Simula o token de acesso válido sem acionar endpoints reais de renovação OAuth
        with patch.object(connector, 'get_valid_access_token', return_value="FAKE_TOKEN"):
            # Dispara a importação de anúncios via conector
            res = connector.importar_anuncios()

        # Valida que o processamento da importação foi concluído com sucesso
        self.assertTrue(res['sucesso'])
        # Valida que todos os 25 itens foram totalizados
        self.assertEqual(res['total'], 25)
        # Valida que a lista tratada contém exatamente 25 objetos
        self.assertEqual(len(res['itens']), 25)

        # Valida que /items/bulk foi chamado 2 vezes
        # Extrai os parâmetros das URLs requisitadas durante os testes
        calls = [c[0][0] for c in mock_get.call_args_list]
        # Filtra apenas as URLs que bateram no endpoint de dados em lote /items/bulk
        bulk_calls = [c for c in calls if '/items/bulk?ids=' in c]
        # Valida se foram feitos exatamente 2 disparos em lote (um de 20 e outro de 5)
        self.assertEqual(len(bulk_calls), 2)
        # Confirma que a primeira fatia transmitiu exatamente 20 identificadores
        self.assertEqual(len(bulk_calls[0].split('ids=')[1].split(',')), 20)
        # Confirma que a segunda fatia transmitiu exatamente os 5 identificadores finais
        self.assertEqual(len(bulk_calls[1].split('ids=')[1].split(',')), 5)

    # Intercepta as requisições GET para simulação do modo de paginação via scroll/cursor
    @patch('requests.get')
    def test_importar_anuncios_scan_mode(self, mock_get):
        """Valida que contas com search_type=scan consomem scroll_id até exaustão."""
        # Configura a primeira página do cursor retornando um scroll_id e 2 resultados
        resp_scan_1 = MagicMock()
        resp_scan_1.status_code = 200
        resp_scan_1.json.return_value = {
            "scroll_id": "SCROLL_123",
            "results": ["MLB101", "MLB102"]
        }

        # Configura a segunda e última página de cursor sem scroll_id novo, indicando fim do fluxo
        resp_scan_2 = MagicMock()
        resp_scan_2.status_code = 200
        resp_scan_2.json.return_value = {
            "scroll_id": None,
            "results": ["MLB103"]
        }

        # Monta a resposta detalhada dos 3 itens para a etapa subsequente de bulk
        resp_bulk = MagicMock()
        resp_bulk.status_code = 200
        resp_bulk.json.return_value = [
            {"code": 200, "body": {"id": "MLB101", "title": "Item 1", "price": 10.0, "available_quantity": 2}},
            {"code": 200, "body": {"id": "MLB102", "title": "Item 2", "price": 20.0, "available_quantity": 3}},
            {"code": 200, "body": {"id": "MLB103", "title": "Item 3", "price": 30.0, "available_quantity": 4}},
        ]

        # Define a ordem de respostas das requisições simuladas
        mock_get.side_effect = [resp_scan_1, resp_scan_2, resp_bulk]

        # Instancia o conector configurando-o para disparar requisições
        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        # Emula token válido e executa a rotina de importação no modo de varredura (scan)
        with patch.object(connector, 'get_valid_access_token', return_value="FAKE_TOKEN"):
            res = connector.importar_anuncios(search_type='scan')

        # Assegura a conclusão correta da importação
        self.assertTrue(res['sucesso'])
        # Valida que o total acumulado das duas páginas do cursor foi de 3 itens
        self.assertEqual(res['total'], 3)
        # Confirma que os 3 IDs externos coincidem com os dados retornados
        self.assertEqual([i['item_id_externo'] for i in res['itens']], ['MLB101', 'MLB102', 'MLB103'])

    # Teste de persistência idempotente e amarração automática de catálogo por SKU
    def test_persistencia_idempotente_e_autovinculo_sku(self):
        """Valida persistência idempotente no banco e auto-vínculo de AnuncioComposicao por SKU."""
        # Monta payload simulado contendo dois anúncios, um com SKU existente no estoque e outro sem
        mock_itens = [
            {
                "item_id_externo": "MLB9991",
                "titulo": "Mouse Óptico Importado",
                "preco": Decimal("59.90"),
                "quantidade_disponivel": 8,
                "status": "active",
                "sku_vendedor": "MOUSE-OPT-01",  # Coincide com self.produto_mouse.sku
                "thumbnail": "https://img.mlstatic.com/item1.jpg",
                "permalink": "https://produto.mercadolivre.com.br/MLB9991",
            },
            {
                "item_id_externo": "MLB9992",
                "titulo": "Headset Gamer Sem Cadastro",
                "preco": Decimal("150.00"),
                "quantidade_disponivel": 2,
                "status": "active",
                "sku_vendedor": "HEADSET-SEM-CADASTRO",
                "thumbnail": None,
                "permalink": None,
            }
        ]

        # Intercepta o método do conector para retornar diretamente o payload simulado
        with patch.object(MercadoLivreConnector, 'importar_anuncios', return_value={"sucesso": True, "itens": mock_itens, "total": 2}):
            # 1. Primeira Execução
            # Executa a importação inicial pela camada de serviço
            res1 = AnuncioImportacaoService.importar_anuncios_da_conta(self.conta_meli, usuario=self.user_admin)
            # Valida o sucesso do processamento do serviço
            self.assertTrue(res1['sucesso'])
            # Valida a criação de 2 novos anúncios na base
            self.assertEqual(res1['total_importados'], 2)
            # Confirma que apenas 1 anúncio foi vinculado automaticamente por correspondência de SKU físico
            self.assertEqual(res1['total_vinculados'], 1)  # Apenas MOUSE-OPT-01 existia no estoque

            # Confirma persistência
            # Recupera o anúncio importado do banco
            anuncio1 = Anuncio.objects.get(conta=self.conta_meli, item_id_externo="MLB9991")
            # Valida o título gravado
            self.assertEqual(anuncio1.titulo, "Mouse Óptico Importado")
            # Valida que foi criada 1 linha de composição automaticamente
            self.assertEqual(anuncio1.itens_composicao.count(), 1)
            # Confirma que o produto físico vinculado é o produto_mouse cadastrado no setUp
            self.assertEqual(anuncio1.itens_composicao.first().produto, self.produto_mouse)
            # Confirma que a cota calculada assumiu o saldo físico disponível do mouse (10)
            self.assertEqual(anuncio1.calcular_cota_disponivel(), 10)

            # Recupera o segundo anúncio cujo SKU não existe no cadastro local
            anuncio2 = Anuncio.objects.get(conta=self.conta_meli, item_id_externo="MLB9992")
            # Valida que ele não recebeu composição automática, permanecendo desvinculado
            self.assertEqual(anuncio2.itens_composicao.count(), 0)

            # 2. Segunda Execução (Idempotência com atualização de preço e título)
            # Modifica os valores do payload para testar a atualização segura sem criar duplicatas
            mock_itens[0]["titulo"] = "Mouse Óptico Importado (Atualizado)"
            mock_itens[0]["preco"] = Decimal("64.90")

            # Executa a importação novamente sobre a mesma conta
            res2 = AnuncioImportacaoService.importar_anuncios_da_conta(self.conta_meli, usuario=self.user_admin)
            # Valida o sucesso da operação
            self.assertTrue(res2['sucesso'])
            # Confirma que nenhum novo anúncio foi inserido (total_importados = 0)
            self.assertEqual(res2['total_importados'], 0)
            # Confirma que os 2 anúncios preexistentes foram apenas atualizados
            self.assertEqual(res2['total_atualizados'], 2)

            # Recarrega os dados do anúncio a partir do banco de dados
            anuncio1.refresh_from_db()
            # Valida se o título foi modificado no banco
            self.assertEqual(anuncio1.titulo, "Mouse Óptico Importado (Atualizado)")
            # Valida se o preço de venda foi ajustado
            self.assertEqual(anuncio1.preco_venda, Decimal("64.90"))
            # Garante que a contagem total de anúncios permaneceu inalterada em 2
            self.assertEqual(Anuncio.objects.filter(conta=self.conta_meli).count(), 2)

    # Teste de autorização em endpoints de anúncios aplicando controle de acesso (RBAC)
    def test_anuncio_views_and_rbac_permissions(self):
        """Valida endpoints de listagem, disparo de importação e RBAC."""
        # 1. Usuário comum (USUARIO) tem acesso à listagem mas é bloqueado ao disparar importação (403)
        # Efetua login com o usuário restrito de operação
        self.client.login(username='usuario_loja', password='password123')
        # Requisita a tela de listagem de anúncios
        res_list = self.client.get(reverse('anuncio_list'))
        # Valida que a visualização da listagem é autorizada com HTTP 200
        self.assertEqual(res_list.status_code, 200)

        # Tenta disparar a importação de anúncios da conta
        res_import_forbidden = self.client.post(reverse('anuncio_importar', kwargs={'pk': self.conta_meli.pk}))
        # Valida que o operador comum é bloqueado com status HTTP 403 Forbidden
        self.assertEqual(res_import_forbidden.status_code, 403)

        # 2. Administrador (ADMIN) pode disparar importação com sucesso
        # Efetua login com o perfil administrativo
        self.client.login(username='admin_loja', password='password123')
        # Intercepta a chamada ao conector durante a requisição da view
        with patch.object(MercadoLivreConnector, 'importar_anuncios') as mock_imp:
            mock_imp.return_value = {
                "sucesso": True,
                "itens": [
                    {
                        "item_id_externo": "MLB7771",
                        "titulo": "Item Teste View",
                        "preco": Decimal("30.00"),
                        "quantidade_disponivel": 1,
                        "status": "active",
                    }
                ],
                "total": 1
            }
            # Envia a requisição POST seguindo os redirecionamentos da resposta
            res_import = self.client.post(reverse('anuncio_importar', kwargs={'pk': self.conta_meli.pk}), follow=True)
            # Valida resposta HTTP 200 após o redirecionamento
            self.assertEqual(res_import.status_code, 200)
            # Valida a mensagem flash de sucesso renderizada no template
            self.assertContains(res_import, "Importação de anúncios concluída com sucesso!")
            # Confirma a existência do novo anúncio gravado no banco
            self.assertTrue(Anuncio.objects.filter(item_id_externo="MLB7771").exists())

        # 3. Gerenciamento de Composição via View
        # Obtém a instância do anúncio recém-importado
        anuncio = Anuncio.objects.get(item_id_externo="MLB7771")
        # Submete requisição para vincular 2 unidades do mouse físico a este anúncio
        res_comp = self.client.post(reverse('anuncio_composicao_add', kwargs={'pk': anuncio.pk}), {
            'produto': self.produto_mouse.pk,
            'quantidade': 2
        })
        # Valida redirecionamento pós-inclusão (HTTP 302 Found)
        self.assertEqual(res_comp.status_code, 302)
        # Confirma que a composição do anúncio possui 1 componente cadastrado
        self.assertEqual(anuncio.itens_composicao.count(), 1)
        # Valida que o multiplicador cadastrado foi gravado com valor 2
        self.assertEqual(anuncio.itens_composicao.first().quantidade, 2)


# Classe de testes para rotinas de sincronização, Circuit Breaker e integridade de eventos
class SincronizacaoEstoquePrecoTestCase(TestCase):
    # Docstring explicativa das validações defensivas e de concorrência cobertas na Fase 2
    """
    Suíte de testes para a Fase 2: Sincronização segura de estoque e preço no Mercado Livre,
    lógica defensiva, Circuit Breaker e disparo por Django Signals.
    """

    # Prepara o estado inicial compartilhado para os testes de sincronização
    def setUp(self):
        # Cria a loja para testes de sincronização
        self.loja = Loja.objects.create(
            nome="Loja Sync",
            slug="loja-sync",
            cnpj="22.222.222/0001-22"
        )
        # Garante a habilitação dos módulos necessários
        self.loja.garantir_modulos_padrao()
        # Cria a categoria de produtos eletrônicos
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Eletrônicos",
            slug="eletronicos"
        )

        # Cria produto principal do catálogo com 20 unidades de saldo físico
        self.produto_gamer = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="HEADSET-01",
            nome="Headset Gamer 7.1",
            preco=Decimal('100.00'),
            estoque=20
        )

        # Cria produto acessório com saldo limitado a 6 unidades
        self.produto_acessorio = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SUPORTE-01",
            nome="Suporte Headset RGB",
            preco=Decimal('50.00'),
            estoque=6
        )

        # Cria usuário administrador para disparar operações com auditoria
        self.user_admin = User.objects.create_user(username='admin_sync', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        # Cria a conta do Mercado Livre vinculada à loja
        self.conta_meli = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Sync",
            access_token="APP_USR_REAL_TEST_TOKEN",
            refresh_token="TG_REAL_TEST_REFRESH",
            seller_id_externo="99887766"
        )

        # Anúncio 1: Unitário (Headset)
        # Cria anúncio unitário para o produto headset
        self.anuncio_unitario = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB2001",
            titulo="Headset Gamer 7.1 Surround",
            preco_venda=Decimal('100.00'),
            estoque_publicado=20,
            status='active',
            sku_vendedor="HEADSET-01"
        )
        # Vincula 1 unidade física do headset ao anúncio unitário
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_unitario,
            produto=self.produto_gamer,
            quantidade=1
        )

        # Anúncio 2: Kit Gamer (1x Headset + 2x Suporte)
        # Cria anúncio representando um kit com dois componentes físicos diferentes
        self.anuncio_kit = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB2002",
            titulo="Kit Combo Gamer Headset + 2 Suportes",
            preco_venda=Decimal('189.90'),
            estoque_publicado=3,
            status='active',
            sku_vendedor="KIT-GAMER-01"
        )
        # Adiciona 1 headset à composição do kit
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_kit,
            produto=self.produto_gamer,
            quantidade=1
        )
        # Adiciona 2 suportes à composição do kit
        AnuncioComposicao.objects.create(
            anuncio=self.anuncio_kit,
            produto=self.produto_acessorio,
            quantidade=2
        )

    # Intercepta as requisições HTTP PUT de atualização no canal externo
    @patch('requests.put')
    def test_conector_meli_atualizar_estoque_e_preco_sucesso(self, mock_put):
        """Valida PUT /items/{id} para estoque e preço com criação de LogSincronizacao."""
        # Monta a simulação da resposta de sucesso da API externa
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "MLB2001", "status": "updated"}
        mock_put.return_value = mock_resp

        # Prepara o conector para chamadas simuladas de rede
        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        # 1. Atualizar Estoque
        # Executa o ajuste de saldo no conector
        ok_est, msg_est, log_est = connector.atualizar_estoque("MLB2001", 15, usuario=self.user_admin)
        # Valida o status positivo da operação
        self.assertTrue(ok_est)
        # Confirma o teor da mensagem retornada
        self.assertIn("Estoque sincronizado no Mercado Livre: 15 un.", msg_est)
        # Valida que a entidade de log de auditoria foi gerada
        self.assertIsNotNone(log_est)
        # Valida que o evento gravado foi de sincronização de estoque
        self.assertEqual(log_est.evento, EventoAuditoriaEnum.SYNC_ESTOQUE)
        # Valida o ID externo registrado no log
        self.assertEqual(log_est.item_id_externo, "MLB2001")
        # Valida que o payload enviado contém a chave exigida pela API remota
        self.assertEqual(log_est.payload_enviado, {"available_quantity": 15})

        # 2. Atualizar Preço
        # Executa o ajuste de preço no conector
        ok_prc, msg_prc, log_prc = connector.atualizar_preco("MLB2001", Decimal('119.90'), usuario=self.user_admin)
        # Valida retorno de sucesso
        self.assertTrue(ok_prc)
        # Confirma mensagem amigável contendo o novo valor
        self.assertIn("Preço de R$ 119.90 sincronizado no Mercado Livre!", msg_prc)
        # Valida o registro de log criado para o preço
        self.assertIsNotNone(log_prc)
        # Valida o enum correspondente ao evento de preço
        self.assertEqual(log_prc.evento, EventoAuditoriaEnum.SYNC_PRECO)
        # Valida o payload de preço formatado
        self.assertEqual(log_prc.payload_enviado, {"price": 119.90})

    # Teste de renovação automática do token OAuth2 quando a requisição retornar HTTP 401
    @patch('requests.put')
    def test_conector_meli_retry_refresh_sob_401(self, mock_put):
        """Valida que resposta HTTP 401 dispara renovar_token e retenta a requisição."""
        # Simula resposta de token expirado (HTTP 401)
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.json.return_value = {"message": "Invalid token"}

        # Simula resposta bem-sucedida (HTTP 200) na tentativa de reexecução
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"id": "MLB2001", "status": "updated"}

        # Encadeia as respostas: a primeira falha com 401 e a segunda tem sucesso com 200
        mock_put.side_effect = [resp_401, resp_200]

        # Obtém o conector da conta
        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        # Intercepta o método renovar_token para simular um refresh bem-sucedido
        with patch.object(connector, 'renovar_token', return_value=(True, "Token renovado")) as mock_renovar:
            ok, msg, log = connector.atualizar_estoque("MLB2001", 12)
            # Valida que o conector recuperou o fluxo e finalizou com sucesso
            self.assertTrue(ok)
            # Confirma que o método de renovação de token foi acionado exatamente 1 vez
            self.assertEqual(mock_renovar.call_count, 1)
            # Confirma que foram feitas 2 chamadas PUT (a original e o retry com novo token)
            self.assertEqual(mock_put.call_count, 2)

    # Teste de manipulação de respostas de erro da API do parceiro comercial
    @patch('requests.put')
    def test_conector_meli_rejeicao_api_externa(self, mock_put):
        """Valida tratamento de erro HTTP 400 com log de auditoria de falha."""
        # Simula rejeição de requisição com status HTTP 400 Bad Request
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.json.return_value = {"message": "Item paused, cannot update stock"}
        mock_put.return_value = resp_400

        # Prepara o conector para a chamada
        connector = self.conta_meli.get_connector()
        connector._forcar_http_real = True

        # Dispara a sincronização esperando falha tratada
        ok, msg, log = connector.atualizar_estoque("MLB2001", 5)
        # Valida que o resultado retornou como falso
        self.assertFalse(ok)
        # Confirma que a mensagem detalha o motivo da rejeição da API parceira
        self.assertIn("Mercado Livre rejeitou sincronização de estoque", msg)
        # Valida que o registro de falha foi gravado para auditoria
        self.assertIsNotNone(log)
        # Valida que a flag de sucesso do log foi marcada como False
        self.assertFalse(log.sucesso)
        # Confirma que o código HTTP 400 foi persistido no log
        self.assertEqual(log.status_http, 400)

    # Teste de recálculo dinâmico da cota de kits mediante alteração de saldo físico de um componente
    def test_sincronizacao_cota_kit_e_unitario(self):
        """Valida cálculo de cota de kit (min entre componentes) e envio correto."""
        # Suporte tem estoque 6. Multiplicador no kit é 2. Logo cota do kit = 6 // 2 = 3.
        # Valida a cota inicial com base nos estoques do setup (6 // 2 = 3)
        self.assertEqual(self.anuncio_kit.calcular_cota_disponivel(), 3)

        # Alterando estoque do suporte para 4: nova cota do kit deve ser 4 // 2 = 2.
        # Altera o saldo físico do acessório para 4 unidades
        self.produto_acessorio.estoque = 4
        # Salva o produto acessório
        self.produto_acessorio.save()

        # Valida que a cota recalculada é imediatamente rebaixada para 2 (4 // 2 = 2)
        self.assertEqual(self.anuncio_kit.calcular_cota_disponivel(), 2)

        # Simula a chamada de rede ao conector para envio da nova cota
        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_att:
            mock_att.return_value = (True, "OK", None)
            # Dispara a sincronização de estoque forçada para o kit
            res = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(self.anuncio_kit, forcar=True)
            # Valida o sucesso do retorno do serviço
            self.assertTrue(res['sucesso'])
            # Confirma que o saldo enviado ao marketplace foi a cota calculada (2)
            self.assertEqual(res['estoque_sincronizado'], 2)
            # Recarrega o anúncio do banco
            self.anuncio_kit.refresh_from_db()
            # Confirma que o snapshot local gravou a nova cota (2)
            self.assertEqual(self.anuncio_kit.estoque_publicado, 2)

    # Validação do tratamento defensivo contra estoques negativos no catálogo
    def test_bloqueio_saldo_negativo_defensivo(self):
        """Valida que valores negativos de estoque são clampados para zero."""
        # Se produto ficar com estoque negativo (-5)
        # Simula distorção de inventário com saldo físico negativo
        self.produto_gamer.estoque = -5
        # Salva a alteração
        self.produto_gamer.save()

        # Calcula a cota disponível
        cota = self.anuncio_unitario.calcular_cota_disponivel()
        # Valida que o saldo foi clampado para 0, impedindo o envio de valores negativos ao canal
        self.assertEqual(cota, 0)

        # Simula o envio ao conector
        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_att:
            mock_att.return_value = (True, "OK", None)
            res = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(self.anuncio_unitario, forcar=True)
            # Valida conclusão da sincronização
            self.assertTrue(res['sucesso'])
            # Valida que o estoque sincronizado enviado foi exatamente 0
            self.assertEqual(res['estoque_sincronizado'], 0)
            # Confirma os argumentos passados ao conector
            mock_att.assert_called_with("MLB2001", 0, usuario=None)

    # Teste de acionamento do Circuit Breaker em variações atípicas de preço
    def test_circuit_breaker_variacao_anomala_preco(self):
        """Valida bloqueio de variações de preço > 50% para baixo ou > 100% para cima sem override."""
        # Preço atual: R$ 100.00. Tentativa de baixar para R$ 40.00 (queda de 60%)
        # Dispara redução de 60% no preço sem permissão forçada
        res_queda = AnuncioSincronizacaoService.sincronizar_preco_anuncio(
            self.anuncio_unitario, Decimal('40.00'), usuario=self.user_admin, forcar=False
        )
        # Valida que a operação foi rejeitada
        self.assertFalse(res_queda['sucesso'])
        # Confirma que a flag de bloqueio por Circuit Breaker veio ativada
        self.assertTrue(res_queda.get('bloqueado_circuit_breaker'))
        # Confirma o alerta de queda anômala na mensagem
        self.assertIn("Circuit Breaker acionado: Queda anômala", res_queda['mensagem'])
        # Recarrega o anúncio do banco
        self.anuncio_unitario.refresh_from_db()
        # Valida que o preço original de R$ 100.00 foi preservado intacto
        self.assertEqual(self.anuncio_unitario.preco_venda, Decimal('100.00'))

        # Confirma registro no LogAuditoria
        # Valida se o bloqueio do Circuit Breaker foi registrado na auditoria
        self.assertTrue(LogAuditoria.objects.filter(
            loja=self.loja,
            evento=EventoAuditoriaEnum.SYNC_PRECO,
            detalhes__contains="Circuit Breaker"
        ).exists())

        # Tentativa de aumento anômalo: de R$ 100.00 para R$ 250.00 (aumento de 150% > 100%)
        # Dispara aumento de 150% no preço sem aprovação forçada
        res_alta = AnuncioSincronizacaoService.sincronizar_preco_anuncio(
            self.anuncio_unitario, Decimal('250.00'), usuario=self.user_admin, forcar=False
        )
        # Valida que o aumento atípico também foi bloqueado
        self.assertFalse(res_alta['sucesso'])
        # Confirma a ativação da proteção
        self.assertTrue(res_alta.get('bloqueado_circuit_breaker'))
        # Valida a mensagem de aumento anômalo
        self.assertIn("Aumento anômalo", res_alta['mensagem'])

        # Com forcar=True, deve aprovar e sincronizar
        # Simula a aprovação manual de override pelo operador
        with patch.object(MercadoLivreConnector, 'atualizar_preco') as mock_prc:
            mock_prc.return_value = (True, "Preço atualizado", None)
            res_forcar = AnuncioSincronizacaoService.sincronizar_preco_anuncio(
                self.anuncio_unitario, Decimal('40.00'), usuario=self.user_admin, forcar=True
            )
            # Valida que o envio forçado foi autorizado
            self.assertTrue(res_forcar['sucesso'])
            # Recarrega o anúncio do banco
            self.anuncio_unitario.refresh_from_db()
            # Valida que o preço de venda foi devidamente atualizado no banco
            self.assertEqual(self.anuncio_unitario.preco_venda, Decimal('40.00'))

    # Validação do bloqueio do Circuit Breaker para zeramento massivo de estoque em lote
    def test_circuit_breaker_zeramento_lote(self):
        """Valida o bloqueio preventivo de operações massivas com risco de zeramento acidental."""
        # 6 de 10 anúncios zerando (> 5 e > 50%)
        # Submete cenário com 6 itens zerando em lote de 10 sem override forçado
        ok, msg = AnuncioSincronizacaoService.validar_zeramento_em_lote(10, 6, forcar=False)
        # Confirma que a operação foi bloqueada
        self.assertFalse(ok)
        # Confirma que o motivo reporta a tentativa de zeramento em massa
        self.assertIn("Circuit Breaker acionado: Tentativa de zeramento em massa", msg)

        # Com forcar=True, deve aprovar
        # Valida que a passagem do parâmetro forcar=True libera o zeramento em lote
        ok_forcado, _ = AnuncioSincronizacaoService.validar_zeramento_em_lote(10, 6, forcar=True)
        self.assertTrue(ok_forcado)

        # 2 de 10 anúncios zerando (dentro do limite aceitável)
        # Submete cenário normal com 2 itens zerando em 10 (abaixo dos patamares de alerta)
        ok_normal, _ = AnuncioSincronizacaoService.validar_zeramento_em_lote(10, 2, forcar=False)
        # Valida que operações dentro do limite são aprovadas sem necessidade de confirmação
        self.assertTrue(ok_normal)

    # Teste para verificar o desacoplamento de sinais: alteração física gera status PENDENTE sem disparar envio de rede silencioso
    def test_signals_produto_disparam_sincronizacao_anuncios(self):
        """Valida que salvar Produto com alteração de estoque marca anúncios vinculados como PENDENTE sem disparar chamadas externas silenciosas."""
        # Intercepta as chamadas externas de estoque
        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_sync_est:
            mock_sync_est.return_value = (True, "OK", None)

            # Define estado inicial sincronizado
            # Define o status dos anúncios como previamente enviados
            self.anuncio_unitario.status_sincronizacao = 'ENVIADO'
            self.anuncio_unitario.save()
            self.anuncio_kit.status_sincronizacao = 'ENVIADO'
            self.anuncio_kit.save()

            # Altera estoque do Headset de 20 para 2 (afeta cota unitária e do kit)
            # Simula edição manual de inventário pelo usuário
            self.produto_gamer.estoque = 2
            # Grava a alteração disparando o post_save do produto
            self.produto_gamer.save()

            # NÃO deve ter disparado chamadas externas à API do Mercado Livre (desacoplamento defensivo)
            # Garante que nenhuma chamada externa de sincronização foi disparada de forma silenciosa
            self.assertEqual(mock_sync_est.call_count, 0)

            # Deve marcar anúncios vinculados como PENDENTE para confirmação manual
            # Recarrega os anúncios do banco
            self.anuncio_unitario.refresh_from_db()
            self.anuncio_kit.refresh_from_db()
            # Valida que o anúncio unitário foi enfileirado com status PENDENTE
            self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'PENDENTE')
            # Valida que o kit dependente também entrou em estado PENDENTE
            self.assertEqual(self.anuncio_kit.status_sincronizacao, 'PENDENTE')

            # Confirma registro na trilha de histórico de ciclo
            # Importa o modelo de histórico para conferência do log
            from apps.anuncios.models import HistoricoSincronizacaoAnuncio
            # Confirma que foi gerado um histórico de auditoria registrando a pendência
            self.assertTrue(HistoricoSincronizacaoAnuncio.objects.filter(
                anuncio=self.anuncio_unitario, status_resultante='PENDENTE'
            ).exists())

    # Teste de reabertura automática de pendência para anúncios cancelados após nova alteração física
    def test_signals_reabrem_anuncios_cancelados_sob_divergencia_fisica(self):
        """Valida que anúncios marcados como CANCELADO têm seu status alterado para PENDENTE quando houver nova divergência física no Produto."""
        # Força o anúncio para o status CANCELADO (ignorado pelo operador)
        self.anuncio_unitario.status_sincronizacao = 'CANCELADO'
        self.anuncio_unitario.save()

        # Altera estoque físico gerando divergência na cota
        # Promove nova alteração física no catálogo
        self.produto_gamer.estoque = 5
        self.produto_gamer.save()

        # Recarrega o anúncio
        self.anuncio_unitario.refresh_from_db()
        # Valida que o anúncio antes cancelado foi reaberto com status PENDENTE devido à nova divergência
        self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'PENDENTE')

    # Teste para alternar a flag de ignorar/cancelar a sincronização de um anúncio
    def test_toggle_ignorar_anuncio_view(self):
        """Valida alternância entre status CANCELADO e reativação para PENDENTE/ENVIADO."""
        # Força o login com usuário administrador
        self.client.force_login(self.user_admin)
        # Obtém a rota do toggle de ignorar anúncio
        url = reverse('anuncio_toggle_ignorar', kwargs={'pk': self.anuncio_unitario.pk})

        # 1. Marca como CANCELADO
        # Envia requisição para alternar o status
        resp1 = self.client.post(url, HTTP_REFERER='/produtos/1/')
        # Confirma redirecionamento
        self.assertEqual(resp1.status_code, 302)
        # Recarrega o anúncio do banco
        self.anuncio_unitario.refresh_from_db()
        # Valida que o anúncio assumiu o estado CANCELADO
        self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'CANCELADO')

        # 2. Reativa a sincronização
        # Dispara a requisição novamente para reverter a ação
        resp2 = self.client.post(url, HTTP_REFERER='/produtos/1/')
        # Confirma redirecionamento
        self.assertEqual(resp2.status_code, 302)
        # Recarrega o anúncio
        self.anuncio_unitario.refresh_from_db()
        # Valida que o status retornou para um estado ativo de sincronização (PENDENTE ou ENVIADO)
        self.assertIn(self.anuncio_unitario.status_sincronizacao, ['PENDENTE', 'ENVIADO'])

    # Teste da view que efetua o envio manual e atualiza o status para ENVIADO
    def test_sincronizar_anuncio_view_atualiza_status_para_enviado(self):
        """Valida que sincronização manual via view atualiza status_sincronizacao para ENVIADO e grava histórico."""
        # Força autenticação de usuário administrador
        self.client.force_login(self.user_admin)
        # Obtém a rota da ação de sincronizar o anúncio
        url = reverse('anuncio_sincronizar', kwargs={'pk': self.anuncio_unitario.pk})
        # Define o estado inicial como PENDENTE
        self.anuncio_unitario.status_sincronizacao = 'PENDENTE'
        self.anuncio_unitario.save()

        # Simula as respostas do conector para atualização de estoque e preço
        with patch.object(MercadoLivreConnector, 'atualizar_estoque', return_value=(True, "OK", None)), \
             patch.object(MercadoLivreConnector, 'atualizar_preco', return_value=(True, "OK", None)):
            # Dispara a requisição POST via view
            resp = self.client.post(url, HTTP_REFERER='/produtos/1/')
            # Confirma redirecionamento da view
            self.assertEqual(resp.status_code, 302)
            # Recarrega o anúncio do banco
            self.anuncio_unitario.refresh_from_db()
            # Confirma que a sincronização manual alterou o status para ENVIADO
            self.assertEqual(self.anuncio_unitario.status_sincronizacao, 'ENVIADO')

            # Valida a gravação do registro correspondente no histórico do anúncio
            from apps.anuncios.models import HistoricoSincronizacaoAnuncio
            self.assertTrue(HistoricoSincronizacaoAnuncio.objects.filter(
                anuncio=self.anuncio_unitario, status_resultante='ENVIADO'
            ).exists())

    # Teste do mecanismo de idempotência para suprimir chamadas externas de valores idênticos
    def test_idempotencia_evita_requisicao_externa_redundante(self):
        """Valida que se o estoque calculado for idêntico ao já publicado, a chamada de rede é poupada."""
        # Iguala o estoque publicado ao saldo físico existente (20 unidades)
        self.anuncio_unitario.estoque_publicado = 20
        self.anuncio_unitario.save()

        # Intercepta o conector para verificar se foi efetuada chamada externa
        with patch.object(MercadoLivreConnector, 'atualizar_estoque') as mock_att:
            # Invoca o serviço sem forçar envio
            res = AnuncioSincronizacaoService.sincronizar_estoque_anuncio(self.anuncio_unitario, forcar=False)
            # Valida retorno de sucesso
            self.assertTrue(res['sucesso'])
            # Valida que o processamento acusou o benefício da idempotência
            self.assertTrue(res.get('ignorado_idempotencia'))
            # Confirma que nenhuma chamada externa de rede foi realizada
            self.assertEqual(mock_att.call_count, 0)

    # Teste de exclusão de componente intermediário de kit garantindo a integridade dos demais itens
    def test_exclusao_componente_intermediario_kit_3_itens_preserva_irmas(self):
        # Docstring detalhando o cenário com 3 produtos (A, B, C) e a remoção de B
        """
        Cenário 1: Kit com 3 componentes (A, B, C).
        Exclui o componente intermediário (B).
        Assertar que A e C continuam intactos no banco, com SKUs, quantidades e vínculos inalterados.
        Assertar que os produtos físicos continuam existindo.
        """
        # Força autenticação de usuário administrador
        self.client.force_login(self.user_admin)

        # Cria os produtos A, B e C no catálogo físico
        prod_a = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT3-A", nome="Produto A", preco=Decimal('10.00'), estoque=15)
        prod_b = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT3-B", nome="Produto B", preco=Decimal('20.00'), estoque=25)
        prod_c = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT3-C", nome="Produto C", preco=Decimal('30.00'), estoque=35)

        # Cria o anúncio do kit triplo
        anuncio_kit3 = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB-KIT3-01",
            titulo="Anúncio Kit Triplo ABC",
            preco_venda=Decimal('60.00'),
            estoque_publicado=10
        )
        # Vincula o componente A com quantidade 1
        comp_a = AnuncioComposicao.objects.create(anuncio=anuncio_kit3, produto=prod_a, quantidade=1)
        # Vincula o componente intermediário B com quantidade 2
        comp_b = AnuncioComposicao.objects.create(anuncio=anuncio_kit3, produto=prod_b, quantidade=2)
        # Vincula o componente C com quantidade 3
        comp_c = AnuncioComposicao.objects.create(anuncio=anuncio_kit3, produto=prod_c, quantidade=3)

        # Prepara a URL para exclusão do componente intermediário B
        url_delete = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio_kit3.pk, 'pk': comp_b.pk})
        # Executa a requisição de exclusão
        resp = self.client.post(url_delete)
        # Confirma redirecionamento após exclusão
        self.assertEqual(resp.status_code, 302)

        # B foi excluído da composição
        # Valida que o vínculo do componente B foi removido do banco
        self.assertFalse(AnuncioComposicao.objects.filter(pk=comp_b.pk).exists())

        # A e C continuam intactos na composição
        # Recarrega os registros dos componentes irmãos A e C
        comp_a.refresh_from_db()
        comp_c.refresh_from_db()
        # Valida a preservação da quantidade de A
        self.assertEqual(comp_a.quantidade, 1)
        # Valida que a referência ao produto A continua correta
        self.assertEqual(comp_a.produto, prod_a)
        # Valida a preservação da quantidade de C
        self.assertEqual(comp_c.quantidade, 3)
        # Valida que a referência ao produto C continua correta
        self.assertEqual(comp_c.produto, prod_c)

        # Produtos físicos originais permanecem intactos no catálogo
        # Confirma que a exclusão da ficha técnica não afetou os produtos físicos no catálogo
        self.assertTrue(Produto.objects.filter(pk=prod_a.pk).exists())
        self.assertTrue(Produto.objects.filter(pk=prod_b.pk).exists())
        self.assertTrue(Produto.objects.filter(pk=prod_c.pk).exists())

    # Teste de remoções sequenciais de itens da composição em requisições isoladas
    def test_exclusao_sequencial_componentes_kit_4_itens(self):
        # Docstring detalhando o cenário com 4 produtos e remoções graduais
        """
        Cenário 2: Kit com 4 componentes (A, B, C, D).
        Executa a remoção sequencial de dois componentes em requisições isoladas.
        Assertar a integridade referencial dos registros restantes após cada requisição.
        """
        # Força autenticação de usuário administrador
        self.client.force_login(self.user_admin)

        # Cria os 4 produtos que integrarão o kit quádruplo
        prod_a = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-A", nome="Item A", preco=Decimal('10.00'), estoque=10)
        prod_b = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-B", nome="Item B", preco=Decimal('10.00'), estoque=10)
        prod_c = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-C", nome="Item C", preco=Decimal('10.00'), estoque=10)
        prod_d = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="KIT4-D", nome="Item D", preco=Decimal('10.00'), estoque=10)

        # Cria o anúncio do kit quádruplo
        anuncio_kit4 = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB-KIT4-01",
            titulo="Anúncio Kit Quádruplo",
            preco_venda=Decimal('40.00'),
            estoque_publicado=5
        )
        # Cria os vínculos dos 4 produtos
        comp_a = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_a, quantidade=1)
        comp_b = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_b, quantidade=1)
        comp_c = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_c, quantidade=1)
        comp_d = AnuncioComposicao.objects.create(anuncio=anuncio_kit4, produto=prod_d, quantidade=1)

        # 1ª Requisição: Exclui B
        # Define a URL de exclusão para o componente B
        url_del_b = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio_kit4.pk, 'pk': comp_b.pk})
        # Executa a primeira remoção
        resp1 = self.client.post(url_del_b)
        # Confirma redirecionamento
        self.assertEqual(resp1.status_code, 302)

        # Valida integridade após 1ª exclusão (restam A, C, D)
        # Extrai os SKUs restantes vinculados à composição do anúncio
        restantes1 = list(anuncio_kit4.itens_composicao.values_list('produto__sku', flat=True))
        # Confirma a presença de exatamente 3 componentes
        self.assertEqual(len(restantes1), 3)
        # Valida se os itens remanescentes são precisamente A, C e D
        self.assertCountEqual(restantes1, ["KIT4-A", "KIT4-C", "KIT4-D"])

        # 2ª Requisição: Exclui C
        # Define a URL de exclusão para o componente C
        url_del_c = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio_kit4.pk, 'pk': comp_c.pk})
        # Executa a segunda remoção em requisição independente
        resp2 = self.client.post(url_del_c)
        # Confirma redirecionamento
        self.assertEqual(resp2.status_code, 302)

        # Valida integridade após 2ª exclusão (restam A, D)
        # Extrai novamente a listagem de SKUs vinculados
        restantes2 = list(anuncio_kit4.itens_composicao.values_list('produto__sku', flat=True))
        # Confirma que agora restam apenas 2 componentes
        self.assertEqual(len(restantes2), 2)
        # Valida se os itens remanescentes são exatamente A e D
        self.assertCountEqual(restantes2, ["KIT4-A", "KIT4-D"])

        # Todos os 4 produtos físicos permanecem íntegros no banco
        # Confirma que os 4 registros físicos do catálogo continuam persistidos no banco
        self.assertEqual(Produto.objects.filter(sku__in=["KIT4-A", "KIT4-B", "KIT4-C", "KIT4-D"]).count(), 4)

    # Validação do preenchimento dos snapshots JSON antes e depois da exclusão de um item da ficha técnica
    def test_validacao_snapshots_auditoria_exclusao_composicao(self):
        # Docstring detalhando a asserção de snapshots de auditoria estruturados
        """
        Cenário 3: Validação de Snapshots de Auditoria.
        Assertar que, ao excluir um item, o registro criado em HistoricoSincronizacaoAnuncio
        grava fielmente a lista completa prévia em snapshot_antes e a lista restante exata em snapshot_depois.
        """
        # Força autenticação de usuário administrador
        self.client.force_login(self.user_admin)

        # Cria dois produtos no catálogo
        prod1 = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="SNAP-01", nome="Item 1", preco=Decimal('15.00'), estoque=20)
        prod2 = Produto.objects.create(loja=self.loja, categoria=self.categoria, sku="SNAP-02", nome="Item 2", preco=Decimal('25.00'), estoque=30)

        # Cria o anúncio para teste de auditoria
        anuncio = Anuncio.objects.create(
            conta=self.conta_meli,
            item_id_externo="MLB-SNAP-TEST",
            titulo="Anúncio Teste Snapshots",
            preco_venda=Decimal('40.00'),
            estoque_publicado=20
        )
        # Cria o componente 1 com quantidade 1
        comp1 = AnuncioComposicao.objects.create(anuncio=anuncio, produto=prod1, quantidade=1)
        # Cria o componente 2 com quantidade 2
        comp2 = AnuncioComposicao.objects.create(anuncio=anuncio, produto=prod2, quantidade=2)

        # Importa a entidade de histórico para auditar a criação de snapshots
        from apps.anuncios.models import HistoricoSincronizacaoAnuncio
        # Coleta o volume de históricos antes da exclusão
        hist_count_antes = HistoricoSincronizacaoAnuncio.objects.filter(anuncio=anuncio).count()

        # Dispara exclusão do comp1
        # Obtém a rota de remoção para o componente 1
        url_del = reverse('anuncio_composicao_delete', kwargs={'anuncio_id': anuncio.pk, 'pk': comp1.pk})
        # Executa a requisição de exclusão
        resp = self.client.post(url_del)
        # Valida redirecionamento
        self.assertEqual(resp.status_code, 302)

        # Valida que um novo registro de histórico foi criado com os snapshots
        # Obtém o registro de histórico mais recente criado para o anúncio
        hist = HistoricoSincronizacaoAnuncio.objects.filter(anuncio=anuncio).order_by('-criado_em').first()
        # Valida que o registro de histórico foi gerado
        self.assertIsNotNone(hist)
        # Confirma o incremento de 1 registro na contagem total de históricos do anúncio
        self.assertEqual(HistoricoSincronizacaoAnuncio.objects.filter(anuncio=anuncio).count(), hist_count_antes + 1)

        # Validação do snapshot_antes (deve conter comp1 e comp2)
        # Extrai os SKUs contidos no snapshot anterior à operação
        skus_antes = [item['sku'] for item in hist.snapshot_antes]
        # Valida que a lista do snapshot_antes continha exatamente 2 itens
        self.assertEqual(len(hist.snapshot_antes), 2)
        # Confirma presença do item 1
        self.assertIn("SNAP-01", skus_antes)
        # Confirma presença do item 2
        self.assertIn("SNAP-02", skus_antes)

        # Validação do snapshot_depois (deve conter apenas comp2)
        # Extrai os SKUs contidos no snapshot posterior à operação
        skus_depois = [item['sku'] for item in hist.snapshot_depois]
        # Valida que a lista do snapshot_depois agora contém apenas 1 item
        self.assertEqual(len(hist.snapshot_depois), 1)
        # Confirma que o item 1 foi devidamente removido do snapshot posterior
        self.assertNotIn("SNAP-01", skus_depois)
        # Confirma que o item 2 permaneceu registrado
        self.assertIn("SNAP-02", skus_depois)
        # Valida que o SKU do item restante é 'SNAP-02'
        self.assertEqual(hist.snapshot_depois[0]['sku'], "SNAP-02")
        # Valida que o fator de quantidade 2 do item restante foi preservado no payload JSON
        self.assertEqual(hist.snapshot_depois[0]['quantidade'], 2)


# Classe de testes para criação manual e gestão de composições comerciais via formulários e formsets
class AnuncioCriacaoManualEComposicaoTestCase(TestCase):
    # Docstring documentando a validação de regras de kits, unicidade e isolamento multi-tenant
    """
    O QUE FAZ: Testes automatizados para criação e edição manual de anúncios e composições comerciais (ADR-003, ADR-009).
    POR QUE FAZ: Valida criação de combos heterogêneos, recálculo dinâmico de cota gargalo, rejeição de duplicidades,
                 isolamento multi-tenant estrito e autorização RBAC.
    """
    # Prepara o fixture com duas lojas distintas para testes de isolamento multi-tenant
    def setUp(self):
        # Instancia o cliente de requisições HTTP
        self.client = Client()

        # Cria a primeira loja (Loja A)
        self.loja = Loja.objects.create(nome="Loja A", slug="loja-a", cnpj="11.111.111/0001-11")
        self.loja.garantir_modulos_padrao()

        # Cria a segunda loja (Loja B) para validação de invasão de dados entre tenants
        self.loja_b = Loja.objects.create(nome="Loja B", slug="loja-b", cnpj="22.222.222/0001-22")
        self.loja_b.garantir_modulos_padrao()

        # Cria usuário administrador da Loja A
        self.user_admin = User.objects.create_user(username='admin_a', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        # Cria usuário padrão de operação da Loja A
        self.user_padrao = User.objects.create_user(username='operador_a', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

        # Cria usuário com perfil de desenvolvedor (DEV) sem loja específica associada
        self.user_dev = User.objects.create_user(username='dev_master', password='password123')
        PerfilUsuario.objects.create(usuario=self.user_dev, papel=PapelUsuarioEnum.DEV)

        # Cria categoria de produtos para a Loja A
        self.categoria = Categoria.objects.create(loja=self.loja, nome="Hardware", slug="hardware")
        # Cria categoria de produtos para a Loja B
        self.categoria_b = Categoria.objects.create(loja=self.loja_b, nome="Hardware B", slug="hardware-b")

        # Cria produto Alpha pertencente à Loja A com 10 unidades em estoque
        self.produto_a = Produto.objects.create(
            loja=self.loja, categoria=self.categoria, sku="PROD-A", nome="Produto Alpha",
            preco=Decimal('100.00'), estoque=10
        )
        # Cria produto Beta pertencente à Loja A com 12 unidades em estoque
        self.produto_b = Produto.objects.create(
            loja=self.loja, categoria=self.categoria, sku="PROD-B", nome="Produto Beta",
            preco=Decimal('50.00'), estoque=12
        )
        # Cria produto pertencente à Loja B para simulação de violação de tenant
        self.produto_loja_b = Produto.objects.create(
            loja=self.loja_b, categoria=self.categoria_b, sku="PROD-OUTRA-LOJA", nome="Produto Outra Loja",
            preco=Decimal('30.00'), estoque=50
        )

        # Cria a conta de integração do Mercado Livre vinculada à Loja A
        self.conta = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Loja A",
            seller_id_externo="12345"
        )

    # Teste de criação manual de anúncio com múltiplos componentes heterogêneos calculando cota gargalo
    def test_criacao_manual_anuncio_combo_multiproduto(self):
        """Valida a criação manual de anúncio com 2 produtos heterogêneos (Combo) e cálculo da cota gargalo."""
        # Força autenticação de usuário administrador
        self.client.force_login(self.user_admin)
        # Obtém a rota de criação manual de anúncio
        url = reverse('anuncio_create')

        # Monta os dados do payload de submissão do formulário e do formset inline de composição
        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-COMBO-99',
            'titulo': 'Combo Teclado + Mouse Gamer',
            'sku_vendedor': 'COMBO-GAMER',
            'preco_venda': '149.90',
            'status': 'active',
            # Inline formset (prefix 'itens_composicao')
            'itens_composicao-TOTAL_FORMS': '2',
            'itens_composicao-INITIAL_FORMS': '0',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            # Item 0: Produto A x 2 (10 // 2 = 5)
            'itens_composicao-0-produto': self.produto_a.pk,
            'itens_composicao-0-quantidade': '2',
            # Item 1: Produto B x 3 (12 // 3 = 4 -> gargalo!)
            'itens_composicao-1-produto': self.produto_b.pk,
            'itens_composicao-1-quantidade': '3',
        }

        # Submete o formulário com o formset
        resp = self.client.post(url, post_data)
        # Confirma redirecionamento indicando criação bem-sucedida
        self.assertEqual(resp.status_code, 302)

        # Localiza o anúncio recém-criado no banco de dados
        anuncio = Anuncio.objects.filter(item_id_externo='MLB-COMBO-99').first()
        # Valida que o anúncio foi criado
        self.assertIsNotNone(anuncio)
        # Confirma que possui 2 componentes cadastrados na composição
        self.assertEqual(anuncio.itens_composicao.count(), 2)
        # Valida a tipologia arquitetural classificada como Combo Multi-Produto
        self.assertEqual(anuncio.tipo_composicao, "Combo Multi-Produto")
        # Valida o texto exibido no badge visual
        self.assertEqual(anuncio.tipo_composicao_badge['label'], "Combo Multi-Produto")
        # Gargalo min(10//2, 12//3) = min(5, 4) = 4
        # Valida o cálculo da cota gargalo entre 10//2=5 e 12//3=4, resultando em 4
        self.assertEqual(anuncio.calcular_cota_disponivel(), 4)
        # Valida que o campo estoque_publicado recebeu a cota calculada na criação
        self.assertEqual(anuncio.estoque_publicado, 4)

    # Teste de validação para impedir repetição do mesmo produto em mais de uma linha da composição
    def test_validacao_rejeicao_produtos_duplicados(self):
        """Valida que o formset rejeita o mesmo produto selecionado mais de uma vez."""
        # Força autenticação de usuário administrador
        self.client.force_login(self.user_admin)
        url = reverse('anuncio_create')

        # Monta o payload repetindo intencionalmente o produto_a nas linhas 0 e 1 do formset
        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-DUP-01',
            'titulo': 'Anúncio com Duplicidade',
            'preco_venda': '100.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '2',
            'itens_composicao-INITIAL_FORMS': '0',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            # Linha 0 e 1 usam o mesmo produto_a
            'itens_composicao-0-produto': self.produto_a.pk,
            'itens_composicao-0-quantidade': '1',
            'itens_composicao-1-produto': self.produto_a.pk,
            'itens_composicao-1-quantidade': '2',
        }

        # Submete a criação inválida
        resp = self.client.post(url, post_data)
        # Confirma que a view retornou HTTP 200 re-renderizando a página com os erros de validação
        self.assertEqual(resp.status_code, 200)
        # Valida a presença da mensagem de erro de duplicidade no HTML retornado
        self.assertTrue(
            "adicionado mais de uma vez" in resp.content.decode('utf-8') or
            "duplicado" in resp.content.decode('utf-8')
        )
        # Garante que nenhum anúncio duplicado inconsistente foi persistido no banco
        self.assertFalse(Anuncio.objects.filter(item_id_externo='MLB-DUP-01').exists())

    # Teste de barreira multi-tenant: rejeição de produtos pertencentes a outra loja
    def test_validacao_rejeicao_produto_outra_loja_multi_tenant(self):
        """Valida que produto de outra loja não é aceito no formset (ADR-003)."""
        # Força login do administrador da Loja A
        self.client.force_login(self.user_admin)
        url = reverse('anuncio_create')

        # Tenta vincular um produto pertencente à Loja B em um anúncio da Loja A
        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-CROSS-TENANT',
            'titulo': 'Anúncio Cross Tenant Tentativa',
            'preco_venda': '100.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '1',
            'itens_composicao-INITIAL_FORMS': '0',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            'itens_composicao-0-produto': self.produto_loja_b.pk,
            'itens_composicao-0-quantidade': '1',
        }

        # Submete a criação
        resp = self.client.post(url, post_data)
        # O formulário rejeita porque o produto_loja_b não pertence ao queryset filtrado pela loja
        # Confirma que o formulário rejeita a opção inválida reapresentando a tela
        self.assertEqual(resp.status_code, 200)
        # Confirma que o anúncio ilegítimo não foi gravado
        self.assertFalse(Anuncio.objects.filter(item_id_externo='MLB-CROSS-TENANT').exists())

    # Teste de edição manual de anúncio com recálculo automático da cota vendável
    def test_edicao_anuncio_recalculo_cota(self):
        """Valida atualização do anúncio e recálculo da cota dinâmica via AnuncioUpdateView."""
        # Força autenticação de usuário administrador
        self.client.force_login(self.user_admin)

        # Cria um anúncio inicial com 1 unidade do produto A (estoque 10)
        anuncio = Anuncio.objects.create(
            conta=self.conta,
            item_id_externo='MLB-EDIT-01',
            titulo='Anúncio para Edição',
            preco_venda=Decimal('100.00'),
            estoque_publicado=10
        )
        comp_a = AnuncioComposicao.objects.create(anuncio=anuncio, produto=self.produto_a, quantidade=1)

        # Obtém a rota de edição do anúncio
        url = reverse('anuncio_update', kwargs={'pk': anuncio.pk})

        # Altera multiplicador do produto A de 1 para 5 (10 // 5 = 2)
        # Submete alteração aumentando a quantidade exigida por pacote de 1 para 5
        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-EDIT-01',
            'titulo': 'Anúncio Editado com Sucesso',
            'preco_venda': '120.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '1',
            'itens_composicao-INITIAL_FORMS': '1',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            'itens_composicao-0-id': comp_a.pk,
            'itens_composicao-0-produto': self.produto_a.pk,
            'itens_composicao-0-quantidade': '5',
        }

        # Envia a requisição POST de atualização
        resp = self.client.post(url, post_data)
        # Confirma redirecionamento com sucesso
        self.assertEqual(resp.status_code, 302)

        # Recarrega o anúncio do banco
        anuncio.refresh_from_db()
        # Valida que o título foi editado
        self.assertEqual(anuncio.titulo, 'Anúncio Editado com Sucesso')
        # Valida que o novo preço de R$ 120.00 foi persistido
        self.assertEqual(anuncio.preco_venda, Decimal('120.00'))
        # Valida que a cota disponível foi recalculada para 2 (10 // 5 = 2)
        self.assertEqual(anuncio.calcular_cota_disponivel(), 2)
        # Valida que o estoque publicado foi ajustado para 2
        self.assertEqual(anuncio.estoque_publicado, 2)
        # Valida que a composição passou a ser tipificada como 'Kit Homogêneo' (1 produto com multiplicador > 1)
        self.assertEqual(anuncio.tipo_composicao, "Kit Homogêneo")

    # Teste para garantir bloqueio HTTP 403 para operadores comuns em ações de escrita/edição
    def test_rbac_usuario_padrao_bloqueado(self):
        """Valida que perfil USUARIO recebe 403 ao tentar criar ou editar anúncios."""
        # Força autenticação de usuário padrão (sem permissão de escrita)
        self.client.force_login(self.user_padrao)

        # Cria um anúncio prévio na base
        anuncio = Anuncio.objects.create(
            conta=self.conta,
            item_id_externo='MLB-RBAC-01',
            titulo='Anúncio RBAC',
            preco_venda=Decimal('10.00'),
            estoque_publicado=5
        )

        # Tenta acessar a página de criação de anúncio
        resp_create = self.client.get(reverse('anuncio_create'))
        # Confirma bloqueio com status HTTP 403 Forbidden
        self.assertEqual(resp_create.status_code, 403)

        # Tenta acessar a página de edição de anúncio
        resp_update = self.client.get(reverse('anuncio_update', kwargs={'pk': anuncio.pk}))
        # Confirma bloqueio com status HTTP 403 Forbidden
        self.assertEqual(resp_update.status_code, 403)

    # Teste de isolamento multi-tenant estrito mesmo quando acessado com credencial com papel de DEV
    def test_dev_restringido_estritamente_produtos_da_loja_do_anuncio(self):
        # Docstring detalhando a imunidade do isolamento comercial contra privilégios globais de desenvolvedor
        """
        Valida que, mesmo acessando com usuário DEV, o anúncio e o formset são
        restringidos unicamente aos produtos pertencentes à loja em questão.
        """
        # Força login do usuário com papel global de desenvolvedor (DEV)
        self.client.force_login(self.user_dev)

        # Cria anúncio vinculado à conta da Loja A
        anuncio = Anuncio.objects.create(
            conta=self.conta,
            item_id_externo='MLB-DEV-RESTRICT',
            titulo='Anúncio Teste DEV',
            preco_venda=Decimal('150.00'),
            estoque_publicado=10
        )
        # Adiciona o componente da Loja A
        AnuncioComposicao.objects.create(anuncio=anuncio, produto=self.produto_a, quantidade=1)

        # 1. GET no AnuncioUpdateView: o dropdown deve conter apenas produtos da Loja A
        # Requisita a tela de edição do anúncio
        url_edit = reverse('anuncio_update', kwargs={'pk': anuncio.pk})
        resp = self.client.get(url_edit)
        # Confirma o carregamento da tela
        self.assertEqual(resp.status_code, 200)

        # Recupera o formset a partir do contexto da view
        formset = resp.context['formset']
        # Extrai o queryset do campo produto na primeira linha do formset
        form_prod_qs = formset.forms[0].fields['produto'].queryset
        # Deve conter produto_a (Loja A), e NÃO pode conter produto_loja_b (Loja B)
        # Valida que o produto da Loja A está disponível para seleção
        self.assertIn(self.produto_a, form_prod_qs)
        # Valida que o produto da Loja B foi isolado e não aparece no queryset
        self.assertNotIn(self.produto_loja_b, form_prod_qs)
        # Valida a presença do SKU do produto legítimo no HTML
        self.assertContains(resp, "PROD-A")
        # Confirma que o SKU de produto de outra loja não é renderizado
        self.assertNotContains(resp, "PROD-OUTRA-LOJA")

        # 2. POST com produto da Loja B pelo DEV deve ser rejeitado
        # Tenta injetar manualmente o produto da Loja B na composição
        post_data = {
            'conta': self.conta.pk,
            'item_id_externo': 'MLB-DEV-RESTRICT',
            'titulo': 'Tentativa DEV Cross-Tenant',
            'preco_venda': '150.00',
            'status': 'active',
            'itens_composicao-TOTAL_FORMS': '1',
            'itens_composicao-INITIAL_FORMS': '1',
            'itens_composicao-MIN_NUM_FORMS': '0',
            'itens_composicao-MAX_NUM_FORMS': '1000',
            'itens_composicao-0-produto': self.produto_loja_b.pk,
            'itens_composicao-0-quantidade': '1',
        }
        # Submete a requisição POST
        resp_post = self.client.post(url_edit, post_data)
        # Confirma que a alteração não redirecionou, retornando a página com validação ativa
        self.assertEqual(resp_post.status_code, 200)
        # Formset deve conter erro e rejeitar o salvamento
        # Valida que o formset apontou erro de validação multi-tenant, bloqueando o salvamento indevido
        self.assertTrue(bool(resp_post.context['formset'].errors))


