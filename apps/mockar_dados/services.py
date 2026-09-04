# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Serviço atômico para provisionamento, substituição e exclusão de dados mockados de teste.
POR QUE FAZ: Permite ao desenvolvedor/testador popular ou limpar a base de dados de demonstração com um único clique.
REGRAS DE SEGURANÇA E AMBIENTE:
- Executado sob transação atômica (transaction.atomic).
- O usuário DEV mestre (devmaster) é estritamente preservado e NUNCA é excluído ou alterado.
- Utiliza máscaras de CNPJ e telefones anticoincidência sintéticos (11.111.111/0001-11, etc.).
- Metade dos produtos gerados recebe status RASCUNHO e a outra metade ATIVO.
"""
from decimal import Decimal
from django.db import transaction
from django.contrib.auth.models import User

from apps.tenancy.models import Loja, PerfilUsuario
from apps.tenancy.enums import PapelUsuarioEnum, ModuloSistemaEnum
from apps.catalogo.models import Categoria, Produto, AnuncioMarketplace
from apps.catalogo.enums import StatusProdutoEnum
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import CanalMarketplaceEnum
from apps.financeiro.models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace
from .conf import DEV_HARDCODED_USER, DEV_HARDCODED_PASS, DEV_HARDCODED_EMAIL


def is_simular_rotas_mock_ativo(request=None) -> bool:
    """
    O QUE FAZ: Verifica se a feature flag SIMULAR_ROTAS_MOCK está habilitada.
    POR QUE FAZ: Controla se as ações em contas mockadas retornam sucesso simulado (HTTP 200) ou recusa (HTTP 401).
    PRIORIDADE: request.session['SIMULAR_ROTAS_MOCK'] > settings.SIMULAR_ROTAS_MOCK > True.
    """
    from django.conf import settings
    if request and hasattr(request, 'session'):
        val = request.session.get('SIMULAR_ROTAS_MOCK')
        if val is not None:
            return bool(val)
    return getattr(settings, 'SIMULAR_ROTAS_MOCK', True)


def alternar_simulacao_mock(request) -> bool:
    """
    O QUE FAZ: Inverte o estado da flag SIMULAR_ROTAS_MOCK na sessão do usuário.
    POR QUE FAZ: Permite alternar rapidamente entre modo Simulado e modo Recusa (HTTP 401) pela interface.
    """
    atual = is_simular_rotas_mock_ativo(request)
    novo = not atual
    if request and hasattr(request, 'session'):
        request.session['SIMULAR_ROTAS_MOCK'] = novo
    return novo


class MockDataService:
    """
    Serviço centralizado de gestão de dados sintéticos para testes e desenvolvimento.
    """

    MOCK_SLUGS = ['techzone-mock', 'comfort-mock', 'passofirme-mock']
    MOCK_CNPJS = ['11.111.111/0001-11', '22.222.222/0001-22', '33.333.333/0001-33']
    MOCK_USERNAMES = [
        'admin_techzone', 'sup_techzone', 'user_techzone',
        'admin_comfort', 'sup_comfort', 'user_comfort',
        'admin_passofirme', 'sup_passofirme', 'user_passofirme',
    ]

    @classmethod
    def tem_dados_mockados(cls) -> bool:
        """
        Verifica se existem lojas mockadas registradas no banco de dados.
        """
        return Loja.objects.filter(slug__in=cls.MOCK_SLUGS).exists()

    @classmethod
    def contar_registros_mockados(cls) -> dict:
        """
        Retorna o quantitativo atual de entidades mockadas no sistema.
        """
        lojas = Loja.objects.filter(slug__in=cls.MOCK_SLUGS)
        lojas_ids = list(lojas.values_list('id', flat=True))

        return {
            'lojas': lojas.count(),
            'produtos': Produto.objects.filter(loja_id__in=lojas_ids).count(),
            'categorias': Categoria.objects.filter(loja_id__in=lojas_ids).count(),
            'contas_marketplace': ContaMarketplace.objects.filter(loja_id__in=lojas_ids).count(),
            'anuncios': AnuncioMarketplace.objects.filter(produto__loja_id__in=lojas_ids).count(),
            'usuarios': User.objects.filter(username__in=cls.MOCK_USERNAMES).count(),
        }

    @classmethod
    @transaction.atomic
    def excluir_dados_mockados(cls) -> dict:
        """
        Exclui permanentemente todos os registros sintéticos criados para teste.
        Garante expressamente a preservação do usuário devmaster.
        """
        # 1. Localiza as lojas mockadas
        lojas = Loja.objects.filter(slug__in=cls.MOCK_SLUGS)
        qtd_lojas = lojas.count()
        lojas_ids = list(lojas.values_list('id', flat=True))

        if qtd_lojas > 0:
            # Exclui dependências em ordem reversa para respeitar FKs com on_delete=PROTECT (ex: Produto -> Categoria)
            AnuncioMarketplace.objects.filter(produto__loja_id__in=lojas_ids).delete()
            Produto.objects.filter(loja_id__in=lojas_ids).delete()
            Categoria.objects.filter(loja_id__in=lojas_ids).delete()
            ContaMarketplace.objects.filter(loja_id__in=lojas_ids).delete()
            ConfiguracaoTaxasLoja.objects.filter(loja_id__in=lojas_ids).delete()
            ParametroCanalMarketplace.objects.filter(loja_id__in=lojas_ids).delete()
            lojas.delete()

        # 2. Exclui os usuários mockados secundários (NUNCA devmaster)
        usuarios_para_excluir = User.objects.filter(
            username__in=cls.MOCK_USERNAMES
        ).exclude(username=DEV_HARDCODED_USER)
        qtd_usuarios = usuarios_para_excluir.count()
        usuarios_para_excluir.delete()

        return {
            'sucesso': True,
            'lojas_excluidas': qtd_lojas,
            'usuarios_excluidos': qtd_usuarios,
        }

    @classmethod
    @transaction.atomic
    def gerar_dados_mockados(cls) -> dict:
        """
        Gera ou substitui o conjunto completo de dados sintéticos de teste.
        """
        # 1. Limpa registros mockados pré-existentes para garantir padrão de fábrica
        cls.excluir_dados_mockados()

        # 2. Assegura a existência do DEV Master intacto
        user_dev, _ = User.objects.get_or_create(
            username=DEV_HARDCODED_USER,
            defaults={
                'email': DEV_HARDCODED_EMAIL,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        if not user_dev.check_password(DEV_HARDCODED_PASS):
            user_dev.set_password(DEV_HARDCODED_PASS)
            user_dev.save()

        perfil_dev, _ = PerfilUsuario.objects.get_or_create(
            usuario=user_dev,
            defaults={'papel': PapelUsuarioEnum.DEV, 'loja': None}
        )
        perfil_dev.papel = PapelUsuarioEnum.DEV
        perfil_dev.loja = None
        perfil_dev.save()

        # 3. Definição das 3 Lojas Mockadas
        lojas_especificacao = [
            {
                'nome': 'TechZone Eletrônicos Mock',
                'slug': 'techzone-mock',
                'cnpj': '11.111.111/0001-11',
                'telefone': '(11) 1111-1111',
                'email': 'contato@techzone.mock',
                'cidade': 'São Paulo',
                'estado': 'SP',
                'categoria_nome': 'Eletrônicos & Informática',
                'categoria_slug': 'eletronicos-techzone',
                'taxas': {
                    'aliquota_imposto': Decimal('0.0600'),
                    'custo_embalagem_padrao': Decimal('3.50'),
                    'margem_minima_seguranca': Decimal('0.1500'),
                    'custos_fixos_mensais': Decimal('5500.00'),
                },
                'usuarios': [
                    ('admin_techzone', 'TechZone Admin', PapelUsuarioEnum.ADMIN),
                    ('sup_techzone', 'TechZone Supervisor', PapelUsuarioEnum.SUPERVISOR),
                    ('user_techzone', 'TechZone Operador', PapelUsuarioEnum.USUARIO),
                ],
                'produtos': [
                    ('TZ-NOTE-01', 'Notebook Gamer Core i7 16GB RTX', Decimal('4899.00'), Decimal('3400.00'), Decimal('15.00'), 12, StatusProdutoEnum.ATIVO, True),
                    ('TZ-MON-02', 'Monitor UltraWide 29 IPS 75Hz', Decimal('1199.00'), Decimal('820.00'), Decimal('20.00'), 20, StatusProdutoEnum.ATIVO, False),
                    ('TZ-MOUSE-03', 'Mouse Sem Fio Ergonômico 2.4Ghz', Decimal('149.90'), Decimal('55.00'), Decimal('4.00'), 50, StatusProdutoEnum.ATIVO, False),
                    ('TZ-HEAD-04', 'Headset Gamer Surround 7.1 USB', Decimal('329.90'), Decimal('160.00'), Decimal('6.00'), 15, StatusProdutoEnum.RASCUNHO, False),
                    ('TZ-WEBC-05', 'Webcam Full HD 1080p c/ Microfone', Decimal('249.90'), Decimal('115.00'), Decimal('5.00'), 8, StatusProdutoEnum.RASCUNHO, False),
                ]
            },
            {
                'nome': 'Comfort Cama Mesa e Banho Mock',
                'slug': 'comfort-mock',
                'cnpj': '22.222.222/0001-22',
                'telefone': '(22) 2222-2222',
                'email': 'contato@comfort.mock',
                'cidade': 'Niterói',
                'estado': 'RJ',
                'categoria_nome': 'Cama, Mesa e Banho',
                'categoria_slug': 'cama-mesa-banho-comfort',
                'taxas': {
                    'aliquota_imposto': Decimal('0.0450'),
                    'custo_embalagem_padrao': Decimal('4.00'),
                    'margem_minima_seguranca': Decimal('0.1800'),
                    'custos_fixos_mensais': Decimal('3200.00'),
                },
                'usuarios': [
                    ('admin_comfort', 'Comfort Admin', PapelUsuarioEnum.ADMIN),
                    ('sup_comfort', 'Comfort Supervisor', PapelUsuarioEnum.SUPERVISOR),
                    ('user_comfort', 'Comfort Operador', PapelUsuarioEnum.USUARIO),
                ],
                'produtos': [
                    ('CF-JOGO-01', 'Jogo de Cama Queen 400 Fios Cetim', Decimal('289.90'), Decimal('135.00'), Decimal('8.00'), 30, StatusProdutoEnum.ATIVO, False),
                    ('CF-TOAL-02', 'Kit 4 Toalhas Banhão Algodão Egípcio', Decimal('179.90'), Decimal('78.00'), Decimal('6.00'), 40, StatusProdutoEnum.ATIVO, True),
                    ('CF-EDR-03', 'Edredom Dupla Face Casal Plush Macio', Decimal('239.90'), Decimal('105.00'), Decimal('10.00'), 25, StatusProdutoEnum.ATIVO, False),
                    ('CF-TRAV-04', 'Par de Travesseiros Ortopédicos Nasa', Decimal('129.90'), Decimal('58.00'), Decimal('5.00'), 18, StatusProdutoEnum.RASCUNHO, False),
                    ('CF-MANTA-05', 'Manta Microfibra Soft Toque de Seda', Decimal('89.90'), Decimal('36.00'), Decimal('4.00'), 35, StatusProdutoEnum.RASCUNHO, False),
                ]
            },
            {
                'nome': 'Passo Firme Calçados Mock',
                'slug': 'passofirme-mock',
                'cnpj': '33.333.333/0001-33',
                'telefone': '(33) 3333-3333',
                'email': 'contato@passofirme.mock',
                'cidade': 'Belo Horizonte',
                'estado': 'MG',
                'categoria_nome': 'Calçados & Acessórios',
                'categoria_slug': 'calcados-passofirme',
                'taxas': {
                    'aliquota_imposto': Decimal('0.0500'),
                    'custo_embalagem_padrao': Decimal('3.00'),
                    'margem_minima_seguranca': Decimal('0.1600'),
                    'custos_fixos_mensais': Decimal('4000.00'),
                },
                'usuarios': [
                    ('admin_passofirme', 'Passo Firme Admin', PapelUsuarioEnum.ADMIN),
                    ('sup_passofirme', 'Passo Firme Supervisor', PapelUsuarioEnum.SUPERVISOR),
                    ('user_passofirme', 'Passo Firme Operador', PapelUsuarioEnum.USUARIO),
                ],
                'produtos': [
                    ('PF-TENIS-01', 'Tênis Esportivo Running Amortecedor', Decimal('379.90'), Decimal('168.00'), Decimal('6.00'), 45, StatusProdutoEnum.ATIVO, True),
                    ('PF-SAPA-02', 'Sapato Social Couro Legítimo Nobuck', Decimal('299.00'), Decimal('125.00'), Decimal('7.00'), 22, StatusProdutoEnum.ATIVO, False),
                    ('PF-BOTA-03', 'Bota Adventure Couro Trilha Impermeável', Decimal('349.90'), Decimal('150.00'), Decimal('8.00'), 16, StatusProdutoEnum.ATIVO, False),
                    ('PF-SND-04', 'Sandália Feminina Confort Anatômica', Decimal('149.90'), Decimal('62.00'), Decimal('4.00'), 28, StatusProdutoEnum.RASCUNHO, False),
                    ('PF-CHIN-05', 'Chinelo Slide Nuvem Ortopédico', Decimal('69.90'), Decimal('25.00'), Decimal('3.00'), 60, StatusProdutoEnum.RASCUNHO, False),
                ]
            },
        ]

        total_produtos_criados = 0
        total_anuncios_criados = 0

        for spec in lojas_especificacao:
            # A. Criação da Loja
            loja = Loja.objects.create(
                nome=spec['nome'],
                slug=spec['slug'],
                cnpj=spec['cnpj'],
                telefone=spec['telefone'],
                email=spec['email'],
                cidade=spec['cidade'],
                estado=spec['estado'],
                pais='Brasil',
                ativo=True
            )
            loja.garantir_modulos_padrao()

            # B. Criação dos Parâmetros Fiscais da Loja
            ConfiguracaoTaxasLoja.objects.create(
                loja=loja,
                aliquota_imposto=spec['taxas']['aliquota_imposto'],
                custo_embalagem_padrao=spec['taxas']['custo_embalagem_padrao'],
                margem_minima_seguranca=spec['taxas']['margem_minima_seguranca'],
                custos_fixos_mensais=spec['taxas']['custos_fixos_mensais']
            )

            # C. Criação dos Parâmetros dos Canais
            canais_params = [
                ('mercadolivre_classico', Decimal('0.1200'), Decimal('79.00'), Decimal('18.00'), Decimal('6.00')),
                ('mercadolivre_premium', Decimal('0.1700'), Decimal('79.00'), Decimal('18.00'), Decimal('6.00')),
                ('shopee', Decimal('0.1400'), Decimal('50.00'), Decimal('14.00'), Decimal('4.00')),
                ('magalu', Decimal('0.1600'), Decimal('79.00'), Decimal('16.00'), Decimal('5.00')),
            ]
            for canal_nome, comissao, frete_piso, frete_acima, taxa_abaixo in canais_params:
                ParametroCanalMarketplace.objects.create(
                    loja=loja,
                    marketplace=canal_nome,
                    comissao_padrao=comissao,
                    frete_gratis_piso=frete_piso,
                    taxa_frete_acima_limite=frete_acima,
                    taxa_fixa_abaixo_limite=taxa_abaixo
                )

            # D. Criação dos Usuários Operacionais da Loja
            for username, nome_completo, papel in spec['usuarios']:
                user_obj = User.objects.create_user(
                    username=username,
                    email=f'{username}@mock.local',
                    password='password123',
                    first_name=nome_completo.split()[0],
                    last_name=' '.join(nome_completo.split()[1:]) if len(nome_completo.split()) > 1 else ''
                )
                PerfilUsuario.objects.create(
                    usuario=user_obj,
                    papel=papel,
                    loja=loja
                )

            # E. Criação de Contas de Marketplace para a Loja
            conta_ml = ContaMarketplace.objects.create(
                loja=loja,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                apelido_conta=f'ML - {loja.nome[:15]}',
                seller_id_externo=f'ML_{spec["cnpj"][:8]}',
                access_token=f'MOCK_TOKEN_ML_{loja.id}',
                ativo=True,
                is_mock=True
            )
            conta_shopee = ContaMarketplace.objects.create(
                loja=loja,
                canal=CanalMarketplaceEnum.SHOPEE,
                apelido_conta=f'Shopee - {loja.nome[:15]}',
                seller_id_externo=f'SHP_{spec["cnpj"][:8]}',
                access_token=f'MOCK_TOKEN_SHP_{loja.id}',
                ativo=True,
                is_mock=True
            )
            conta_magalu = ContaMarketplace.objects.create(
                loja=loja,
                canal=CanalMarketplaceEnum.MAGALU,
                apelido_conta=f'Magalu - {loja.nome[:15]}',
                seller_id_externo=f'MGL_{spec["cnpj"][:8]}',
                access_token=f'MOCK_TOKEN_MGL_{loja.id}',
                ativo=True,
                is_mock=True
            )

            # F. Criação da Categoria Mestre da Loja
            categoria = Categoria.objects.create(
                loja=loja,
                nome=spec['categoria_nome'],
                slug=spec['categoria_slug'],
                descricao=f'Categoria principal para a {loja.nome}'
            )

            # G. Criação dos Produtos e Anúncios Multicanal
            for sku, nome, preco, custo_aq, custo_emb, estoque, status, full in spec['produtos']:
                produto = Produto.objects.create(
                    loja=loja,
                    categoria=categoria,
                    sku=sku,
                    nome=nome,
                    descricao=f'Descrição detalhada de teste para {nome}. Produto mockado de alta qualidade.',
                    preco=preco,
                    custo_aquisicao=custo_aq,
                    custo_embalagem=custo_emb,
                    estoque=estoque,
                    status=status,
                    modalidade_full=full
                )
                total_produtos_criados += 1

                # Cria anúncios de marketplace para produtos ativos
                if status == StatusProdutoEnum.ATIVO:
                    AnuncioMarketplace.objects.create(
                        produto=produto,
                        conta_marketplace=conta_ml,
                        item_id_externo=f'MLB{produto.id}9988',
                        status_anuncio='ativo',
                        preco_sincronizado=preco
                    )
                    AnuncioMarketplace.objects.create(
                        produto=produto,
                        conta_marketplace=conta_shopee,
                        item_id_externo=f'SHP{produto.id}7766',
                        status_anuncio='ativo',
                        preco_sincronizado=preco
                    )
                    AnuncioMarketplace.objects.create(
                        produto=produto,
                        conta_marketplace=conta_magalu,
                        item_id_externo=f'MGL{produto.id}5544',
                        status_anuncio='ativo',
                        preco_sincronizado=preco
                    )
                    total_anuncios_criados += 3

        return {
            'sucesso': True,
            'lojas_criadas': len(lojas_especificacao),
            'produtos_criados': total_produtos_criados,
            'anuncios_criados': total_anuncios_criados,
        }
