from django.db import models


class PapelUsuarioEnum(models.TextChoices):
    """
    Papéis de acesso RBAC no sistema.
    Isolados neste enum para facilitar a extensão com novos perfis (ex.: OPERADOR, FINANCEIRO).
    """
    DEV = 'DEV', 'Desenvolvedor (DEV) — Escopo Global'
    ADMIN = 'ADMIN', 'Administrador da Loja (ADMIN)'
    SUPERVISOR = 'SUPERVISOR', 'Supervisor da Loja (SUPERVISOR)'
    USUARIO = 'USUARIO', 'Usuário Padrão da Loja (USUÁRIO)'


class EventoAuditoriaEnum(models.TextChoices):
    """
    Tipos de eventos para registro em LogAuditoria.
    """
    CRIACAO_USUARIO = 'CRIACAO_USUARIO', 'Criação de Usuário'
    EDICAO_USUARIO = 'EDICAO_USUARIO', 'Edição de Dados Cadastrais'
    TROCA_PAPEL = 'TROCA_PAPEL', 'Alteração de Papel RBAC'
    STATUS_USUARIO = 'STATUS_USUARIO', 'Alteração de Status de Usuário'
    RESET_SENHA = 'RESET_SENHA', 'Redefinição de Senha por Administrador'
    CRIACAO_LOJA = 'CRIACAO_LOJA', 'Provisionamento de Loja'
    EDICAO_LOJA = 'EDICAO_LOJA', 'Edição de Loja'
