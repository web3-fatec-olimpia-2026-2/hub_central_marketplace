# Os códigos foram gerados com auxilio de I.A.
from django.db import models


class StatusProdutoEnum(models.TextChoices):
    """
    O QUE FAZ: Status de comercialização do Produto no catálogo interno do Hub.
    POR QUE FAZ: Controla a disponibilidade do item para venda e sincronização.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Status isolado por produto da loja.
    """
    ATIVO = 'ATIVO', 'Ativo (Disponível para venda)'
    INATIVO = 'INATIVO', 'Inativo (Pausado)'
    RASCUNHO = 'RASCUNHO', 'Rascunho (Em elaboração)'


class TipoAjusteEstoqueEnum(models.TextChoices):
    """
    O QUE FAZ: Motivos de movimentação e ajuste de estoque físico.
    POR QUE FAZ: Separa entradas/correções de gestão das baixas operacionais de perda/avaria (RN-09).
    PERMISSÕES RBAC: SAIDA_AVARIA e SAIDA_PERDA permitidos para USUARIO; demais para SUPERVISOR/ADMIN/DEV.
    MULTI-TENANCY: Registrado em log vinculado à loja.
    """
    ENTRADA = 'ENTRADA', 'Entrada de Estoque / Reposição'
    SAIDA_AVARIA = 'SAIDA_AVARIA', 'Baixa por Avaria / Defeito'
    SAIDA_PERDA = 'SAIDA_PERDA', 'Baixa por Perda / Extravio'
    CORRECAO_BALANCO = 'CORRECAO_BALANCO', 'Ajuste de Balanço / Correção Manual'
