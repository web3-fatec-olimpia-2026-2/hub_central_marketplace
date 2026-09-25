# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta os objetivos do serviço, garantias atômicas e regras de ambiente
"""
O QUE FAZ: Serviço atômico para provisionamento, substituição e exclusão de dados mockados de teste.
POR QUE FAZ: Permite ao desenvolvedor/testador popular ou limpar a base de dados de demonstração com um único clique.
REGRAS DE SEGURANÇA E AMBIENTE:
- Executado sob transação atômica (transaction.atomic).
- O usuário DEV mestre (devmaster) é estritamente preservado e NUNCA é excluído ou alterado.
- Utiliza máscaras de CNPJ e telefones anticoincidência sintéticos (11.111.111/0001-11, etc.).
- Metade dos produtos gerados recebe status RASCUNHO e a outra metade ATIVO.
"""
# Fim do bloco de docstring estrutural

# Importa a classe Decimal para definição e cálculos de valores monetários e alíquotas fiscais com precisão exata
from decimal import Decimal

# Importa o gerenciador de transações atômicas para garantir rollback automático em caso de exceções
from django.db import transaction

# Importa o modelo nativo de usuários do Django
from django.contrib.auth.models import User

# Importa os modelos Loja e PerfilUsuario do aplicativo de governança multi-tenant
from apps.tenancy.models import Loja, PerfilUsuario

# Importa as enumerações de papéis de usuários (RBAC) e módulos estruturais do sistema
from apps.tenancy.enums import PapelUsuarioEnum, ModuloSistemaEnum

# Importa as entidades estruturais do catálogo de produtos e anúncios
from apps.catalogo.models import Categoria, Produto, AnuncioMarketplace

# Importa o enum de ciclo de vida e publicação cadastral de produtos
from apps.catalogo.enums import StatusProdutoEnum

# Importa o modelo que materializa as credenciais de integrações com marketplaces
from apps.marketplaces.models import ContaMarketplace

# Importa o enum com a relação canônica de canais parceiros integrados
from apps.marketplaces.enums import CanalMarketplaceEnum

# Importa os modelos de configurações fiscais e precificação por canal da aplicação financeira
from apps.financeiro.models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace

# Importa as funções para resolução dinâmica das credenciais seguras do usuário desenvolvedor
from .conf import (
    get_dev_debug_username,
    get_dev_debug_password,
    get_dev_debug_email,
)


# Função responsável por provisionar ou atualizar de forma idempotente o superusuário de desenvolvimento
def garantir_usuario_devmaster():
    # Início do bloco de docstring que documenta as salvaguardas de ambiente do provisionamento de devmaster
    """
    O QUE FAZ: Garante a existência do usuário DEV mestre no banco de dados com as credenciais do .env/settings.
    POR QUE FAZ: Inicializa e sincroniza o superusuário de testes sem senhas estáticas no código-fonte.
    REGRAS DE SEGURANÇA E AMBIENTE:
    - Executa APENAS quando settings.DEBUG=True e settings.LOGIN_DEBUG=True.
    - Atualiza a senha no banco se a variável LOGIN_DEBUG_PASSWORD for alterada no .env.
    - Garante os privilégios de superuser e vínculo de PerfilUsuario com papel DEV.
    """
    # Fim da docstring explicativa

    # Importa as configurações do Django
    from django.conf import settings

    # Trava de segurança: impede execução caso DEBUG ou LOGIN_DEBUG não estejam ambos ativos
    if not (getattr(settings, 'DEBUG', False) and getattr(settings, 'LOGIN_DEBUG', False)):
        return None

    # Resolve dinamicamente as credenciais a partir do settings/.env
    username = get_dev_debug_username()
    password = get_dev_debug_password()
    email = get_dev_debug_email()

    # Se o nome de usuário não foi definido, aborta a rotina
    if not username:
        return None

    # Cria o usuário caso não exista, com flags de superusuário e staff ativas
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
        }
    )

    alterou = False
    # Atualiza o e-mail caso tenha divergido da configuração
    if email and user.email != email:
        user.email = email
        alterou = True

    # Assegura que o usuário possua privilégios administrativos totais
    if not user.is_staff or not user.is_superuser or not user.is_active:
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        alterou = True

    # Atualiza o hash da senha caso o usuário seja novo ou a senha tenha sido alterada nas variáveis de ambiente
    if password and (created or not user.check_password(password)):
        user.set_password(password)
        alterou = True

    # Persiste as alterações no modelo User se houver mutações
    if alterou:
        user.save()

    # Garante a existência do PerfilUsuario com papel DEV sem vínculo de loja (acesso global ao SaaS)
    perfil, _ = PerfilUsuario.objects.get_or_create(
        usuario=user,
        defaults={
            'papel': PapelUsuarioEnum.DEV,
            'loja': None,
        }
    )
    # Se o papel ou o isolamento de loja estiverem incorretos, restaura o privilégio mestre de DEV
    if perfil.papel != PapelUsuarioEnum.DEV or perfil.loja is not None:
        perfil.papel = PapelUsuarioEnum.DEV
        perfil.loja = None
        perfil.save()

    # Retorna o usuário devmaster configurado
    return user


