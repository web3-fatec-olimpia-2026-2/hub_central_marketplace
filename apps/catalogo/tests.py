# Os códigos foram gerados com auxilio de I.A.

# Importa a classe Decimal para manipulação financeira e operações monetárias de alta precisão
from decimal import Decimal

# Importa a classe base TestCase (com isolamento transacional por teste) e o cliente HTTP de testes do Django
from django.test import TestCase, Client

# Importa a entidade User padrão do framework Django para criação de operadores e administradores nos testes
from django.contrib.auth.models import User

# Importa o utilitário reverse para resolução dinâmica de rotas nomeadas
from django.urls import reverse

# Importa os modelos de Loja (tenant) e Perfil de Usuário da aplicação tenancy
from apps.tenancy.models import Loja, PerfilUsuario

# Importa o enum que tipifica os papéis hierárquicos de controle de acesso (DEV, ADMIN, SUPERVISOR, USUARIO)
from apps.tenancy.enums import PapelUsuarioEnum

# Importa o modelo de Contas de Integração vinculadas aos canais parceiros
from apps.marketplaces.models import ContaMarketplace

# Importa o enum com as constantes oficiais de canais de marketplace suportados (MERCADOLIVRE, SHOPEE, etc.)
from apps.marketplaces.enums import CanalMarketplaceEnum

# Importa os modelos de Categoria, Produto físico, Anúncio direto e Histórico unificado de auditoria
from apps.catalogo.models import Categoria, Produto, AnuncioMarketplace, HistoricoPreco

# Importa o enum de motivos de movimentação física de estoque (avaria, perda, balanço, entrada)
from apps.catalogo.enums import TipoAjusteEstoqueEnum


