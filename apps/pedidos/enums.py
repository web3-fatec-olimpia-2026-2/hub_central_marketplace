# Os códigos foram gerados com auxilio de I.A.
from django.db import models


class StatusPedidoEnum(models.TextChoices):
    """
    O QUE FAZ: Status operacional e financeiro do Pedido de Venda no Hub.
    POR QUE FAZ: Controla o ciclo de vida do pedido (PAGO, CANCELADO, ENVIADO, ENTREGUE).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Status isolado por pedido da loja.
    """
    PAGO = 'PAGO', 'Pago / Aprovado'
    CANCELADO = 'CANCELADO', 'Cancelado'
    ENVIADO = 'ENVIADO', 'Enviado / Em Trânsito'
    ENTREGUE = 'ENTREGUE', 'Entregue'
