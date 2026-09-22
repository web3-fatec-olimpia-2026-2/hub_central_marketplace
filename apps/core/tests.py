# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o propósito da suíte de testes de estresse, concorrência e RBAC
"""
Suíte de Testes Automatizados para o Laboratório de Testes de Concorrência e Resiliência.
Valida:
1. Controle de Acesso Estrito RBAC: Exclusivo para perfil DEV (403 para ADMIN/SUPERVISOR/USUARIO).
2. Teste 1 (Estoque): Lock Pessimista com 3 requisições simultâneas, medição de trava (0 a 10.000 ms)
   e gravação de auditoria em HistoricoPreco com carimbos dia/mês/ano - hh:mm:ss.SSS.
3. Teste 2 (OAuth): Lock Pessimista e Double-Checked Locking com 3 requisições simultâneas.
4. Validação de parâmetros (quantidades obrigatórias e limite de 0 a 10.000 ms).
"""
# Fim do bloco de documentação da suíte de testes

# Importa o módulo nativo json para serialização e desserialização de payloads de requisições AJAX
import json

# Importa o módulo nativo re para validação de padrões textuais através de expressões regulares
import re

# Importa a classe Decimal para manipulação precisa de moeda sem discrepâncias de ponto flutuante
from decimal import Decimal

# Importa TransactionTestCase (que permite commits reais necessários para threads) e Client HTTP do Django
from django.test import TransactionTestCase, Client

# Importa o modelo User padrão do Django para autenticação de operadores e administradores nos testes
from django.contrib.auth.models import User

# Importa o utilitário reverse para resolução dinâmica de rotas nomeadas
from django.urls import reverse

# Importa o utilitário timezone para manipulação de datas cientes de fuso horário
from django.utils import timezone

# Importa os modelos de Loja (tenant) e Perfil de Usuário da aplicação tenancy
from apps.tenancy.models import Loja, PerfilUsuario

# Importa o enum que define os papéis de controle de acesso (DEV, ADMIN, SUPERVISOR, USUARIO)
from apps.tenancy.enums import PapelUsuarioEnum

# Importa os modelos de Categoria, Produto e Histórico de Preço/Estoque da aplicação catalogo
from apps.catalogo.models import Categoria, Produto, HistoricoPreco

# Importa a enumeração de status do ciclo de vida dos produtos
from apps.catalogo.enums import StatusProdutoEnum

# Importa o modelo de credenciais de contas integradas aos marketplaces
from apps.marketplaces.models import ContaMarketplace

# Importa o enum com as constantes de canais parceiros (Mercado Livre, etc.)
from apps.marketplaces.enums import CanalMarketplaceEnum

# Importa os serviços de orquestração de testes de concorrência e o formatador estrito de timestamps
from .services_testes import (
    ConcorrenciaEstoqueTestService,
    ConcorrenciaOAuthTestService,
    formatar_timestamp_ms,
)


