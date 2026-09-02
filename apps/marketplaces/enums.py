# Os códigos foram gerados com auxilio de I.A.
from django.db import models


class CanalMarketplaceEnum(models.TextChoices):
    """
    O QUE FAZ: Enumeração dos canais de marketplaces suportados na arquitetura multicanal do Hub.
    POR QUE FAZ: Substitui a abordagem exclusiva de canal único pelo suporte expansível a múltiplos marketplaces (Mercado Livre, Shopee, Magalu, Amazon).
    PERMISSÕES RBAC: Usado em conectores, contas e parâmetros financeiros.
    MULTI-TENANCY: Cada loja pode conectar uma ou mais contas de cada um desses canais.
    """
    MERCADOLIVRE = 'mercadolivre', 'Mercado Livre'
    SHOPEE = 'shopee', 'Shopee'
    MAGALU = 'magalu', 'Magazine Luiza'
    AMAZON = 'amazon', 'Amazon'


class StatusSincronizacaoEnum(models.TextChoices):
    """
    O QUE FAZ: Enumeração de status de sincronização de dados (preço/estoque) com os marketplaces.
    POR QUE FAZ: Informa na interface o estado da comunicação com a API externa.
    PERMISSÕES RBAC: Consulta em listas de produtos e auditoria.
    MULTI-TENANCY: Status isolado por produto/anúncio da loja.
    """
    NAO_SINCRONIZADO = 'NAO_SINCRONIZADO', 'Não Sincronizado'
    PENDENTE = 'PENDENTE', 'Sincronização Pendente'
    SINCRONIZADO = 'SINCRONIZADO', 'Sincronizado com Sucesso'
    ERRO = 'ERRO', 'Erro de Sincronização'


class EventoAuditoriaEnum(models.TextChoices):
    """
    O QUE FAZ: Tipos de eventos auditados pelo Hub em logs de sincronização e auditoria geral.
    POR QUE FAZ: Rastreabilidade, diagnóstico de integrações e conformidade de segurança (RN-04).
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Registro vinculado à loja.
    """
    # Gestão de Contas e Conexão
    CRIACAO_CONTA = 'CRIACAO_CONTA', 'Cadastro de Conta de Marketplace'
    EDICAO_CONTA = 'EDICAO_CONTA', 'Edição de Conta de Marketplace'
    EXCLUSAO_CONTA = 'EXCLUSAO_CONTA', 'Exclusão de Conta de Marketplace'
    TESTE_CONEXAO = 'TESTE_CONEXAO', 'Teste de Conexão com API Externa'
    REFRESH_TOKEN = 'REFRESH_TOKEN', 'Renovação de Token OAuth'

    # Sincronização de Catálogo
    SYNC_PRECO = 'SYNC_PRECO', 'Sincronização de Preço'
    SYNC_PRECO_LOTE = 'SYNC_PRECO_LOTE', 'Sincronização de Preço em Lote'
    SYNC_ESTOQUE = 'SYNC_ESTOQUE', 'Sincronização de Estoque'
    BROADCAST_ESTOQUE = 'BROADCAST_ESTOQUE', 'Broadcast Multi-Canal de Estoque'
    PUBLICACAO_ANUNCIO = 'PUBLICACAO_ANUNCIO', 'Publicação de Anúncio'

    # Vendas e Pedidos
    WEBHOOK_RECEBIDO = 'WEBHOOK_RECEBIDO', 'Webhook de Venda Recebido'
    BAIXA_ESTOQUE_VENDA = 'BAIXA_ESTOQUE_VENDA', 'Baixa Automática de Estoque por Venda'
    ALERTA_RUPTURA_ESTOQUE = 'ALERTA_RUPTURA_ESTOQUE', 'Alerta de Ruptura / Saldo Negativo'

    # Auditoria de Tenant e Catálogo
    CRIACAO_PRODUTO = 'CRIACAO_PRODUTO', 'Cadastro de Produto'
    EDICAO_PRODUTO = 'EDICAO_PRODUTO', 'Edição de Produto'
    EXCLUSAO_PRODUTO = 'EXCLUSAO_PRODUTO', 'Exclusão de Produto'
    ALTERACAO_PRECO = 'ALTERACAO_PRECO', 'Alteração Manual de Preço'
    AJUSTE_ESTOQUE = 'AJUSTE_ESTOQUE', 'Ajuste Geral de Estoque'
    BAIXA_AVARIA = 'BAIXA_AVARIA', 'Baixa de Estoque por Avaria'
    CRIACAO_CATEGORIA = 'CRIACAO_CATEGORIA', 'Cadastro de Categoria'
    EDICAO_CATEGORIA = 'EDICAO_CATEGORIA', 'Edição de Categoria'
    EXCLUSAO_CATEGORIA = 'EXCLUSAO_CATEGORIA', 'Exclusão de Categoria'