# Função utilitária que avalia se a simulação de respostas bem-sucedidas em contas mockadas está ativa
def is_simular_rotas_mock_ativo(request=None) -> bool:
    # Início do bloco de docstring que documenta a ordem de precedência da feature flag
    """
    O QUE FAZ: Verifica se a feature flag SIMULAR_ROTAS_MOCK está habilitada.
    POR QUE FAZ: Controla se as ações em contas mockadas retornam sucesso simulado (HTTP 200) ou recusa (HTTP 401).
    PRIORIDADE: request.session['SIMULAR_ROTAS_MOCK'] > settings.SIMULAR_ROTAS_MOCK > True.
    """
    # Fim da docstring informativa

    # Importa as configurações globais
    from django.conf import settings

    # Checa precedência primária: valor explicitamente gravado na sessão web do usuário
    if request and hasattr(request, 'session'):
        val = request.session.get('SIMULAR_ROTAS_MOCK')
        if val is not None:
            return bool(val)
    # Precedência secundária: configuração estática do projeto Django (padrão True)
    return getattr(settings, 'SIMULAR_ROTAS_MOCK', True)


# Função para alternar o estado booleano da feature flag de simulação mock na sessão do operador
def alternar_simulacao_mock(request) -> bool:
    # Início da docstring descritiva
    """
    O QUE FAZ: Inverte o estado da flag SIMULAR_ROTAS_MOCK na sessão do usuário.
    POR QUE FAZ: Permite alternar rapidamente entre modo Simulado e modo Recusa (HTTP 401) pela interface.
    """
    # Fim do bloco descritivo

    # Obtém o estado corrente
    atual = is_simular_rotas_mock_ativo(request)
    # Inverte o estado lógico
    novo = not atual
    # Persiste na sessão da requisição atual caso disponível
    if request and hasattr(request, 'session'):
        request.session['SIMULAR_ROTAS_MOCK'] = novo
    return novo


