# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo de modelos ORM do Django, utilizado aqui para herdar a classe base TextChoices
from django.db import models


# Declaração da enumeração textual dos canais de integração de marketplaces compatíveis com o ecossistema
class CanalMarketplaceEnum(models.TextChoices):
    # Início do bloco de docstring que documenta o suporte multicanal, RBAC e particionamento multi-tenant
    """
    O QUE FAZ: Enumeração dos canais de marketplaces suportados na arquitetura multicanal do Hub.
    POR QUE FAZ: Substitui a abordagem exclusiva de canal único pelo suporte expansível a múltiplos marketplaces (Mercado Livre, Shopee, Magalu, Amazon).
    PERMISSÕES RBAC: Usado em conectores, contas e parâmetros financeiros.
    MULTI-TENANCY: Cada loja pode conectar uma ou mais contas de cada um desses canais.
    """
    # Fim do bloco de documentação estrutural do enum

    # Define o identificador e o rótulo legível para a integração com a plataforma Mercado Livre
    MERCADOLIVRE = 'mercadolivre', 'Mercado Livre'

    # Define o identificador e o rótulo legível para a integração com a plataforma Shopee
    SHOPEE = 'shopee', 'Shopee'

    # Define o identificador e o rótulo legível para a integração com a plataforma Magazine Luiza
    MAGALU = 'magalu', 'Magazine Luiza'

    # Define o identificador e o rótulo legível para a integração com a plataforma Amazon
    AMAZON = 'amazon', 'Amazon'


# Declaração da enumeração textual representativa dos estados da fila e disparos de sincronização com canais externos
class StatusSincronizacaoEnum(models.TextChoices):
    # Início do bloco de docstring que detalha o papel da enumeração no monitoramento visual e auditoria
    """
    O QUE FAZ: Enumeração de status de sincronização de dados (preço/estoque) com os marketplaces.
    POR QUE FAZ: Informa na interface o estado da comunicação com a API externa.
    PERMISSÕES RBAC: Consulta em listas de produtos e auditoria.
    MULTI-TENANCY: Status isolado por produto/anúncio da loja.
    """
    # Fim da documentação explicativa da classe

    # Estado indicando que o registro local ainda não foi submetido a nenhuma rotina de envio ao marketplace
    NAO_SINCRONIZADO = 'NAO_SINCRONIZADO', 'Não Sincronizado'

    # Estado indicando que alterações de preço ou saldo físico foram detectadas e aguardam despacho na fila de sincronização
    PENDENTE = 'PENDENTE', 'Sincronização Pendente'

    # Estado confirmando que o anúncio remoto no canal parceiro recebeu e aceitou as atualizações com sucesso
    SINCRONIZADO = 'SINCRONIZADO', 'Sincronizado com Sucesso'

    # Estado acusando falha de comunicação, rejeição de validação ou erro HTTP retornado pela API remota do canal
    ERRO = 'ERRO', 'Erro de Sincronização'


