# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo models do Django para permitir o uso de TextChoices em enumerações de banco
from django.db import models


# Declaração do enum textual que padroniza os níveis hierárquicos do modelo de governança RBAC
class PapelUsuarioEnum(models.TextChoices):
    # Início do bloco de docstring que documenta os papéis, escopo hierárquico e fronteiras multi-tenant
    """
    O QUE FAZ: Enumeração dos papéis de acesso do modelo RBAC (Role-Based Access Control).
    POR QUE FAZ: Centraliza e padroniza as constantes de perfil de usuário (DEV, ADMIN, SUPERVISOR, USUARIO), garantindo integridade referencial e facilidade de extensão.
    PERMISSÕES RBAC: DEV (Global), ADMIN (Loja), SUPERVISOR (Intermediário Loja), USUARIO (Restrito Loja).
    MULTI-TENANCY: DEV atua globalmente; os demais papéis são restritos ao escopo da loja vinculada.
    """
    # Fim do bloco de docstring informativa

    # Constante para o desenvolvedor mestre com privilégios irrestritos e acesso transversal a todos os tenants
    DEV = 'DEV', 'Desenvolvedor (DEV) — Escopo Global'

    # Constante para o administrador da organização lojista com gestão completa no escopo do seu tenant
    ADMIN = 'ADMIN', 'Administrador da Loja (ADMIN)'

    # Constante para o supervisor com privilégios operacionais avançados e controle de equipe dentro da loja
    SUPERVISOR = 'SUPERVISOR', 'Supervisor da Loja (SUPERVISOR)'

    # Constante para o usuário operacional comum com permissões restritas às rotinas diárias da loja
    USUARIO = 'USUARIO', 'Usuário Padrão da Loja (USUÁRIO)'


# Declaração do enum textual que mapeia os módulos funcionais comercializáveis e ativáveis por loja
class ModuloSistemaEnum(models.TextChoices):
    # Início do bloco de docstring estrutural documentando os módulos e a gestão de feature flags por tenant
    """
    O QUE FAZ: Enumeração dos módulos funcionais controlados por feature flags por tenant.
    POR QUE FAZ: Permite que cada Loja contrate ou tenha ativado individualmente os módulos do sistema (Catálogo, Pedidos, Marketplaces, Financeiro).
    PERMISSÕES RBAC: DEV pode ativar/desativar módulos; os demais perfis consomem os módulos conforme ativação.
    MULTI-TENANCY: Cada tenant possui seu próprio conjunto de módulos habilitados.
    """
    # Fim da docstring explicativa

    # Módulo de cadastro, manutenção física de SKUs, estoque interno e composições (Kits/Combos)
    CATALOGO = 'catalogo', 'Gestão de Catálogo e Produtos'

    # Módulo de ingestão assíncrona de vendas, reconciliação de pedidos e baixa atômica de estoque
    PEDIDOS = 'pedidos', 'Vendas e Pedidos Multicanal'

    # Módulo de credenciamento, gestão de contas e conectores com canais externos (ML, Shopee, Magalu, Amazon)
    MARKETPLACES = 'marketplaces', 'Hub de Conectores de Marketplaces'

    # Módulo de precificação dinâmica, parâmetros fiscais por canal, custos e margem de segurança
    FINANCEIRO = 'financeiro', 'Motor de Inteligência Financeira'