# Classe principal de testes automatizados para catálogo de produtos e políticas de segurança de perfil (RBAC)
class CatalogoAndRBACPermissionsTestCase(TestCase):
    # Início do bloco de docstring que documenta os objetivos da suíte de testes e conformidade com a RN-09
    """
    O QUE FAZ: Suíte de testes automatizados para Catálogo de Produtos, Anúncios Multicanal e Restrições RBAC (RN-09).
    POR QUE FAZ: Garante que o papel USUARIO não altere preços nem exclua itens, mas possa registrar baixas por avaria.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR, USUARIO.
    MULTI-TENANCY: Isolamento por Loja.
    """
    # Fim da docstring explicativa da suíte de catálogo

    # Método de inicialização executado antes de cada método de teste individual
    def setUp(self):
        # Instancia o cliente simulador de navegação HTTP
        self.client = Client()

        # Cria a loja matriz que atuará como o tenant proprietário dos registros
        self.loja = Loja.objects.create(
            nome="Loja Central",
            slug="loja-central",
            cnpj="44.444.444/0001-44"
        )
        # Habilita os módulos padrões do sistema para a loja criada
        self.loja.garantir_modulos_padrao()

        # Cria uma categoria associada à loja central
        self.categoria = Categoria.objects.create(
            loja=self.loja,
            nome="Eletrônicos",
            slug="eletronicos"
        )

        # Cria a entidade mestre de produto com 10 unidades físicas em estoque e custos preenchidos
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="NOTE-DELL-G15",
            nome="Notebook Dell G15",
            preco=Decimal('5000.00'),
            estoque=10,
            custo_aquisicao=Decimal('3500.00'),
            custo_embalagem=Decimal('15.00')
        )

        # Usuários
        # Cria usuário com privilégio de administrador de loja
        self.user_admin = User.objects.create_user(username='admin_cat', password='password123')
        # Vincula o perfil ADMIN associado à loja central
        PerfilUsuario.objects.create(usuario=self.user_admin, papel=PapelUsuarioEnum.ADMIN, loja=self.loja)

        # Cria usuário operacional com perfil comum de operador
        self.user_padrao = User.objects.create_user(username='usuario_cat', password='password123')
        # Vincula o perfil USUARIO associado à loja central
        PerfilUsuario.objects.create(usuario=self.user_padrao, papel=PapelUsuarioEnum.USUARIO, loja=self.loja)

        # Contas de marketplace para anúncio multicanal
        # Cria a conta integrada do Mercado Livre vinculada à loja
        self.conta_ml = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Principal",
            seller_id_externo="1111"
        )
        # Cria a conta integrada da Shopee vinculada à mesma loja
        self.conta_shopee = ContaMarketplace.objects.create(
            loja=self.loja,
            canal=CanalMarketplaceEnum.SHOPEE,
            apelido_conta="Shopee Principal",
            seller_id_externo="2222"
        )

    # Teste de validação do desacoplamento multicanal permitindo associar o mesmo produto a contas distintas
    def test_anuncio_multicanal_decoupling(self):
        """Valida a vinculação de múltiplos anúncios em canais distintos ao mesmo produto."""
        # Cria o anúncio do produto para a conta do Mercado Livre
        anuncio_ml = AnuncioMarketplace.objects.create(
            produto=self.produto,
            conta_marketplace=self.conta_ml,
            item_id_externo="MLB998877",
            preco_sincronizado=Decimal('5000.00')
        )
        # Cria o anúncio do mesmo produto físico para a conta da Shopee
        anuncio_shopee = AnuncioMarketplace.objects.create(
            produto=self.produto,
            conta_marketplace=self.conta_shopee,
            item_id_externo="SHP112233",
            preco_sincronizado=Decimal('5000.00')
        )

        # Valida se o produto agregou exatamente 2 anúncios multicanal em seu relacionamento reverso
        self.assertEqual(self.produto.anuncios.count(), 2)
        # Confirma que o anúncio do Mercado Livre está presente na relação
        self.assertIn(anuncio_ml, self.produto.anuncios.all())
        # Confirma que o anúncio da Shopee está presente na relação
        self.assertIn(anuncio_shopee, self.produto.anuncios.all())

    # Teste de auditoria automática garantindo que a mutação de preço gera registro em HistoricoPreco
    def test_price_mutation_creates_history_record(self):
        """Valida que a alteração de preço grava automaticamente em HistoricoPreco."""
        # Autentica no cliente de testes com usuário administrador
        self.client.login(username='admin_cat', password='password123')
        # Submete alteração aumentando o preço do notebook de R$ 5000.00 para R$ 5200.00
        response = self.client.post(reverse('produto_update', kwargs={'pk': self.produto.pk}), {
            'sku': self.produto.sku,
            'nome': self.produto.nome,
            'categoria': self.categoria.pk,
            'preco': '5200.00',
            'estoque': '10',
            'status': 'ATIVO'
        })
        # Valida que a view processou e redirecionou com sucesso (HTTP 302 Found)
        self.assertEqual(response.status_code, 302)

        # Recarrega os dados do produto do banco de dados
        self.produto.refresh_from_db()
        # Valida se o preço do produto foi modificado no banco
        self.assertEqual(self.produto.preco, Decimal('5200.00'))

        # Recupera o registro mais recente gerado na tabela HistoricoPreco para o produto
        historico = HistoricoPreco.objects.filter(produto=self.produto).latest('criado_em')
        # Confirma que o preço anterior registrado foi R$ 5000.00
        self.assertEqual(historico.preco_anterior, Decimal('5000.00'))
        # Confirma que o novo preço registrado na auditoria foi R$ 5200.00
        self.assertEqual(historico.preco_novo, Decimal('5200.00'))

    # Teste que avalia o bloqueio de segurança contra alteração de preço e exclusão pelo perfil USUARIO (RN-09)
    def test_usuario_role_cannot_alter_price_or_delete_product(self):
        """Valida as restrições do papel USUARIO: bloqueio de alteração de preço e exclusão (RN-09)."""
        # 1. Tenta alterar preço via formulário -> Preço é preservado e ignorado
        # Efetua login com o usuário restrito de operação
        self.client.login(username='usuario_cat', password='password123')
        # Tenta enviar formulário de edição com novo nome, mas adulterando preço e estoque
        self.client.post(reverse('produto_update', kwargs={'pk': self.produto.pk}), {
            'sku': self.produto.sku,
            'nome': 'Notebook Dell G15 Editado',
            'categoria': self.categoria.pk,
            'preco': '1000.00',  # Tentativa de alteração não autorizada
            'estoque': '50',      # Tentativa de ajuste geral não autorizada
            'status': 'ATIVO'
        })

        # Recarrega a entidade do banco de dados
        self.produto.refresh_from_db()
        # Valida que o preço original de R$ 5000.00 foi mantido intacto pela regra RN-09
        self.assertEqual(self.produto.preco, Decimal('5000.00'))  # Preço intacto
        # Valida que o saldo físico de estoque original foi mantido intacto em 10 unidades
        self.assertEqual(self.produto.estoque, 10)               # Estoque intacto
        # Confirma que o campo descritivo (nome) foi atualizado normalmente
        self.assertEqual(self.produto.nome, 'Notebook Dell G15 Editado')  # Descritivo atualizado

        # 2. Tenta excluir produto -> Espera 403 Forbidden
        # Submete requisição POST para a rota de exclusão do produto
        res_del = self.client.post(reverse('produto_delete', kwargs={'pk': self.produto.pk}))
        # Valida que o acesso à exclusão foi bloqueado com status HTTP 403 Forbidden
        self.assertEqual(res_del.status_code, 403)

    # Teste confirmando que operadores com papel USUARIO possuem autorização para registrar baixa de avaria
    def test_usuario_role_can_register_baixa_avaria(self):
        """Valida que o papel USUARIO pode registrar baixa pontual de estoque por motivo de avaria/perda (RN-09)."""
        # Autentica com o usuário de operação regular
        self.client.login(username='usuario_cat', password='password123')
        # Submete a baixa por avaria de 2 unidades informando justificativa
        response = self.client.post(reverse('produto_baixa_avaria', kwargs={'pk': self.produto.pk}), {
            'quantidade': 2,
            'tipo_baixa': TipoAjusteEstoqueEnum.SAIDA_AVARIA,
            'justificativa': 'Tela trincada durante o manuseio no galpão'
        })
        # Confirma redirecionamento com sucesso
        self.assertEqual(response.status_code, 302)

        # Recarrega o produto do banco
        self.produto.refresh_from_db()
        # Confirma a dedução correta do inventário (10 - 2 = 8 unidades)
        self.assertEqual(self.produto.estoque, 8)  # 10 - 2 = 8

    # Teste de proteção de integridade referencial: impede exclusão de categoria com produtos vinculados
    def test_categoria_delete_blocked_when_products_exist(self):
        """Valida que categoria com produtos vinculados não pode ser excluída."""
        # Autentica com usuário administrador
        self.client.login(username='admin_cat', password='password123')
        # Tenta excluir a categoria vinculada ao produto existente
        res = self.client.post(reverse('categoria_delete', kwargs={'pk': self.categoria.pk}))
        # Confirma redirecionamento emitindo alerta
        self.assertEqual(res.status_code, 302)
        # Categoria deve continuar existindo
        # Confirma que a categoria foi preservada no banco de dados
        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())

    # Teste do endpoint que vincula um anúncio de marketplace direto a um produto local
    def test_anuncio_marketplace_view_creation(self):
        """Valida a criação de vínculo de anúncio via endpoint da view."""
        # Autentica com perfil de administrador
        self.client.login(username='admin_cat', password='password123')
        # Envia requisição para criação do vínculo do anúncio
        res = self.client.post(reverse('anuncio_marketplace_create', kwargs={'pk': self.produto.pk}), {
            'conta_marketplace': self.conta_ml.pk,
            'item_id_externo': 'MLB_NOVO_123',
            'status_anuncio': 'ativo',
            'preco_sincronizado': '5000.00'
        })
        # Confirma redirecionamento
        self.assertEqual(res.status_code, 302)
        # Valida que o registro de anúncio foi criado no banco
        self.assertTrue(AnuncioMarketplace.objects.filter(item_id_externo='MLB_NOVO_123').exists())

    # Teste de bloqueio de permissão: perfil USUARIO não pode acessar a view de publicação de anúncios
    def test_publicar_anuncio_view_blocked_for_usuario_role(self):
        """Valida que o papel USUARIO é bloqueado com 403 ao tentar publicar anúncio (RF-04 / RBAC)."""
        # Autentica com perfil USUARIO
        self.client.login(username='usuario_cat', password='password123')
        # Tenta acessar via GET a tela de publicação de anúncio
        res_get = self.client.get(reverse('anuncio_marketplace_publicar', kwargs={'pk': self.produto.pk}))
        # Valida bloqueio HTTP 403
        self.assertEqual(res_get.status_code, 403)

        # Tenta disparar o POST de publicação de anúncio
        res_post = self.client.post(reverse('anuncio_marketplace_publicar', kwargs={'pk': self.produto.pk}), {
            'conta_marketplace': self.conta_ml.pk,
            'listing_type_id': 'gold_special',
            'preco': '5000.00',
            'category_id': 'MLB3530'
        })
        # Valida rejeição HTTP 403
        self.assertEqual(res_post.status_code, 403)

    # Teste de publicação de anúncio via view por administrador com criação de metadados
    def test_publicar_anuncio_view_success_and_telemetry(self):
        """Valida a publicação de anúncio com criação em AnuncioMarketplace e telemetria (RF-04)."""
        # Autentica como administrador
        self.client.login(username='admin_cat', password='password123')
        # Requisita a tela de publicação via GET
        res_get = self.client.get(reverse('anuncio_marketplace_publicar', kwargs={'pk': self.produto.pk}))
        # Confirma carregamento da página com status HTTP 200
        self.assertEqual(res_get.status_code, 200)
        # Valida a presença do título da tela no HTML renderizado
        self.assertContains(res_get, "Parâmetros de Publicação no Marketplace")

        # Submete os parâmetros de publicação via POST
        res_post = self.client.post(reverse('anuncio_marketplace_publicar', kwargs={'pk': self.produto.pk}), {
            'conta_marketplace': self.conta_ml.pk,
            'listing_type_id': 'gold_special',
            'preco': '4950.00',
            'category_id': 'MLB3530'
        })
        # Confirma redirecionamento após a criação
        self.assertEqual(res_post.status_code, 302)

        # Valida que o AnuncioMarketplace foi criado/atualizado
        # Recupera o registro criado no banco
        anuncio = AnuncioMarketplace.objects.get(produto=self.produto, conta_marketplace=self.conta_ml)
        # Confirma que o preço sincronizado foi de R$ 4950.00
        self.assertEqual(anuncio.preco_sincronizado, Decimal('4950.00'))
        # Valida que o status do anúncio foi definido como ativo
        self.assertEqual(anuncio.status_anuncio, 'ativo')
        # Valida se o ID externo atribuído inicia com o prefixo 'MLB'
        self.assertTrue(anuncio.item_id_externo.startswith('MLB'))

    # Teste de isolamento multi-tenant impedindo publicação de produto em conta de marketplace de outro tenant
    def test_publicar_anuncio_multi_tenant_isolation(self):
        """Valida que uma loja não pode publicar na conta de outra loja (Isolamento Multi-tenant)."""
        # Cria uma loja distinta para simular outro tenant
        loja_alheia = Loja.objects.create(
            nome="Loja Alheia",
            slug="loja-alheia",
            cnpj="88.888.888/0001-88"
        )
        # Cria uma conta de marketplace atrelada a esse outro tenant
        conta_alheia = ContaMarketplace.objects.create(
            loja=loja_alheia,
            canal=CanalMarketplaceEnum.MERCADOLIVRE,
            apelido_conta="ML Alheio",
            seller_id_externo="8888"
        )

        # Autentica como administrador da loja original
        self.client.login(username='admin_cat', password='password123')
        # Tenta publicar o produto da loja original na conta da loja alheia
        res_cross = self.client.post(reverse('anuncio_marketplace_publicar', kwargs={'pk': self.produto.pk}), {
            'conta_marketplace': conta_alheia.pk,
            'listing_type_id': 'gold_special',
            'preco': '5000.00'
        })
        # Formulário deve rejeitar ou view bloquear com 403
        # Confirma que a tentativa resultou em formulário inválido (HTTP 200) ou bloqueio de permissão (HTTP 403)
        self.assertIn(res_cross.status_code, [200, 403])
        # Garante que nenhum anúncio indevido foi persistido no banco
        self.assertFalse(AnuncioMarketplace.objects.filter(produto=self.produto, conta_marketplace=conta_alheia).exists())

    # Teste da propriedade consolidada de status e da respectiva estilização visual do badge
    def test_produto_status_sincronizacao_consolidado(self):
        """Valida cálculo dinâmico da propriedade status_sincronizacao_consolidado e respectivo badge."""
        # Importa os modelos de anúncio e composição
        from apps.anuncios.models import Anuncio, AnuncioComposicao

        # 1. Sem anúncios vinculados
        # Valida que o produto sem anúncios retorna 'Sem Anúncios'
        self.assertEqual(self.produto.status_sincronizacao_consolidado, "Sem Anúncios")
        # Valida a classe Bootstrap neutra associada
        self.assertEqual(self.produto.status_sincronizacao_consolidado_badge, "bg-light text-dark border")

        # 2. Cria anúncio vinculado com status PENDENTE
        # Cria anúncio com sincronização pendente
        anuncio = Anuncio.objects.create(
            conta=self.conta_ml,
            item_id_externo="MLB_TEST_STATUS",
            titulo="Notebook Teste",
            preco_venda=Decimal('5000.00'),
            estoque_publicado=10,
            status_sincronizacao='PENDENTE'
        )
        # Vincula o produto ao anúncio
        AnuncioComposicao.objects.create(anuncio=anuncio, produto=self.produto, quantidade=1)

        # Valida que o status consolidado do produto passa para 'Pendente de Sincronização'
        self.assertEqual(self.produto.status_sincronizacao_consolidado, "Pendente de Sincronização")
        # Valida o badge de alerta amarelo
        self.assertEqual(self.produto.status_sincronizacao_consolidado_badge, "bg-warning text-dark")

        # 3. Status ENVIADO sem divergências
        # Atualiza o status do anúncio para ENVIADO
        anuncio.status_sincronizacao = 'ENVIADO'
        anuncio.save()
        # Valida que o status consolidado do produto passa para 'Sincronizado com Sucesso'
        self.assertEqual(self.produto.status_sincronizacao_consolidado, "Sincronizado com Sucesso")
        # Valida o badge de sucesso verde
        self.assertEqual(self.produto.status_sincronizacao_consolidado_badge, "bg-success text-white")

        # 4. Status CANCELADO
        # Atualiza o status do anúncio para CANCELADO
        anuncio.status_sincronizacao = 'CANCELADO'
        anuncio.save()
        # Valida que o status consolidado passa para 'Sincronização Descartada'
        self.assertEqual(self.produto.status_sincronizacao_consolidado, "Sincronização Descartada")
        # Valida o badge secundário cinza
        self.assertEqual(self.produto.status_sincronizacao_consolidado_badge, "bg-secondary text-white")

    # Teste de envio de sincronização selecionando anúncios específicos via formulário com checkboxes
    def test_produto_sincronizacao_global_seletiva_via_checkboxes(self):
        """Valida que envio global respeita estritamente os IDs de anúncios selecionados no formulário."""
        from apps.anuncios.models import Anuncio, AnuncioComposicao, HistoricoSincronizacaoAnuncio
        from unittest.mock import patch
        from apps.marketplaces.connectors.mercadolivre import MercadoLivreConnector

        # Cria primeiro anúncio com status PENDENTE
        anuncio1 = Anuncio.objects.create(
            conta=self.conta_ml,
            item_id_externo="MLB_SEL_1",
            titulo="Notebook 1",
            preco_venda=Decimal('4900.00'),
            estoque_publicado=5,
            status_sincronizacao='PENDENTE'
        )
        AnuncioComposicao.objects.create(anuncio=anuncio1, produto=self.produto, quantidade=1)

        # Cria segundo anúncio com status CANCELADO
        anuncio2 = Anuncio.objects.create(
            conta=self.conta_ml,
            item_id_externo="MLB_SEL_2",
            titulo="Notebook 2",
            preco_venda=Decimal('4900.00'),
            estoque_publicado=5,
            status_sincronizacao='CANCELADO'
        )
        AnuncioComposicao.objects.create(anuncio=anuncio2, produto=self.produto, quantidade=1)

        # Autentica como administrador
        self.client.login(username='admin_cat', password='password123')
        url_sync = reverse('produto_sincronizar_preco', kwargs={'pk': self.produto.pk})

        # 1. Submissão sem nenhum anúncio selecionado
        # Submete requisição sem marcar nenhum checkbox
        res_vazio = self.client.post(url_sync, {'anuncios_selecionados': []})
        self.assertEqual(res_vazio.status_code, 302)
        anuncio1.refresh_from_db()
        # Valida que o anúncio 1 permaneceu como PENDENTE sem alteração
        self.assertEqual(anuncio1.status_sincronizacao, 'PENDENTE')

        # 2. Submissão selecionando apenas anuncio1 com acao=enviar
        # Simula chamadas externas de estoque e preço no conector
        with patch.object(MercadoLivreConnector, 'atualizar_estoque', return_value=(True, "OK", None)), \
             patch.object(MercadoLivreConnector, 'atualizar_preco', return_value=(True, "OK", None)):
            # Envia a instrução de sincronizar apenas o anúncio 1
            res_sel = self.client.post(url_sync, {'anuncios_selecionados': [anuncio1.pk], 'acao': 'enviar'})
            self.assertEqual(res_sel.status_code, 302)

            anuncio1.refresh_from_db()
            anuncio2.refresh_from_db()
            # Confirma que o anúncio 1 selecionado foi atualizado para ENVIADO
            self.assertEqual(anuncio1.status_sincronizacao, 'ENVIADO')
            # Confirma que o anúncio 2 não selecionado permaneceu intacto como CANCELADO
            self.assertEqual(anuncio2.status_sincronizacao, 'CANCELADO')  # Intacto

            # Confirma que foi registrado o histórico do anúncio 1
            self.assertTrue(HistoricoSincronizacaoAnuncio.objects.filter(
                anuncio=anuncio1, status_resultante='ENVIADO'
            ).exists())

            # Validação do duplo histórico registrado no Produto com SKU e Canal
            # Localiza a auditoria gravada na entidade do Produto referenciando o canal e ID externo
            hist_prod = HistoricoPreco.objects.filter(
                produto=self.produto,
                motivo__icontains="Mercado Livre"
            ).filter(motivo__icontains="MLB_SEL_1")
            self.assertTrue(hist_prod.exists())
            self.assertIn("Sincronização enviada ao canal", hist_prod.first().motivo)

    # Teste da ação de cancelamento no modal: gravação de histórico duplo e remoção da fila de pendentes
    def test_produto_sincronizacao_global_acao_cancelar_e_fila_pendentes(self):
        """Valida ação de cancelamento com duplo histórico e exclusão do anúncio da fila de pendentes."""
        from apps.anuncios.models import Anuncio, AnuncioComposicao, HistoricoSincronizacaoAnuncio

        # Cria anúncio pendente vinculado ao produto
        anuncio = Anuncio.objects.create(
            conta=self.conta_ml,
            item_id_externo="MLB_CANC_1",
            titulo="Notebook Canc",
            preco_venda=Decimal('4900.00'),
            estoque_publicado=5,
            status_sincronizacao='PENDENTE'
        )
        AnuncioComposicao.objects.create(anuncio=anuncio, produto=self.produto, quantidade=1)

        # Autentica com administrador
        self.client.login(username='admin_cat', password='password123')
        url_detail = reverse('produto_detail', kwargs={'pk': self.produto.pk})
        url_sync = reverse('produto_sincronizar_preco', kwargs={'pk': self.produto.pk})

        # Antes do cancelamento, o anúncio está na fila de pendentes
        # Carrega a tela de detalhes do produto
        res_detail_antes = self.client.get(url_detail)
        # Confirma que o anúncio consta na listagem de pendências de sincronização do modal
        self.assertIn(anuncio, res_detail_antes.context['anuncios_pendentes_sync'])

        # Dispara cancelamento/descarte no modal
        # Envia a ação 'cancelar' para o anúncio selecionado
        res_cancel = self.client.post(url_sync, {
            'anuncios_selecionados': [anuncio.pk],
            'acao': 'cancelar'
        })
        self.assertEqual(res_cancel.status_code, 302)

        # Recarrega o anúncio do banco
        anuncio.refresh_from_db()
        # Confirma que o status foi atualizado para CANCELADO
        self.assertEqual(anuncio.status_sincronizacao, 'CANCELADO')

        # 1. Histórico no Anúncio
        # Valida a gravação da auditoria no modelo do anúncio
        hist_anuncio = HistoricoSincronizacaoAnuncio.objects.filter(
            anuncio=anuncio, status_resultante='CANCELADO'
        ).first()
        self.assertIsNotNone(hist_anuncio)
        self.assertIn("Mercado Livre", hist_anuncio.motivo)
        self.assertIn(anuncio.item_id_externo, hist_anuncio.motivo)

        # 2. Histórico no Produto
        # Valida a gravação simultânea da auditoria no modelo Produto
        hist_prod = HistoricoPreco.objects.filter(
            produto=self.produto,
            motivo__icontains="cancelada/descartada"
        ).filter(motivo__icontains=anuncio.item_id_externo).first()
        self.assertIsNotNone(hist_prod)
        self.assertIn("Mercado Livre", hist_prod.motivo)

        # Após o cancelamento, o anúncio sai da fila de pendentes no modal
        # Recarrega a tela de detalhe do produto
        res_detail_depois = self.client.get(url_detail)
        # Valida que o anúncio foi removido da fila de pendentes exibida no modal
        self.assertNotIn(anuncio, res_detail_depois.context['anuncios_pendentes_sync'])
        # Confirma a integridade da propriedade de última sincronização
        self.assertEqual(anuncio.ultima_sincronizacao, anuncio.data_sincronizacao)

    # Teste de reabertura automática de pendência quando um anúncio CANCELADO sofre alteração de saldo físico
    def test_anuncio_cancelado_reabre_pendencia_sob_alteracao_fisica_estoque(self):
        """Valida que anúncio CANCELADO volta automaticamente para PENDENTE ao sofrer alteração física."""
        from apps.anuncios.models import Anuncio, AnuncioComposicao, HistoricoSincronizacaoAnuncio

        # Cria anúncio com status inicial CANCELADO
        anuncio = Anuncio.objects.create(
            conta=self.conta_ml,
            item_id_externo="MLB_REOPEN_1",
            titulo="Notebook Reopen",
            preco_venda=Decimal('5000.00'),
            estoque_publicado=10,
            status_sincronizacao='CANCELADO'
        )
        AnuncioComposicao.objects.create(anuncio=anuncio, produto=self.produto, quantidade=1)

        # Autentica com administrador
        self.client.login(username='admin_cat', password='password123')
        url_detail = reverse('produto_detail', kwargs={'pk': self.produto.pk})
        url_baixa = reverse('produto_baixa_avaria', kwargs={'pk': self.produto.pk})

        # Inicialmente está CANCELADO e com cota igual ao publicado (10 un), logo não está pendente
        res_antes = self.client.get(url_detail)
        self.assertNotIn(anuncio, res_antes.context['anuncios_pendentes_sync'])

        # Registra baixa por avaria de 2 unidades (10 -> 8)
        # Executa a baixa física de 2 unidades por motivo de avaria
        res_baixa = self.client.post(url_baixa, {
            'quantidade': 2,
            'tipo_baixa': TipoAjusteEstoqueEnum.SAIDA_AVARIA,
            'justificativa': 'Produto danificado'
        })
        self.assertEqual(res_baixa.status_code, 302)

        # O anúncio vinculado DEVE ter reaberto para PENDENTE
        # Recarrega o anúncio do banco
        anuncio.refresh_from_db()
        # Valida que o anúncio retornou automaticamente para o status PENDENTE
        self.assertEqual(anuncio.status_sincronizacao, 'PENDENTE')
        # Valida que a cota disponível agora reflete as 8 unidades restantes
        self.assertEqual(anuncio.calcular_cota_disponivel(), 8)

        # Fila do modal e badge refletem o anúncio pendente
        # Requisita a tela de detalhes do produto
        res_depois = self.client.get(url_detail)
        # Confirma que o anúncio reaberto voltou para a lista de pendentes do modal
        self.assertIn(anuncio, res_depois.context['anuncios_pendentes_sync'])
        self.assertEqual(len(res_depois.context['anuncios_pendentes_sync']), 1)
        # Valida se o badge de contagem de pendências (1) é renderizado
        self.assertContains(res_depois, '<span class="badge bg-danger rounded-pill ms-2">1</span>')
        self.assertContains(res_depois, '1 ação(ões) de sincronização aguardando decisão')

        # Linha em HistoricoSincronizacaoAnuncio com status_resultante='PENDENTE'
        # Localiza a auditoria registrando a transição do anúncio para pendente
        hist_pend = HistoricoSincronizacaoAnuncio.objects.filter(
            anuncio=anuncio, status_resultante='PENDENTE'
        ).first()
        self.assertIsNotNone(hist_pend)
        # Valida o registro de estoque anterior (10) e proposto (8)
        self.assertEqual(hist_pend.estoque_anterior, 10)
        self.assertEqual(hist_pend.estoque_proposto, 8)

    # Teste de ajuste de estoque em produto desvinculado de anúncios emitindo alerta em nível WARNING
    def test_ajuste_estoque_produto_sem_anuncios_emite_alerta_warning(self):
        # Docstring documentando o Cenário 4 de teste de produto sem vínculos de anúncio
        """
        Cenário 4: Fluxo de Estoque sem Vínculo.
        Executar ajuste geral de estoque em produto com 0 anúncios associados.
        Assertar que nenhuma entrada é criada na fila de sincronização e que a mensagem retornada no contexto possui nível messages.WARNING.
        """
        from django.contrib.messages import get_messages
        from django.contrib import messages as django_messages
        from apps.anuncios.models import HistoricoSincronizacaoAnuncio

        # Cria um produto sem nenhum anúncio vinculado
        # Instancia produto isolado no catálogo
        prod_sem_anuncio = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            sku="SEM-ANUNCIO-01",
            nome="Produto Sem Anúncio",
            preco=Decimal('100.00'),
            estoque=50
        )
        # Valida que a contagem de anúncios publicados é nula
        self.assertEqual(prod_sem_anuncio.anuncios_publicados.count(), 0)

        # Autentica como administrador
        self.client.force_login(self.user_admin)
        url_ajuste = reverse('produto_ajuste_estoque', kwargs={'pk': prod_sem_anuncio.pk})

        # Executa ajuste de saldo físico de 50 para 45 unidades
        resp = self.client.post(url_ajuste, {
            'novo_estoque': 45,
            'tipo_ajuste': TipoAjusteEstoqueEnum.CORRECAO_BALANCO,
            'justificativa': 'Contagem de inventário'
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        prod_sem_anuncio.refresh_from_db()
        self.assertEqual(prod_sem_anuncio.estoque, 45)

        # Nenhuma entrada deve ter sido criada em HistoricoSincronizacaoAnuncio
        # Garante que nenhuma entrada foi gerada na fila de sincronização
        self.assertEqual(
            HistoricoSincronizacaoAnuncio.objects.filter(anuncio__in=prod_sem_anuncio.anuncios_publicados).count(),
            0
        )

        # Mensagem deve possuir nível WARNING e o texto exato
        # Extrai a lista de mensagens flash retornadas na requisição
        mensagens = list(get_messages(resp.wsgi_request))
        # Valida se há pelo menos uma mensagem com nível WARNING
        self.assertTrue(any(m.level == django_messages.WARNING for m in mensagens))
        # Isola a mensagem de aviso
        msg_warning = [m for m in mensagens if m.level == django_messages.WARNING][0]
        # Valida o teor do alerta notificando a ausência de anúncios no marketplace
        self.assertIn("este produto não possui anúncios vinculados, portanto nenhuma sincronização foi enviada ao marketplace", msg_warning.message)
        self.assertIn("Estoque atualizado para 45 un. com sucesso", msg_warning.message)


