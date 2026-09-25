# Os códigos foram gerados com auxilio de I.A.

# Início da docstring do módulo que documenta o catálogo central de configurações e mecanismos de notificação
"""
O QUE FAZ: Registro central e constantes de canais de marketplaces e mecanismos de notificação.
POR QUE FAZ: Padroniza o roteamento de webhooks e mensageria desacoplando regras específicas de cada canal.
"""
# Fim da docstring informativa do módulo

# Dicionário mestre que centraliza as regras de comunicação, autenticação e rotas para cada marketplace suportado
CANAL_REGISTRY = {
    # Mapeamento de configurações específicas para a integração com o Mercado Livre
    'mercadolivre': {
        # Nome legível do canal para apresentação visual em interfaces
        'nome': 'Mercado Livre',
        # Chave unificada que identifica o canal no ecossistema
        'canal_key': 'mercadolivre',
        # Tipo de recepção de eventos operando por requisição HTTP POST (Webhook)
        'mecanismo_notificacao': 'WEBHOOK_HTTP',
        # Rota HTTP interna para onde o marketplace redireciona o fluxo de consentimento OAuth
        'callback_path': '/marketplaces/mercadolivre/callback/',
        # Endpoint de webhook central que recebe eventos de todas as contas integradas da plataforma
        'webhook_path_global': '/api/v1/webhooks/mercadolivre/',
        # Padrão de rota parametrizada por UUID para clientes ou contas que exijam endpoint dedicado
        'webhook_path_individual': '/api/v1/webhooks/mercadolivre/{uuid}/',
        # Nome do cabeçalho HTTP que trafega o HMAC de validação de integridade enviado pelo Mercado Livre
        'header_assinatura': 'x-signature',
        # Nome do cabeçalho HTTP que transporta o timestamp para prevenção de ataques de repetição (replay attack)
        'header_timestamp': 'x-timestamp',
        # Sinaliza que este canal necessita de um segredo dedicado para validação da assinatura de webhook
        'requer_webhook_secret': True,
        # Indica se o canal suporta o recebimento unificado de eventos em uma única URL global
        'suporta_global': True,
        # Rótulo amigável exibido no formulário para preenchimento da chave pública da aplicação
        'label_id': 'App ID (Client ID)',
        # Rótulo amigável exibido no formulário para preenchimento da chave secreta da aplicação
        'label_secret': 'Client Secret',
    },
    # Mapeamento de configurações específicas para a integração com a Shopee
    'shopee': {
        # Nome institucional da plataforma de parceiros da Shopee
        'nome': 'Shopee Open Platform',
        # Identificador canônico do canal
        'canal_key': 'shopee',
        # Mecanismo baseado em requisições Webhook via protocolo HTTP
        'mecanismo_notificacao': 'WEBHOOK_HTTP',
        # Rota interna receptora do callback de autorização OAuth
        'callback_path': '/marketplaces/shopee/callback/',
        # Endpoint unificado de webhook para recepção das notificações de pedidos e estoques da Shopee
        'webhook_path_global': '/api/v1/webhooks/shopee/',
        # Endpoint individual formatado por UUID para segregação de tráfego se necessário
        'webhook_path_individual': '/api/v1/webhooks/shopee/{uuid}/',
        # Nome do cabeçalho que carrega o token assinado da Shopee
        'header_assinatura': 'authorization',
        # Nome do parâmetro/cabeçalho contendo a estampa de tempo da requisição
        'header_timestamp': 'timestamp',
        # Dispensado, pois a verificação de integridade da Shopee é derivada da Partner Key cadastrada
        'requer_webhook_secret': False,  # Validação via Partner Key
        # Habilita suporte ao endpoint de webhook compartilhado globalmente
        'suporta_global': True,
        # Rótulo amigável exibido nos formulários para o identificador do parceiro Shopee
        'label_id': 'Partner ID',
        # Rótulo amigável para a chave de autenticação privada da Shopee
        'label_secret': 'Partner Key',
    },
    # Mapeamento de configurações da API Selling Partner da Amazon (SP-API)
    'amazon': {
        # Nome institucional da API de vendedores da Amazon
        'nome': 'Amazon SP-API',
        # Chave unificada do canal
        'canal_key': 'amazon',
        # Mecanismo assíncrono orientado a eventos via filas (SQS/EventBridge), não expondo webhook HTTP público
        'mecanismo_notificacao': 'QUEUE_EVENT',  # Sem endpoint HTTP direto; baseada em mensageria SQS / EventBridge
        # Rota de retorno do handshake OAuth da Amazon (Login with Amazon)
        'callback_path': '/marketplaces/amazon/callback/',
        # Identificador de recurso da AWS (ARN) da fila SQS para consumo dos eventos
        'arn_sqs_global': 'arn:aws:sqs:us-east-1:...',
        # Indica que uma única fila processa eventos de múltiplos sellers
        'suporta_global': True,
        # Rótulo exibido para preenchimento das credenciais de autorização da Amazon
        'label_id': 'LWA Client ID / IAM Role ARN',
        # Rótulo exibido para o segredo de aplicação da Amazon
        'label_secret': 'LWA Client Secret',
        # Sinaliza que o sistema deve manter workers em background realizando polling contínuo na fila SQS
        'requer_worker_polling': True,
    },
    # Mapeamento de configurações para o marketplace Magazine Luiza (Magalu)
    'magalu': {
        # Nome institucional da plataforma aberta do Magazine Luiza
        'nome': 'Magalu Open API',
        # Identificador canônico do canal
        'canal_key': 'magalu',
        # Notificações enviadas via requisição Webhook HTTP POST
        'mecanismo_notificacao': 'WEBHOOK_HTTP',
        # Rota de callback do processo de autorização OAuth
        'callback_path': '/marketplaces/magalu/callback/',
        # Endpoint global de ingestão de webhooks do ecossistema Magalu
        'webhook_path_global': '/api/v1/webhooks/magalu/',
        # Endpoint segregado com identificador UUID
        'webhook_path_individual': '/api/v1/webhooks/magalu/{uuid}/',
        # Cabeçalho HTTP com a assinatura criptográfica para validação do payload
        'header_assinatura': 'x-signature',
        # Cabeçalho HTTP contendo o timestamp para mitigação de replay attacks
        'header_timestamp': 'x-timestamp',
        # Exige token de segredo compartilhado para conferência do HMAC
        'requer_webhook_secret': True,
        # Suporta tráfego agregado no endpoint global
        'suporta_global': True,
        # Rótulo de interface para identificação do cliente
        'label_id': 'Client ID',
        # Rótulo de interface para o segredo do cliente
        'label_secret': 'Client Secret',
    },
}