# Classe de serviço agrupando as operações de ciclo de vida (criação, contagem e limpeza) dos dados de teste
class MockDataService:
    # Início do bloco de docstring da classe
    """
    Serviço centralizado de gestão de dados sintéticos para testes e desenvolvimento.
    """
    # Fim da documentação da classe

    # Slugs exclusivos que identificam as lojas sintéticas no banco de dados
    MOCK_SLUGS = ['techzone-mock', 'comfort-mock', 'passofirme-mock']

    # Máscaras de CNPJ sintéticos para garantir não colisão com entidades fiscais reais
    MOCK_CNPJS = ['11.111.111/0001-11', '22.222.222/0001-22', '33.333.333/0001-33']

    # Lista canônica dos nomes de usuários de teste criados para simulação dos papéis RBAC
    MOCK_USERNAMES = [
        'admin_techzone', 'sup_techzone', 'user_techzone',
        'admin_comfort', 'sup_comfort', 'user_comfort',
        'admin_passofirme', 'sup_passofirme', 'user_passofirme',
    ]

    # Verifica se já existem lojas de teste cadastradas na base
    @classmethod
    def tem_dados_mockados(cls) -> bool:
        """
        Verifica se existem lojas mockadas registradas no banco de dados.
        """
        return Loja.objects.filter(slug__in=cls.MOCK_SLUGS).exists()

    # Totaliza a quantidade de entidades pertencentes às lojas de teste registradas
    @classmethod
    def contar_registros_mockados(cls) -> dict:
        """
        Retorna o quantitativo atual de entidades mockadas no sistema.
        """
        # Recupera as lojas mockadas e extrai seus IDs
        lojas = Loja.objects.filter(slug__in=cls.MOCK_SLUGS)
        lojas_ids = list(lojas.values_list('id', flat=True))

        # Retorna dicionário quantitativo consolidado por modelo
        return {
            'lojas': lojas.count(),
            'produtos': Produto.objects.filter(loja_id__in=lojas_ids).count(),
            'categorias': Categoria.objects.filter(loja_id__in=lojas_ids).count(),
            'contas_marketplace': ContaMarketplace.objects.filter(loja_id__in=lojas_ids).count(),
            'anuncios': AnuncioMarketplace.objects.filter(produto__loja_id__in=lojas_ids).count(),
            'usuarios': User.objects.filter(username__in=cls.MOCK_USERNAMES).count(),
        }

    # Remove de maneira transacional todos os registros de teste, preservando o usuário devmaster
    @classmethod
    @transaction.atomic
    def excluir_dados_mockados(cls) -> dict:
        """
        Exclui permanentemente todos os registros sintéticos criados para teste.
        Garante expressamente a preservação do usuário devmaster.
        """
        # 1. Localiza as lojas mockadas
        # Busca todas as lojas identificadas pelos slugs de teste
        lojas = Loja.objects.filter(slug__in=cls.MOCK_SLUGS)
        qtd_lojas = lojas.count()
        lojas_ids = list(lojas.values_list('id', flat=True))

        # Se houver lojas mockadas presentes na base
        if qtd_lojas > 0:
            # Exclui dependências em ordem reversa para respeitar FKs com on_delete=PROTECT (ex: Produto -> Categoria)
            # Exclui anúncios vinculados aos produtos das lojas mockadas
            AnuncioMarketplace.objects.filter(produto__loja_id__in=lojas_ids).delete()
            # Exclui os produtos físicos do catálogo
            Produto.objects.filter(loja_id__in=lojas_ids).delete()
            # Exclui as categorias cadastrais
            Categoria.objects.filter(loja_id__in=lojas_ids).delete()
            # Exclui as contas de marketplaces conectadas
            ContaMarketplace.objects.filter(loja_id__in=lojas_ids).delete()
            # Exclui configurações fiscais da loja
            ConfiguracaoTaxasLoja.objects.filter(loja_id__in=lojas_ids).delete()
            # Exclui parâmetros de comissões e fretes por canal
            ParametroCanalMarketplace.objects.filter(loja_id__in=lojas_ids).delete()
            # Exclui as próprias organizações Loja
            lojas.delete()

        # 2. Exclui os usuários mockados secundários (NUNCA devmaster)
        # Recupera o username do superusuário de testes para proteção estrita
        dev_username = get_dev_debug_username()
        # Filtra os usuários mockados excluindo categoricamente o usuário devmaster
        usuarios_para_excluir = User.objects.filter(
            username__in=cls.MOCK_USERNAMES
        ).exclude(username=dev_username)
        qtd_usuarios = usuarios_para_excluir.count()
        usuarios_para_excluir.delete()

        # Retorna sumário dos registros removidos
        return {
            'sucesso': True,
            'lojas_excluidas': qtd_lojas,
            'usuarios_excluidos': qtd_usuarios,
        }

    # Gera a massa integral de dados sintéticos para testes locais
    @classmethod
    @transaction.atomic
    def gerar_dados_mockados(cls) -> dict:
        """
        Gera ou substitui o conjunto completo de dados sintéticos de teste.
        """
        # 1. Limpa registros mockados pré-existentes para garantir padrão de fábrica
        # Remove dados anteriores para evitar duplicações de constraints únicas
        cls.excluir_dados_mockados()

        # 2. Assegura a existência do DEV Master intacto com credenciais do .env
        # Garante a existência do usuário desenvolvedor
        garantir_usuario_devmaster()

        # 3. Definição das 3 Lojas Mockadas
        # Especificação completa da Loja 1 (Eletrônicos), Loja 2 (Cama, Mesa e Banho) e Loja 3 (Calçados)
        lojas_especificacao = [
            # Estrutura e dados da Loja 1: TechZone
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
            # Estrutura e dados da Loja 2: Comfort
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
            # Estrutura e dados da Loja 3: Passo Firme
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

        # Contadores de controle
        total_produtos_criados = 0
        total_anuncios_criados = 0

        # Itera provisionando cada loja especificada
        for spec in lojas_especificacao:
            # A. Criação da Loja
            # Cria a entidade tenant com dados cadastrais e fiscais sintéticos
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
            # Habilita os módulos padrões para o novo tenant
            loja.garantir_modulos_padrao()

            # B. Criação dos Parâmetros Fiscais da Loja
            # Registra as taxas operacionais, impostos e margens de lucro padrão da loja
            ConfiguracaoTaxasLoja.objects.create(
                loja=loja,
                aliquota_imposto=spec['taxas']['aliquota_imposto'],
                custo_embalagem_padrao=spec['taxas']['custo_embalagem_padrao'],
                margem_minima_seguranca=spec['taxas']['margem_minima_seguranca'],
                custos_fixos_mensais=spec['taxas']['custos_fixos_mensais']
            )

            # C. Criação dos Parâmetros dos Canais
            # Define as regras de comissão, frete grátis e custos fixos para precificação automatizada
            canais_params = [
                ('mercadolivre_classico', Decimal('0.1200'), Decimal('79.00'), Decimal('18.00'), Decimal('6.00')),
                ('mercadolivre_premium', Decimal('0.1700'), Decimal('79.00'), Decimal('18.00'), Decimal('6.00')),
                ('shopee', Decimal('0.1400'), Decimal('50.00'), Decimal('14.00'), Decimal('4.00')),
                ('magalu', Decimal('0.1600'), Decimal('79.00'), Decimal('16.00'), Decimal('5.00')),
            ]
            # Persiste os parâmetros financeiros para cada marketplace suportado
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
            # Cria operadores para testes com senhas padronizadas e perfis com papéis RBAC específicos
            for username, nome_completo, papel in spec['usuarios']:
                user_obj = User.objects.create_user(
                    username=username,
                    email=f'{username}@mock.local',
                    password='password123',
                    first_name=nome_completo.split()[0],
                    last_name=' '.join(nome_completo.split()[1:]) if len(nome_completo.split()) > 1 else ''
                )
                # Vincula o usuário criado ao perfil da loja atual
                PerfilUsuario.objects.create(
                    usuario=user_obj,
                    papel=papel,
                    loja=loja
                )

            # E. Criação de Contas de Marketplace para a Loja
            # Cria conta simulada do Mercado Livre
            conta_ml = ContaMarketplace.objects.create(
                loja=loja,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                apelido_conta=f'ML - {loja.nome[:15]}',
                seller_id_externo=f'ML_{spec["cnpj"][:8]}',
                access_token=f'MOCK_TOKEN_ML_{loja.id}',
                ativo=True,
                is_mock=True
            )
            # Cria conta simulada da Shopee
            conta_shopee = ContaMarketplace.objects.create(
                loja=loja,
                canal=CanalMarketplaceEnum.SHOPEE,
                apelido_conta=f'Shopee - {loja.nome[:15]}',
                seller_id_externo=f'SHP_{spec["cnpj"][:8]}',
                access_token=f'MOCK_TOKEN_SHP_{loja.id}',
                ativo=True,
                is_mock=True
            )
            # Cria conta simulada do Magazine Luiza
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
            # Cria a categoria departamental padrão da loja
            categoria = Categoria.objects.create(
                loja=loja,
                nome=spec['categoria_nome'],
                slug=spec['categoria_slug'],
                descricao=f'Categoria principal para a {loja.nome}'
            )

            # G. Criação dos Produtos e Anúncios Multicanal
            # Itera cadastrando produtos físicos especificados para a loja
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
                # Para produtos que estão ativos no catálogo, cria anúncios vinculados aos 3 canais integrados
                if status == StatusProdutoEnum.ATIVO:
                    # Anúncio no Mercado Livre
                    AnuncioMarketplace.objects.create(
                        produto=produto,
                        conta_marketplace=conta_ml,
                        item_id_externo=f'MLB{produto.id}9988',
                        status_anuncio='ativo',
                        preco_sincronizado=preco
                    )
                    # Anúncio na Shopee
                    AnuncioMarketplace.objects.create(
                        produto=produto,
                        conta_marketplace=conta_shopee,
                        item_id_externo=f'SHP{produto.id}7766',
                        status_anuncio='ativo',
                        preco_sincronizado=preco
                    )
                    # Anúncio no Magazine Luiza
                    AnuncioMarketplace.objects.create(
                        produto=produto,
                        conta_marketplace=conta_magalu,
                        item_id_externo=f'MGL{produto.id}5544',
                        status_anuncio='ativo',
                        preco_sincronizado=preco
                    )
                    total_anuncios_criados += 3

        # Retorna o sumário da operação de geração dos dados sintéticos
        return {
            'sucesso': True,
            'lojas_criadas': len(lojas_especificacao),
            'produtos_criados': total_produtos_criados,
            'anuncios_criados': total_anuncios_criados,
        }