# Declaração da classe de testes herdando de TransactionTestCase para suportar concorrência real entre conexões de banco
class ConcorrenciaLaboratorioTestesCase(TransactionTestCase):
    # Início do bloco de docstring documentando os cenários de concorrência multithread da classe
    """
    Testes de integração, permissão RBAC e serviços de concorrência com 3 requisições simultâneas.
    """
    # Fim da docstring explicativa da classe

    # Método de preparação do ambiente executado antes de cada teste unitário
    def setUp(self):
        # Instancia o cliente simulador de requisições HTTP
        self.client = Client()

        # Loja Tenant
        # Cria a organização/loja que servirá de tenant para os testes de estresse
        self.loja = Loja.objects.create(
            nome="Loja Laboratório Concorrência",
            slug="loja-lab-concorrencia",
            cnpj="11.222.333/0001-44"
        )

        # Usuário DEV (Permissão Concedida)
        # Cria o usuário com privilégio de desenvolvedor para acesso ao laboratório de concorrência
        self.user_dev = User.objects.create_user(
            username="dev_concorrencia",
            email="dev@hub.local",
            password="testpassword123"
        )
        # Associa o perfil com papel DEV ao usuário e vincula à loja
        self.perfil_dev = PerfilUsuario.objects.create(
            usuario=self.user_dev,
            papel=PapelUsuarioEnum.DEV,
            loja=self.loja
        )

        # Usuário ADMIN (Acesso Bloqueado pelo RBAC DEV-only)
        # Cria usuário administrador comum para validar o bloqueio estrito da ferramenta de testes
        self.user_admin = User.objects.create_user(
            username="admin_loja",
            email="admin@hub.local",
            password="testpassword123"
        )
        # Associa o perfil com papel ADMIN vinculado à loja
        self.perfil_admin = PerfilUsuario.objects.create(
            usuario=self.user_admin,
            papel=PapelUsuarioEnum.ADMIN,
            loja=self.loja
        )

        # Categoria e Produto
        # Cria uma categoria de informática vinculada à loja
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Informática",
            slug="informatica"
        )
        # Cria o produto físico de teste com 50 unidades de saldo inicial em estoque
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="SSD NVMe 1TB High Speed",
            sku="SSD-NVME-1TB",
            preco=Decimal('350.00'),
            estoque=50,
            status=StatusProdutoEnum.ATIVO
        )

        # Conta Marketplace
        # Cria a conta de integração em modo mock com token expirado para simulação concorrente de OAuth
        self.conta = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="Mercado Livre Lab Test",
            seller_id_externo="987654321",
            ativo=True,
            is_mock=True,
            access_token="INITIAL_TOKEN",
            refresh_token="INITIAL_REFRESH",
            token_expira_em=timezone.now()
        )

        # URLs das views dedicadas
        # Resolve dinamicamente as rotas do laboratório de testes
        self.url_dashboard = reverse('testes_dashboard')
        self.url_estoque = reverse('teste_concorrencia_estoque')
        self.url_oauth = reverse('teste_concorrencia_oauth')

    # =========================================================================
    # TESTES DE RBAC (ESTRITAMENTE DEV-ONLY)
    # =========================================================================

    # Valida que visitantes anônimos não autenticados são impedidos e redirecionados para login
    def test_acesso_anonimo_redireciona_login(self):
        """Usuário não autenticado deve ser redirecionado para a página de login em todas as rotas."""
        # Itera por todas as rotas do laboratório de testes
        for url in [self.url_dashboard, self.url_estoque, self.url_oauth]:
            # Executa a requisição GET sem estar autenticado
            response = self.client.get(url)
            # Valida redirecionamento com código HTTP 302 Found
            self.assertEqual(response.status_code, 302)
            # Valida se o destino do redirecionamento aponta para a página de login
            self.assertIn('/auth/login/', response.url)

    # Valida a barreira estrita de RBAC que bloqueia operadores comuns e administradores
    def test_usuario_nao_dev_recebe_403_forbidden(self):
        """Usuário com papel ADMIN (não-DEV) deve receber 403 Forbidden ao tentar acessar os testes."""
        # Autentica o cliente com o perfil ADMIN
        self.client.login(username="admin_loja", password="testpassword123")
        # Itera pelas três rotas administrativas do laboratório
        for url in [self.url_dashboard, self.url_estoque, self.url_oauth]:
            # Requisita a página protegida
            response = self.client.get(url)
            # Valida bloqueio de segurança retornando código HTTP 403 Forbidden
            self.assertEqual(response.status_code, 403)

    # Valida que usuários com papel DEV possuem acesso autorizado às views do laboratório
    def test_usuario_dev_acessa_com_sucesso(self):
        """Usuário com papel DEV deve acessar o dashboard e ambas as views com status 200."""
        # Autentica com o usuário DEV
        self.client.login(username="dev_concorrencia", password="testpassword123")

        # Hub intermediário
        # Requisita a tela inicial de dashboard dos testes
        res_dash = self.client.get(self.url_dashboard)
        # Confirma resposta HTTP 200 OK
        self.assertEqual(res_dash.status_code, 200)
        # Valida se o template correto do dashboard foi utilizado
        self.assertTemplateUsed(res_dash, 'testes/dashboard.html')
        # Valida a presença dos cards das duas baterias de testes
        self.assertContains(res_dash, "Baixa Concorrente de Saldo Físico")
        self.assertContains(res_dash, "Renovação Concorrente de Token OAuth")

        # Teste 1 (Estoque)
        # Requisita a tela do laboratório de concorrência de estoque
        res_est = self.client.get(self.url_estoque)
        self.assertEqual(res_est.status_code, 200)
        self.assertTemplateUsed(res_est, 'testes/concorrencia_estoque.html')
        # Confirma que o produto cadastrado no setup aparece no menu de seleção
        self.assertContains(res_est, "SSD NVMe 1TB High Speed")

        # Teste 2 (OAuth)
        # Requisita a tela do laboratório de renovação concorrente de OAuth
        res_oau = self.client.get(self.url_oauth)
        self.assertEqual(res_oau.status_code, 200)
        self.assertTemplateUsed(res_oau, 'testes/concorrencia_oauth.html')
        # Confirma que a conta cadastrada no setup aparece na interface
        self.assertContains(res_oau, "Mercado Livre Lab Test")

    # =========================================================================
    # VALIDAÇÃO DE FORMATO DE TIMESTAMPS E PARÂMETROS
    # =========================================================================

    # Valida se a função utilitária de timestamp gera o padrão com milissegundos
    def test_formatar_timestamp_ms_padrao_estrito(self):
        """Valida que formatar_timestamp_ms gera estritamente DD/MM/YYYY - HH:MM:SS.SSS."""
        # Obtém a data/hora corrente ciente de fuso
        agora = timezone.now()
        # Formata o timestamp com a função utilitária
        ts_str = formatar_timestamp_ms(agora)
        # Define a expressão regular para validar exatamente dia/mês/ano - hora:minuto:segundo.milissegundo
        padrao = r'^\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3}$'
        # Asserta conformidade estrita da string gerada contra a regex
        self.assertRegex(ts_str, padrao)

    # Valida as barreiras numéricas permitidas para retenção forçada da trava
    def test_validacao_tempo_trava_ms_limites(self):
        """Valida a restrição estrita de 0 a 10.000 ms."""
        # Valida limites válidos (mínimo, intermediário e máximo de 10 segundos)
        self.assertEqual(ConcorrenciaEstoqueTestService.validar_tempo_trava(0), 0)
        self.assertEqual(ConcorrenciaEstoqueTestService.validar_tempo_trava(500), 500)
        self.assertEqual(ConcorrenciaEstoqueTestService.validar_tempo_trava(10000), 10000)

        # Valida que valores negativos disparam exceção ValueError
        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.validar_tempo_trava(-1)

        # Valida que valores superiores a 10.000 ms disparam exceção ValueError
        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.validar_tempo_trava(10001)

        # Valida que entradas não numéricas disparam exceção ValueError
        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.validar_tempo_trava("invalido")

    # Valida a obrigatoriedade de 3 quantidades estritamente positivas no teste de baixa
    def test_validacao_tres_quantidades_obrigatorias(self):
        """As três quantidades de requisição devem ser > 0."""
        # Asserta que quantidade zero na terceira requisição é rejeitada com ValueError
        with self.assertRaises(ValueError):
            ConcorrenciaEstoqueTestService.executar_teste(
                produto_id=self.produto.id,
                qtd1=1,
                qtd2=2,
                qtd3=0
            )

    # =========================================================================
    # EXECUÇÃO DO TESTE 1: ESTOQUE E AUDITORIA EM HISTORICOPRECO
    # =========================================================================

    # Teste de integração que dispara 3 threads de dedução concorrente e afere telemetria e auditoria
    def test_servico_estoque_executa_e_grava_auditoria_no_historico(self):
        """
        Valida que a execução de 3 requisições simultâneas:
        1. Deduz o estoque corretamente sem Lost Updates.
        2. Registra cada uma das 3 baixas em HistoricoPreco com carimbos formatados.
        3. Registra os carimbos de início, lock e término.
        """
        # Salva o estoque inicial (50 unidades)
        saldo_inicial = self.produto.estoque
        # Define as quantidades a deduzir em cada uma das três requisições
        qtd1, qtd2, qtd3 = 2, 3, 5
        # Total acumulado a ser subtraído (2 + 3 + 5 = 10)
        total = qtd1 + qtd2 + qtd3

        # Executa o teste de concorrência com Lock Pessimista via serviço
        resultado = ConcorrenciaEstoqueTestService.executar_teste(
            produto_id=self.produto.id,
            qtd1=qtd1,
            qtd2=qtd2,
            qtd3=qtd3,
            tempo_trava_ms=10,
            user=self.user_dev
        )

        # Valida que o serviço retornou sucesso
        self.assertTrue(resultado['sucesso'])
        # Confirma saldo inicial reportado
        self.assertEqual(resultado['saldo_inicial'], saldo_inicial)
        # Confirma total deduzido
        self.assertEqual(resultado['total_deduzido'], total)
        # Confirma saldo final matemático (50 - 10 = 40)
        self.assertEqual(resultado['saldo_final'], saldo_inicial - total)
        # Confirma a flag de consistência matemática
        self.assertTrue(resultado['consistente'])

        # Verifica se o produto no banco foi atualizado
        # Recarrega o produto do banco para atestar a persistência real
        self.produto.refresh_from_db()
        # Valida se o estoque persistido no banco é exatamente 40
        self.assertEqual(self.produto.estoque, saldo_inicial - total)

        # Verifica gravação no log do produto (HistoricoPreco)
        # Consulta os registros de histórico de estoque gerados para o produto
        historicos = HistoricoPreco.objects.filter(produto=self.produto).order_by('-criado_em')
        # Valida que foram gerados exatamente 3 registros de auditoria (um por requisição)
        self.assertEqual(historicos.count(), 3)

        # Define a regex esperada para o campo motivo contendo os 3 timestamps com milissegundos
        padrao_motivo = r'Baixa Concorrente Lock Pessimista - Req \d+ \(baixa de \d+ un\.\) \[Início: \d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3} \| Lock: \d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3} \| Fim: \d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3}\]'
        # Itera por cada registro de histórico gerado
        for h in historicos:
            # Confirma que o autor da operação foi o usuário DEV executor
            self.assertEqual(h.usuario, self.user_dev)
            # Valida se a mensagem de justificativa/motivo contém os carimbos formatados estritamente
            self.assertRegex(h.motivo, padrao_motivo)

    # =========================================================================
    # EXECUÇÃO DO TESTE 2: OAUTH E DOUBLE-CHECKED LOCKING
    # =========================================================================

    # Teste de validação do padrão Double-Checked Locking para renovação de credenciais com 3 requisições
    def test_servico_oauth_tres_requisicoes_double_checked(self):
        """
        Valida que 3 requisições concorrentes de renovação de token:
        1. Apenas 1 executa chamada externa real.
        2. As outras 2 reaproveitam o token gerado.
        3. Retornam carimbos formatados de início, lock e liberação.
        """
        # Dispara o teste concorrente de renovação sobre a conta de marketplace
        resultado = ConcorrenciaOAuthTestService.executar_teste(
            conta_id=self.conta.id,
            tempo_trava_ms=10,
            user=self.user_dev
        )

        # Confirma que a rotina finalizou com sucesso
        self.assertTrue(resultado['sucesso'])
        # Valida que apenas 1 chamada remota real foi realizada
        self.assertEqual(resultado['total_chamadas_api'], 1)
        # Valida que as outras 2 requisições reaproveitaram a credencial sem nova chamada externa
        self.assertEqual(resultado['total_reaproveitadas'], 2)
        # Confirma que houve medição de tempo de retenção da trava
        self.assertGreater(resultado['tempo_total_bloqueio_tabela_ms'], 0)

        # Verifica carimbos formatados
        # Valida o padrão estrito de data/hora nos carimbos consolidados de telemetria
        padrao = r'^\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}\.\d{3}$'
        self.assertRegex(resultado['tempo_inicio_formatado'], padrao)
        self.assertRegex(resultado['tempo_fim_formatado'], padrao)

        # Recarrega a conta do banco
        self.conta.refresh_from_db()
        # Confirma que a nova data de expiração do token foi renovada para o futuro
        self.assertGreater(self.conta.token_expira_em, timezone.now())

    # =========================================================================
    # ENDPOINTS AJAX JSON (POST) COM DEV AUTENTICADO
    # =========================================================================

    # Teste da view AJAX de concorrência de estoque retornando payload JSON
    def test_endpoint_post_estoque_json(self):
        """Valida POST em /testes/concorrencia/estoque/ retornando JSON completo."""
        # Autentica o cliente com usuário DEV
        self.client.login(username="dev_concorrencia", password="testpassword123")
        # Monta o payload JSON com os parâmetros do teste
        payload = {
            'produto_id': self.produto.id,
            'qtd1': 1,
            'qtd2': 2,
            'qtd3': 3,
            'tempo_trava_ms': 0
        }
        # Submete requisição POST enviando JSON
        response = self.client.post(
            self.url_estoque,
            data=json.dumps(payload),
            content_type='application/json'
        )
        # Confirma status HTTP 200 OK
        self.assertEqual(response.status_code, 200)
        # Decodifica a resposta JSON
        data = response.json()
        # Valida flag de sucesso da resposta
        self.assertTrue(data['sucesso'])
        # Valida integridade matemática de consistência
        self.assertTrue(data['consistente'])
        # Confirma total deduzido (1 + 2 + 3 = 6)
        self.assertEqual(data['total_deduzido'], 6)
        # Confirma presença dos carimbos formatados na resposta JSON
        self.assertIn('tempo_inicio_formatado', data)
        self.assertIn('tempo_fim_formatado', data)

    # Teste da view AJAX de renovação concorrente de OAuth retornando payload JSON
    def test_endpoint_post_oauth_json(self):
        """Valida POST em /testes/concorrencia/oauth/ retornando JSON completo."""
        # Autentica como DEV
        self.client.login(username="dev_concorrencia", password="testpassword123")
        # Monta o payload JSON informando a conta alvo
        payload = {
            'conta_id': self.conta.id,
            'tempo_trava_ms': 0
        }
        # Submete requisição POST enviando JSON
        response = self.client.post(
            self.url_oauth,
            data=json.dumps(payload),
            content_type='application/json'
        )
        # Confirma retorno HTTP 200 OK
        self.assertEqual(response.status_code, 200)
        # Decodifica o payload JSON
        data = response.json()
        # Valida que o teste concluiu com sucesso
        self.assertTrue(data['sucesso'])
        # Confirma a asserção de que apenas 1 chamada remota foi efetuada
        self.assertEqual(data['total_chamadas_api'], 1)
        # Confirma que 2 requisições reaproveitaram a credencial renovada
        self.assertEqual(data['total_reaproveitadas'], 2)