# Normalização de aliases em caixa alta e apelidos comuns (ex: meli -> mercadolivre)
# Dicionário de equivalências que mapeia variações e acrônimos para as chaves oficiais do CANAL_REGISTRY
_aliases = {
    'MERCADOLIVRE': 'mercadolivre',
    'MERCADO_LIVRE': 'mercadolivre',
    'MELI': 'mercadolivre',
    'meli': 'mercadolivre',
    'SHOPEE': 'shopee',
    'AMAZON': 'amazon',
    'MAGALU': 'magalu',
}

# Itera sobre o dicionário de aliases vinculando as chaves alternativas às mesmas definições no registro
for alias, target in _aliases.items():
    # Verifica se a chave de destino está presente no dicionário principal
    if target in CANAL_REGISTRY:
        # Vincula o alias diretamente à referência da configuração de destino
        CANAL_REGISTRY[alias] = CANAL_REGISTRY[target]


# Função utilitária para recuperação segura e normalizada dos dados de configuração de um canal
def get_canal_config(canal: str) -> dict:
    # Início da docstring da função
    """Retorna o dicionário de configurações do canal normalizado."""
    # Fim da docstring informativa

    # Retorna dicionário vazio se o parâmetro for nulo, vazio ou inválido
    if not canal:
        return {}

    # Sanitiza a entrada removendo espaços laterais e convertendo para minúsculas
    key = canal.strip().lower()

    # Busca pela chave normalizada em minúsculas ou tenta em maiúsculas antes de retornar dicionário vazio
    return CANAL_REGISTRY.get(key) or CANAL_REGISTRY.get(canal.strip().upper(), {})
