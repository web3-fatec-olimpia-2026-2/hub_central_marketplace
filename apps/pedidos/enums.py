# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo models do Django para permitir o uso de TextChoices em enumerações de banco
from django.db import models


# Declaração do enum textual que padroniza os estados do ciclo de vida de um Pedido de Venda
class StatusPedidoEnum(models.TextChoices):
    # Início do bloco de docstring que documenta o propósito, ciclo de vida, RBAC e isolamento multi-tenant
    """
    O QUE FAZ: Status operacional e financeiro do Pedido de Venda no Hub.
    POR QUE FAZ: Controla o ciclo de vida do pedido (PAGO, CANCELADO, ENVIADO, ENTREGUE).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Status isolado por pedido da loja.
    """
    # Fim do bloco de docstring informativa

    # Constante para pedidos com pagamento aprovado pelo marketplace aptos para separação/baixa de estoque
    PAGO = 'PAGO', 'Pago / Aprovado'

    # Constante para pedidos cancelados antes do envio ou devolvidos
    CANCELADO = 'CANCELADO', 'Cancelado'

    # Constante para pedidos despachados e em trânsito com transportadora/correios
    ENVIADO = 'ENVIADO', 'Enviado / Em Trânsito'

    # Constante para pedidos com confirmação de entrega ao consumidor final
    ENTREGUE = 'ENTREGUE', 'Entregue'