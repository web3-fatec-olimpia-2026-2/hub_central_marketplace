# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Registro central e constantes de canais de marketplaces e mecanismos de notificação.
POR QUE FAZ: Padroniza o roteamento de webhooks e mensageria desacoplando regras específicas de cada canal.
"""

CANAL_REGISTRY = {
    'mercadolivre': {
        'nome': 'Mercado Livre',
        'canal_key': 'mercadolivre',
        'mecanismo_notificacao': 'WEBHOOK_HTTP',
        'callback_path': '/marketplaces/mercadolivre/callback/',
        'webhook_path_global': '/api/v1/webhooks/mercadolivre/',
        'webhook_path_individual': '/api/v1/webhooks/mercadolivre/{uuid}/',
        'header_assinatura': 'x-signature',
        'header_timestamp': 'x-timestamp',
        'requer_webhook_secret': True,
        'suporta_global': True,
        'label_id': 'App ID (Client ID)',
        'label_secret': 'Client Secret',
    },
    'shopee': {
        'nome': 'Shopee Open Platform',
        'canal_key': 'shopee',
        'mecanismo_notificacao': 'WEBHOOK_HTTP',
        'callback_path': '/marketplaces/shopee/callback/',
        'webhook_path_global': '/api/v1/webhooks/shopee/',
        'webhook_path_individual': '/api/v1/webhooks/shopee/{uuid}/',
        'header_assinatura': 'authorization',
        'header_timestamp': 'timestamp',
        'requer_webhook_secret': False,  # Validação via Partner Key
        'suporta_global': True,
        'label_id': 'Partner ID',
        'label_secret': 'Partner Key',
    },
    'amazon': {
        'nome': 'Amazon SP-API',
        'canal_key': 'amazon',
        'mecanismo_notificacao': 'QUEUE_EVENT',  # Sem endpoint HTTP direto; baseada em mensageria SQS / EventBridge
        'callback_path': '/marketplaces/amazon/callback/',
        'arn_sqs_global': 'arn:aws:sqs:us-east-1:...',
        'suporta_global': True,
        'label_id': 'LWA Client ID / IAM Role ARN',
        'label_secret': 'LWA Client Secret',
        'requer_worker_polling': True,
    },
    'magalu': {
        'nome': 'Magalu Open API',
        'canal_key': 'magalu',
        'mecanismo_notificacao': 'WEBHOOK_HTTP',
        'callback_path': '/marketplaces/magalu/callback/',
        'webhook_path_global': '/api/v1/webhooks/magalu/',
        'webhook_path_individual': '/api/v1/webhooks/magalu/{uuid}/',
        'header_assinatura': 'x-signature',
        'header_timestamp': 'x-timestamp',
        'requer_webhook_secret': True,
        'suporta_global': True,
        'label_id': 'Client ID',
        'label_secret': 'Client Secret',
    },
}

# Normalização de aliases em caixa alta e apelidos comuns (ex: meli -> mercadolivre)
_aliases = {
    'MERCADOLIVRE': 'mercadolivre',
    'MERCADO_LIVRE': 'mercadolivre',
    'MELI': 'mercadolivre',
    'meli': 'mercadolivre',
    'SHOPEE': 'shopee',
    'AMAZON': 'amazon',
    'MAGALU': 'magalu',
}

for alias, target in _aliases.items():
    if target in CANAL_REGISTRY:
        CANAL_REGISTRY[alias] = CANAL_REGISTRY[target]


def get_canal_config(canal: str) -> dict:
    """Retorna o dicionário de configurações do canal normalizado."""
    if not canal:
        return {}
    key = canal.strip().lower()
    return CANAL_REGISTRY.get(key) or CANAL_REGISTRY.get(canal.strip().upper(), {})
