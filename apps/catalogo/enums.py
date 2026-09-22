# Os códigos foram gerados com auxilio de I.A.
# Importa o módulo de modelos do Django para utilizar a classe base tipada TextChoices
from django.db import models


# Declara a enumeração de opções textuais para o ciclo de vida comercial do Produto
class StatusProdutoEnum(models.TextChoices):
    # Início do bloco de docstring que documenta a finalidade, controle de disponibilidade e escopo multi-tenant do enum
    """
    O QUE FAZ: Status de comercialização do Produto no catálogo interno do Hub.
    POR QUE FAZ: Controla a disponibilidade do item para venda e sincronização.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Status isolado por produto da loja.
    """
    # Fim do bloco de documentação do status do produto

    # Opção que define o produto como apto para publicação, cálculo de cota de kits e sincronização ativa
    ATIVO = 'ATIVO', 'Ativo (Disponível para venda)'

    # Opção que suspende a comercialização e pausa a oferta nos canais de integração
    INATIVO = 'INATIVO', 'Inativo (Pausado)'

    # Opção que marca o produto em fase de cadastro/revisão técnica, impedindo sua venda prematura
    RASCUNHO = 'RASCUNHO', 'Rascunho (Em elaboração)'


# Declara a enumeração tipada para classificação e auditoria das movimentações de inventário físico
class TipoAjusteEstoqueEnum(models.TextChoices):
    # Início do bloco de docstring que detalha os motivos de ajuste físico, conformidade com regras e RBAC
    """
    O QUE FAZ: Motivos de movimentação e ajuste de estoque físico.
    POR QUE FAZ: Separa entradas/correções de gestão das baixas operacionais de perda/avaria (RN-09).
    PERMISSÕES RBAC: SAIDA_AVARIA e SAIDA_PERDA permitidos para USUARIO; demais para SUPERVISOR/ADMIN/DEV.
    MULTI-TENANCY: Registrado em log vinculado à loja.
    """
    # Fim do bloco de documentação dos motivos de movimentação de estoque

    # Classificação para acréscimo de saldo físico decorrente de compras, devoluções ou reposição de mercadorias
    ENTRADA = 'ENTRADA', 'Entrada de Estoque / Reposição'

    # Classificação para baixa manual motivada por dano físico, defeito de fabricação ou produto quebrado
    SAIDA_AVARIA = 'SAIDA_AVARIA', 'Baixa por Avaria / Defeito'

    # Classificação para baixa manual motivada por extravio de transporte, furto ou perda física comprovada
    SAIDA_PERDA = 'SAIDA_PERDA', 'Baixa por Perda / Extravio'

    # Classificação para ajustes de conciliação física após inventário cíclico ou auditoria de contagem
    CORRECAO_BALANCO = 'CORRECAO_BALANCO', 'Ajuste de Balanço / Correção Manual'