# Declaração da enumeração textual que tipifica categoricamente todos os eventos auditáveis no sistema
class EventoAuditoriaEnum(models.TextChoices):
    # Início do bloco de docstring que documenta a rastreabilidade e a conformidade técnica com o requisito RN-04
    """
    O QUE FAZ: Tipos de eventos auditados pelo Hub em logs de sincronização e auditoria geral.
    POR QUE FAZ: Rastreabilidade, diagnóstico de integrações e conformidade de segurança (RN-04).
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Registro vinculado à loja.
    """
    # Fim do bloco descritivo de auditoria

    # Gestão de Contas e Conexão
    # Evento gerado quando uma nova conta de integração de marketplace é registrada na loja
    CRIACAO_CONTA = 'CRIACAO_CONTA', 'Cadastro de Conta de Marketplace'

    # Evento gerado quando parâmetros cadastrais ou credenciais de uma conta de marketplace são modificados
    EDICAO_CONTA = 'EDICAO_CONTA', 'Edição de Conta de Marketplace'

    # Evento registrado quando o vínculo de uma conta de canal parceiro é excluído
    EXCLUSAO_CONTA = 'EXCLUSAO_CONTA', 'Exclusão de Conta de Marketplace'

    # Evento de telemetria disparado durante validações ativas de comunicação e teste de ping com a API externa
    TESTE_CONEXAO = 'TESTE_CONEXAO', 'Teste de Conexão com API Externa'

    # Evento que audita a troca e atualização bem-sucedida de tokens de acesso OAuth2 expirados
    REFRESH_TOKEN = 'REFRESH_TOKEN', 'Renovação de Token OAuth'

    # Sincronização de Catálogo
    # Evento que registra a sincronização pontual de preço de um SKU/anúncio para um canal específico
    SYNC_PRECO = 'SYNC_PRECO', 'Sincronização de Preço'

    # Evento disparado quando uma rotina em lote atualiza simultaneamente preços de múltiplos anúncios
    SYNC_PRECO_LOTE = 'SYNC_PRECO_LOTE', 'Sincronização de Preço em Lote'

    # Evento que documenta o envio de novo saldo físico de estoque unitário para o marketplace
    SYNC_ESTOQUE = 'SYNC_ESTOQUE', 'Sincronização de Estoque'

    # Evento que registra o envio massivo simultâneo do saldo físico para todos os canais integrados conectados à loja
    BROADCAST_ESTOQUE = 'BROADCAST_ESTOQUE', 'Broadcast Multi-Canal de Estoque'

    # Evento que registra a criação de uma oferta remota ativa a partir do catálogo local (RF-04)
    PUBLICACAO_ANUNCIO = 'PUBLICACAO_ANUNCIO', 'Publicação de Anúncio'

    # Vendas e Pedidos
    # Evento de entrada assíncrona notificando que uma requisição de Webhook de pedido foi interceptada pelo endpoint
    WEBHOOK_RECEBIDO = 'WEBHOOK_RECEBIDO', 'Webhook de Venda Recebido'

    # Evento que audita a dedução transacional automática de estoque físico no momento da confirmação de compra remota
    BAIXA_ESTOQUE_VENDA = 'BAIXA_ESTOQUE_VENDA', 'Baixa Automática de Estoque por Venda'

    # Evento crítico gerado quando o saldo do produto atinge zero ou fica negativo em virtude de vendas simultâneas
    ALERTA_RUPTURA_ESTOQUE = 'ALERTA_RUPTURA_ESTOQUE', 'Alerta de Ruptura / Saldo Negativo'

    # Auditoria de Tenant e Catálogo
    # Evento que audita a inclusão cadastral de um novo produto físico no catálogo
    CRIACAO_PRODUTO = 'CRIACAO_PRODUTO', 'Cadastro de Produto'

    # Evento que documenta a atualização cadastral das propriedades gerais de um produto existente
    EDICAO_PRODUTO = 'EDICAO_PRODUTO', 'Edição de Produto'

    # Evento que rastreia a remoção definitiva de um produto físico do catálogo da loja
    EXCLUSAO_PRODUTO = 'EXCLUSAO_PRODUTO', 'Exclusão de Produto'

    # Evento que audita intervenções manuais diretas de reajuste de preço de venda no catálogo
    ALTERACAO_PRECO = 'ALTERACAO_PRECO', 'Alteração Manual de Preço'

    # Evento que registra correções manuais de balanço geral de estoque físico realizadas por gestores (RN-09)
    AJUSTE_ESTOQUE = 'AJUSTE_ESTOQUE', 'Ajuste Geral de Estoque'

    # Evento que audita o registro operacional de baixa de estoque motivada por perda, defeito ou avaria física
    BAIXA_AVARIA = 'BAIXA_AVARIA', 'Baixa de Estoque por Avaria'

    # Evento que registra a criação de uma nova categoria estrutural de produtos
    CRIACAO_CATEGORIA = 'CRIACAO_CATEGORIA', 'Cadastro de Categoria'

    # Evento que audita alterações cadastrais de nome ou slug em categorias de produtos
    EDICAO_CATEGORIA = 'EDICAO_CATEGORIA', 'Edição de Categoria'

    # Evento que audita a remoção de categorias de produtos do sistema
    EXCLUSAO_CATEGORIA = 'EXCLUSAO_CATEGORIA', 'Exclusão de Categoria'


# Declaração da enumeração textual para controle do fluxo de processamento e garantia de idempotência de Webhooks
class WebhookStatusEnum(models.TextChoices):
    # Início do bloco de docstring que documenta o ciclo de vida dos webhooks
    """
    O QUE FAZ: Enumeração de status para rastreamento do ciclo de vida e idempotência de eventos de Webhooks.
    """
    # Fim da documentação explicativa

    # Notificação recebida na porta de entrada e persistida em banco, aguardando início de tratamento
    RECEBIDO = 'RECEBIDO', 'Recebido'

    # Sinaliza que uma tarefa assíncrona ou worker está atualmente consumindo e processando os dados do payload
    PROCESSANDO = 'PROCESSANDO', 'Processando'

    # Notificação concluída com sucesso: regras de negócio executadas e efeitos colaterais persistidos
    PROCESSADO = 'PROCESSADO', 'Processado'

    # Indica que a notificação foi descartada deliberadamente (ex.: evento repetido já processado ou tópico irrelevante)
    IGNORADO = 'IGNORADO', 'Ignorado'

    # Indica que ocorreu uma falha fatal ou inconsistência irrecuperável durante o parsing e processamento do evento
    ERRO = 'ERRO', 'Erro'
