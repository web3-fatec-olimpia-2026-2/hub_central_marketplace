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


class StatusProdutoEnum(models.TextChoices):
    """
    Status de comercialização e visibilidade do Produto no Hub.
    """
    ATIVO = 'ATIVO', 'Ativo (Disponível para venda)'
    INATIVO = 'INATIVO', 'Inativo (Pausado)'
    RASCUNHO = 'RASCUNHO', 'Rascunho (Em elaboração)'


class StatusSincronizacaoEnum(models.TextChoices):
    """
    Status de integração do produto com marketplaces externos (Mercado Livre).
    """
    NAO_SINCRONIZADO = 'NAO_SINCRONIZADO', 'Não Sincronizado'
    PENDENTE = 'PENDENTE', 'Sincronização Pendente'
    SINCRONIZADO = 'SINCRONIZADO', 'Sincronizado com Sucesso'
    ERRO = 'ERRO', 'Erro de Sincronização'


class TipoAjusteEstoqueEnum(models.TextChoices):
    """
    Tipos de movimentação e ajuste de estoque.
    """
    ENTRADA = 'ENTRADA', 'Entrada de Estoque / Reposição'
    SAIDA_AVARIA = 'SAIDA_AVARIA', 'Baixa por Avaria / Defeito'
    SAIDA_PERDA = 'SAIDA_PERDA', 'Baixa por Perda / Extravio'
    CORRECAO_BALANCO = 'CORRECAO_BALANCO', 'Ajuste de Balanço / Correção Manual'


class MarketplaceEnum(models.TextChoices):
    """
    Marketplaces suportados ou planejados na arquitetura multi-canal.
    """
    MERCADO_LIVRE = 'MERCADO_LIVRE', 'Mercado Livre'
    SHOPEE = 'SHOPEE', 'Shopee (Backlog)'
    MAGALU = 'MAGALU', 'Magazine Luiza (Backlog)'


class StatusPedidoEnum(models.TextChoices):
    """
    Status de processamento e faturamento de Pedidos de Venda recebidos via Webhook.
    """
    PAGO = 'PAGO', 'Pago / Confirmado'
    CRIADO = 'CRIADO', 'Criado / Pendente de Pagamento'
    CANCELADO = 'CANCELADO', 'Cancelado'
    ENTREGUE = 'ENTREGUE', 'Entregue'
    OUTRO = 'OUTRO', 'Outro Status'


class EventoAuditoriaEnum(models.TextChoices):
    """
    Tipos de eventos para registro em LogAuditoria.
    """
    # Gestão de Usuários
    CRIACAO_USUARIO = 'CRIACAO_USUARIO', 'Criação de Usuário'
    EDICAO_USUARIO = 'EDICAO_USUARIO', 'Edição de Dados Cadastrais'
    TROCA_PAPEL = 'TROCA_PAPEL', 'Alteração de Papel RBAC'
    STATUS_USUARIO = 'STATUS_USUARIO', 'Alteração de Status de Usuário'
    RESET_SENHA = 'RESET_SENHA', 'Redefinição de Senha por Administrador'

    # Gestão de Lojas (Tenants)
    CRIACAO_LOJA = 'CRIACAO_LOJA', 'Provisionamento de Loja'
    EDICAO_LOJA = 'EDICAO_LOJA', 'Edição de Loja'

    # Catálogo de Produtos e Categorias (RF-03)
    CRIACAO_PRODUTO = 'CRIACAO_PRODUTO', 'Cadastro de Produto'
    EDICAO_PRODUTO = 'EDICAO_PRODUTO', 'Edição de Produto'
    EXCLUSAO_PRODUTO = 'EXCLUSAO_PRODUTO', 'Exclusão de Produto'
    ALTERACAO_PRECO = 'ALTERACAO_PRECO', 'Alteração de Preço de Venda'
    AJUSTE_ESTOQUE = 'AJUSTE_ESTOQUE', 'Ajuste Geral de Estoque'
    BAIXA_AVARIA_ESTOQUE = 'BAIXA_AVARIA_ESTOQUE', 'Baixa Pontual de Estoque por Avaria'
    CRIACAO_CATEGORIA = 'CRIACAO_CATEGORIA', 'Cadastro de Categoria'
    EDICAO_CATEGORIA = 'EDICAO_CATEGORIA', 'Edição de Categoria'
    EXCLUSAO_CATEGORIA = 'EXCLUSAO_CATEGORIA', 'Exclusão de Categoria'

    # Integração Marketplaces (RF-05 / RF-06 / RF-07 / RF-08)
    SYNC_PRECO_MELI = 'SYNC_PRECO_MELI', 'Sincronização de Preço (Mercado Livre)'
    SYNC_PRECO_LOTE_MELI = 'SYNC_PRECO_LOTE_MELI', 'Sincronização em Lote de Preços (Mercado Livre)'
    REFRESH_TOKEN_MELI = 'REFRESH_TOKEN_MELI', 'Renovação de Token OAuth (Mercado Livre)'
    CONFIG_CREDENCIAIS_MELI = 'CONFIG_CREDENCIAIS_MELI', 'Configuração de Credenciais de Integração'
    TESTE_CONEXAO_MELI = 'TESTE_CONEXAO_MELI', 'Teste de Conexão com Mercado Livre'
    WEBHOOK_VENDA_MELI = 'WEBHOOK_VENDA_MELI', 'Processamento de Webhook de Venda'
    BAIXA_ESTOQUE_VENDA = 'BAIXA_ESTOQUE_VENDA', 'Baixa Automática de Estoque por Venda'
    ALERTA_ESTOQUE_NEGATIVO_VENDA = 'ALERTA_ESTOQUE_NEGATIVO_VENDA', 'Alerta de Ruptura / Estoque Negativo'

    # Broadcast Multi-Canal (RF-08)
    BROADCAST_ESTOQUE = 'BROADCAST_ESTOQUE', 'Broadcast Multi-Canal de Estoque'
    SYNC_ESTOQUE_MELI = 'SYNC_ESTOQUE_MELI', 'Sincronização de Estoque (Mercado Livre)'
    SYNC_ESTOQUE_SHOPEE = 'SYNC_ESTOQUE_SHOPEE', 'Sincronização de Estoque (Shopee)'
    SYNC_ESTOQUE_MAGALU = 'SYNC_ESTOQUE_MAGALU', 'Sincronização de Estoque (Magalu)'




