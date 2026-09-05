# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

try:
    from apps.tenancy.models import Loja, PerfilUsuario, ModuloLoja, ModuloSistemaEnum
    from apps.catalogo.models import Categoria, Produto, AnuncioMarketplace
    from apps.marketplaces.models import ContaMarketplace, CanalMarketplaceEnum
    from apps.financeiro.models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace
except ImportError:
    from core.models import (
        Loja, PerfilUsuario, Categoria, Produto,
        ConfiguracaoTaxasLoja, ParametroCanalMarketplace
    )
    ModuloLoja = None
    ContaMarketplace = None
    AnuncioMarketplace = None


class Command(BaseCommand):
    """
    O QUE FAZ: Popula uma base de dados completa multi-tenant com usuários DEV dedicados, 
               lojas com endereços reais, configurações fiscais/comissões, produtos e anúncios.
    POR QUE FAZ: Permite testes funcionais locais e em novos ambientes com idempotência e dados consistentes.
    PERMISSÕES RBAC: Cria DEV (global), ADMIN (gestão da loja), SUPERVISOR e OPERADOR.
    """
    help = "Popula o banco com time de DEVs, 3 tenants, produtos e anúncios em marketplaces."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Iniciando seed de dados de teste..."))

        # 1. Usuários DEV Globais
        dev_usernames = ["oscar", "allan", "davidson", "vando", "rafael", "guilherme"]
        senha_padrao_dev = "admin12345"

        for dev_login in dev_usernames:
            u, _ = User.objects.get_or_create(
                username=dev_login,
                defaults={
                    "email": f"{dev_login}@hub.local",
                    "is_staff": True,
                    "is_superuser": True
                }
            )
            u.set_password(senha_padrao_dev)
            u.save()

            PerfilUsuario.objects.update_or_create(
                usuario=u,
                defaults={"papel": "DEV", "loja": None}
            )
            self.stdout.write(self.style.SUCCESS(f"✓ DEV criado: {dev_login} (senha: {senha_padrao_dev})"))

        # 2. Tenants (Lojas)
        tenants_data = [
            {
                "slug": "loja-eletronicos",
                "nome": "TechZone Eletrônicos",
                "dados": {
                    "razao_social": "TechZone Distribuidora de Eletrônicos LTDA",
                    "cnpj": "12.345.678/0001-90",
                    "inscricao_estadual": "110.220.330.440",
                    "telefone": "(11) 3100-2000",
                    "email_contato": "contato@techzone.com.br",
                    "logradouro": "Av. Brigadeiro Faria Lima",
                    "numero": "1811",
                    "complemento": "Andar 5, Sala 52",
                    "bairro": "Pinheiros",
                    "cidade": "São Paulo",
                    "uf": "SP",
                    "cep": "01452-001",
                },
                "taxas": {
                    "imposto": Decimal("6.00"),
                    "embalagem": Decimal("3.00"),
                    "seguranca": Decimal("8.00"),
                    "custos_fixos": Decimal("4500.00")
                },
                "admin": "admin_tech",
                "supervisor": "super_tech",
                "operador": "user_tech",
            },
            {
                "slug": "loja-cama-mesa-banho",
                "nome": "Comfort Cama, Mesa & Banho",
                "dados": {
                    "razao_social": "Comfort Têxtil e Lar EIRELI",
                    "cnpj": "23.456.789/0001-01",
                    "inscricao_estadual": "220.330.440.550",
                    "telefone": "(47) 3320-1000",
                    "email_contato": "vendas@comfortcasa.com.br",
                    "logradouro": "Rua XV de Novembro",
                    "numero": "750",
                    "complemento": "Galpão A",
                    "bairro": "Centro",
                    "cidade": "Blumenau",
                    "uf": "SC",
                    "cep": "89010-001",
                },
                "taxas": {
                    "imposto": Decimal("4.50"),
                    "embalagem": Decimal("4.00"),
                    "seguranca": Decimal("5.00"),
                    "custos_fixos": Decimal("3200.00")
                },
                "admin": "admin_comfort",
                "supervisor": "super_comfort",
                "operador": "user_comfort",
            },
            {
                "slug": "loja-calcados",
                "nome": "Passo Firme Calçados",
                "dados": {
                    "razao_social": "Passo Firme Manufatura de Calçados LTDA",
                    "cnpj": "34.567.890/0001-12",
                    "inscricao_estadual": "330.440.550.660",
                    "telefone": "(16) 3711-5000",
                    "email_contato": "comercial@passofirme.com.br",
                    "logradouro": "Av. Presidente Vargas",
                    "numero": "2100",
                    "complemento": "Loja 03",
                    "bairro": "Cidade Nova",
                    "cidade": "Franca",
                    "uf": "SP",
                    "cep": "14401-110",
                },
                "taxas": {
                    "imposto": Decimal("5.00"),
                    "embalagem": Decimal("3.50"),
                    "seguranca": Decimal("6.00"),
                    "custos_fixos": Decimal("2800.00")
                },
                "admin": "admin_calcados",
                "supervisor": "super_calcados",
                "operador": "user_calcados",
            },
        ]

        # 3. Catálogo por Loja
        catalogo_data = {
            "loja-eletronicos": {
                "categoria": ("Periféricos e Informática", "perifericos-informatica"),
                "produtos": [
                    {
                        "sku": "ELET-MOU-01",
                        "nome": "Mouse Gamer Óptico Wireless RGB 16000 DPI",
                        "descricao": "Mouse gamer ergonômico sem fio com bateria recarregável.",
                        "preco": Decimal("129.90"),
                        "estoque": 85,
                        "custo_aquisicao": Decimal("52.00"),
                        "custo_embalagem": Decimal("2.50"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "ELET-TECL-02",
                        "nome": "Teclado Mecânico Compacto Switch Blue ABNT2",
                        "descricao": "Teclado mecânico gamer formato 60% com switches azuis táteis.",
                        "preco": Decimal("249.90"),
                        "estoque": 40,
                        "custo_aquisicao": Decimal("115.00"),
                        "custo_embalagem": Decimal("4.00"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "ELET-HEAD-03",
                        "nome": "Headset Gamer Surround 7.1 Cancelamento Ruído",
                        "descricao": "Headset over-ear acolchoado com drivers de 50mm e som imersivo.",
                        "preco": Decimal("189.00"),
                        "estoque": 60,
                        "custo_aquisicao": Decimal("82.00"),
                        "custo_embalagem": Decimal("3.50"),
                        "modalidade_full": True,
                    },
                    {
                        "sku": "ELET-CABO-04",
                        "nome": "Cabo USB-C em Nylon Trançado 2m 60W Turbo",
                        "descricao": "Cabo de carregamento rápido com blindagem em alumínio.",
                        "preco": Decimal("39.90"),
                        "estoque": 200,
                        "custo_aquisicao": Decimal("9.50"),
                        "custo_embalagem": Decimal("1.20"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "ELET-HUB-05",
                        "nome": "Hub Adaptador USB-C 7 em 1 HDMI 4K PD 100W",
                        "descricao": "Hub multifuncional com HDMI 4K, leitor SD e USB 3.0.",
                        "preco": Decimal("159.90"),
                        "estoque": 50,
                        "custo_aquisicao": Decimal("68.00"),
                        "custo_embalagem": Decimal("2.00"),
                        "modalidade_full": False,
                    },
                ],
            },
            "loja-cama-mesa-banho": {
                "categoria": ("Cama, Mesa e Banho", "cama-mesa-banho"),
                "produtos": [
                    {
                        "sku": "CASA-JLEN-01",
                        "nome": "Jogo de Lençol Casal Queen 4 Peças Percal 200 Fios",
                        "descricao": "Conjunto 100% algodão contendo lençol com elástico e fronhas macias.",
                        "preco": Decimal("169.90"),
                        "estoque": 70,
                        "custo_aquisicao": Decimal("78.00"),
                        "custo_embalagem": Decimal("4.50"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "CASA-JTOA-02",
                        "nome": "Jogo de Toalhas 5 Peças Banhão Fio Penteado",
                        "descricao": "Toalhas felpudas 500g/m²: 2 banho, 2 rosto e 1 piso.",
                        "preco": Decimal("139.90"),
                        "estoque": 90,
                        "custo_aquisicao": Decimal("60.00"),
                        "custo_embalagem": Decimal("3.80"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "CASA-EDR-03",
                        "nome": "Edredom Dupla Face Queen Toque de Pluma",
                        "descricao": "Edredom térmico macio com manta interna antialérgica.",
                        "preco": Decimal("229.00"),
                        "estoque": 35,
                        "custo_aquisicao": Decimal("105.00"),
                        "custo_embalagem": Decimal("6.00"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "CASA-TRAV-04",
                        "nome": "Travesseiro Cervical Viscoelástico Nasa Capa Lavável",
                        "descricao": "Travesseiro de sustentação anatômica em espuma com memória.",
                        "preco": Decimal("79.90"),
                        "estoque": 110,
                        "custo_aquisicao": Decimal("31.00"),
                        "custo_embalagem": Decimal("2.50"),
                        "modalidade_full": True,
                    },
                    {
                        "sku": "CASA-PANOP-05",
                        "nome": "Kit 10 Panos de Prato Atoalhados com Barrado Estampado",
                        "descricao": "Panos de prato em algodão cru de alta absorção.",
                        "preco": Decimal("49.90"),
                        "estoque": 150,
                        "custo_aquisicao": Decimal("18.00"),
                        "custo_embalagem": Decimal("1.80"),
                        "modalidade_full": False,
                    },
                ],
            },
            "loja-calcados": {
                "categoria": ("Calçados e Acessórios", "calcados-acessorios"),
                "produtos": [
                    {
                        "sku": "CALC-TEN-01",
                        "nome": "Tênis Esportivo Running Amortecimento em Gel",
                        "descricao": "Tênis leve e respirável para corridas de média distância.",
                        "preco": Decimal("199.90"),
                        "estoque": 65,
                        "custo_aquisicao": Decimal("88.00"),
                        "custo_embalagem": Decimal("4.00"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "CALC-SAPA-02",
                        "nome": "Sapato Social Masculino em Couro Legítimo Derby",
                        "descricao": "Sapato executivo solado colado com acabamento polido.",
                        "preco": Decimal("259.00"),
                        "estoque": 45,
                        "custo_aquisicao": Decimal("120.00"),
                        "custo_embalagem": Decimal("4.50"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "CALC-BOTA-03",
                        "nome": "Bota Coturno Feminina Cano Médio Tratorada",
                        "descricao": "Coturno casual com zíper lateral para ajuste prático.",
                        "preco": Decimal("179.90"),
                        "estoque": 55,
                        "custo_aquisicao": Decimal("75.00"),
                        "custo_embalagem": Decimal("4.00"),
                        "modalidade_full": False,
                    },
                    {
                        "sku": "CALC-SAND-04",
                        "nome": "Sandália Feminina Anabela Salto Corda Espadrille",
                        "descricao": "Sandália com plataforma de corda e tira macia.",
                        "preco": Decimal("119.90"),
                        "estoque": 80,
                        "custo_aquisicao": Decimal("46.00"),
                        "custo_embalagem": Decimal("3.00"),
                        "modalidade_full": True,
                    },
                    {
                        "sku": "CALC-CHIN-05",
                        "nome": "Chinelo Slide Anatômico Nuvem Antiderrapante",
                        "descricao": "Chinelo unissex ultra leve em EVA de densidade suave.",
                        "preco": Decimal("59.90"),
                        "estoque": 140,
                        "custo_aquisicao": Decimal("21.00"),
                        "custo_embalagem": Decimal("2.00"),
                        "modalidade_full": False,
                    },
                ],
            },
        }

        # 4. Parâmetros Comerciais dos Marketplaces
        canais_marketplace = [
            ("mercadolivre_classico", "Mercado Livre Clássico", Decimal("12.00"), Decimal("79.00"), Decimal("18.45"), Decimal("6.00")),
            ("mercadolivre_premium", "Mercado Livre Premium", Decimal("17.00"), Decimal("79.00"), Decimal("18.45"), Decimal("6.00")),
            ("shopee", "Shopee Brasil", Decimal("14.00"), Decimal("50.00"), Decimal("13.00"), Decimal("4.00")),
            ("magalu", "Magalu Marketplace", Decimal("16.00"), Decimal("79.00"), Decimal("16.90"), Decimal("5.00")),
        ]

        # 5. Processamento dos Tenants
        for t_info in tenants_data:
            loja, _ = Loja.objects.get_or_create(
                slug=t_info["slug"],
                defaults={
                    "nome": t_info["nome"],
                    "ativo": True,
                    **{k: v for k, v in t_info["dados"].items() if hasattr(Loja, k)}
                }
            )

            if ModuloLoja:
                for mod_slug in ["catalogo", "pedidos", "marketplaces", "financeiro"]:
                    ModuloLoja.objects.update_or_create(
                        loja=loja,
                        modulo=mod_slug,
                        defaults={"ativo": True}
                    )

            papeis_loja = [
                (t_info["admin"], "ADMIN"),
                (t_info["supervisor"], "SUPERVISOR"),
                (t_info["operador"], "USUARIO"),
            ]
            for u_nome, papel in papeis_loja:
                u, _ = User.objects.get_or_create(
                    username=u_nome,
                    defaults={
                        "email": f"{u_nome}@hub.local",
                        "is_staff": False,
                        "is_superuser": False
                    }
                )
                u.set_password("senha123")
                u.save()

                PerfilUsuario.objects.update_or_create(
                    usuario=u,
                    defaults={"papel": papel, "loja": loja}
                )

            ConfiguracaoTaxasLoja.objects.update_or_create(
                loja=loja,
                defaults={
                    "aliquota_imposto": t_info["taxas"]["imposto"],
                    "custo_embalagem_padrao": t_info["taxas"]["embalagem"],
                    "margem_minima_seguranca": t_info["taxas"]["seguranca"],
                    "custos_fixos_mensais": t_info["taxas"]["custos_fixos"],
                }
            )

            for mkt_slug, _, comissao, piso, frete_acima, taxa_abaixo in canais_marketplace:
                ParametroCanalMarketplace.objects.update_or_create(
                    loja=loja,
                    marketplace=mkt_slug,
                    defaults={
                        "comissao_padrao": comissao,
                        "frete_gratis_piso": piso,
                        "taxa_frete_acima_limite": frete_acima,
                        "taxa_fixa_abaixo_limite": taxa_abaixo,
                    }
                )

            contas_conectadas = {}
            if ContaMarketplace:
                for canal_key, canal_label in [("mercadolivre", "Mercado Livre"), ("shopee", "Shopee"), ("magalu", "Magalu")]:
                    conta, _ = ContaMarketplace.objects.update_or_create(
                        loja=loja,
                        canal=canal_key,
                        seller_id_externo=f"SELLER-{loja.slug.upper()}-{canal_key[:3].upper()}",
                        defaults={
                            "apelido_conta": f"{loja.nome} ({canal_label})",
                            "ativo": True,
                            "access_token": f"token_mock_{canal_key}_{loja.id}_xyz",
                            "refresh_token": f"refresh_mock_{canal_key}_{loja.id}_abc",
                        }
                    )
                    contas_conectadas[canal_key] = conta

            cat_nome, cat_slug = catalogo_data[loja.slug]["categoria"]
            categoria, _ = Categoria.objects.update_or_create(
                loja=loja,
                slug=f"{cat_slug}-{loja.id}",
                defaults={"nome": cat_nome}
            )

            for p_dict in catalogo_data[loja.slug]["produtos"]:
                produto, _ = Produto.objects.update_or_create(
                    loja=loja,
                    sku=p_dict["sku"],
                    defaults={
                        "categoria": categoria,
                        "nome": p_dict["nome"],
                        "descricao": p_dict["descricao"],
                        "preco": p_dict["preco"],
                        "estoque": p_dict["estoque"],
                        "custo_aquisicao": p_dict["custo_aquisicao"],
                        "custo_embalagem": p_dict["custo_embalagem"],
                        "modalidade_full": p_dict["modalidade_full"],
                        "status": "ativo"
                    }
                )

                if AnuncioMarketplace and contas_conectadas:
                    for canal_key, conta_obj in contas_conectadas.items():
                        prefixo = "MLB" if canal_key == "mercadolivre" else ("SHP" if canal_key == "shopee" else "MGL")
                        AnuncioMarketplace.objects.update_or_create(
                            produto=produto,
                            conta_marketplace=conta_obj,
                            defaults={
                                "item_id_externo": f"{prefixo}-{produto.sku}",
                                "status_anuncio": "ativo",
                                "preco_sincronizado": produto.preco,
                                "link_anuncio": f"https://www.{canal_key}.com.br/item/{prefixo}-{produto.sku}"
                            }
                        )

            self.stdout.write(self.style.SUCCESS(f"✓ {loja.nome}: 5 produtos e integrações criados."))

        self.stdout.write(self.style.SUCCESS("\n🎉 Base multi-tenant populada com sucesso!"))
