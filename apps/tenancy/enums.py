# Os códigos foram gerados com auxilio de I.A.
from django.db import models


class PapelUsuarioEnum(models.TextChoices):
    """
    O QUE FAZ: Enumeração dos papéis de acesso do modelo RBAC (Role-Based Access Control).
    POR QUE FAZ: Centraliza e padroniza as constantes de perfil de usuário (DEV, ADMIN, SUPERVISOR, USUARIO), garantindo integridade referencial e facilidade de extensão.
    PERMISSÕES RBAC: DEV (Global), ADMIN (Loja), SUPERVISOR (Intermediário Loja), USUARIO (Restrito Loja).
    MULTI-TENANCY: DEV atua globalmente; os demais papéis são restritos ao escopo da loja vinculada.
    """
    DEV = 'DEV', 'Desenvolvedor (DEV) — Escopo Global'
    ADMIN = 'ADMIN', 'Administrador da Loja (ADMIN)'
    SUPERVISOR = 'SUPERVISOR', 'Supervisor da Loja (SUPERVISOR)'
    USUARIO = 'USUARIO', 'Usuário Padrão da Loja (USUÁRIO)'


class ModuloSistemaEnum(models.TextChoices):
    """
    O QUE FAZ: Enumeração dos módulos funcionais controlados por feature flags por tenant.
    POR QUE FAZ: Permite que cada Loja contrate ou tenha ativado individualmente os módulos do sistema (Catálogo, Pedidos, Marketplaces, Financeiro).
    PERMISSÕES RBAC: DEV pode ativar/desativar módulos; os demais perfis consomem os módulos conforme ativação.
    MULTI-TENANCY: Cada tenant possui seu próprio conjunto de módulos habilitados.
    """
    CATALOGO = 'catalogo', 'Gestão de Catálogo e Produtos'
    PEDIDOS = 'pedidos', 'Vendas e Pedidos Multicanal'
    MARKETPLACES = 'marketplaces', 'Hub de Conectores de Marketplaces'
    FINANCEIRO = 'financeiro', 'Motor de Inteligência Financeira'
