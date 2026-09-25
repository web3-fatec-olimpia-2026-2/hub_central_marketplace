# Os códigos foram gerados com auxilio de I.A.

# Importa a classe Decimal para cálculo e persistência precisa de valores financeiros sem erro de ponto flutuante
from decimal import Decimal

# Importa o módulo models do Django para declaração de modelos e campos ORM
from django.db import models

# Importa o modelo Loja para estabelecer a chave estrangeira obrigatória de isolamento multi-tenant
from apps.tenancy.models import Loja

# Importa o modelo ContaMarketplace para vincular a integração específica pela qual a venda ocorreu
from apps.marketplaces.models import ContaMarketplace

# Importa o enum de canais de marketplace suportados (Mercado Livre, Shopee, Magalu, Amazon)
from apps.marketplaces.enums import CanalMarketplaceEnum

# Importa os modelos de catálogo Produto (estoque físico) e AnuncioMarketplace (anúncio comercial externo)
from apps.catalogo.models import Produto, AnuncioMarketplace

# Importa o enum de status operacional do pedido (PAGO, CANCELADO, ENVIADO, ENTREGUE)
from .enums import StatusPedidoEnum


# Declaração da classe do modelo PedidoVenda que registra os pedidos consolidados no Hub
class PedidoVenda(models.Model):
    # Início do bloco de docstring documentando objetivos, regras de negócio (RF-06/RN-05), RBAC e multi-tenancy
    """
    O QUE FAZ: Representa o registro consolidado de uma Venda recebida via Webhook ou conciliação de marketplaces (RF-06).
    POR QUE FAZ: Desacopla as vendas por canal mantendo rastreabilidade de comprador, valor, origem e integridade de estoque (RN-05).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO (leitura na própria loja).
    MULTI-TENANCY: FK obrigatória para Loja com unicidade composta ('loja', 'canal_origem', 'pedido_id_externo').
    """
    # Fim do bloco de docstring explicativa

    # Chave estrangeira para o tenant Loja com exclusão em cascata
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='pedidos_venda', verbose_name="Loja (Tenant)"
    )

    # Chave estrangeira opcional para a conta de marketplace específica que recebeu a venda
    conta_marketplace = models.ForeignKey(
        ContaMarketplace, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pedidos', verbose_name="Conta do Canal"
    )

    # Identificação do canal de venda parceiro com base nas opções do CanalMarketplaceEnum
    canal_origem = models.CharField(
        max_length=30, choices=CanalMarketplaceEnum.choices, default=CanalMarketplaceEnum.MERCADOLIVRE,
        verbose_name="Canal de Origem"
    )

    # Identificador textual do pedido gerado pela plataforma de origem, indexado no banco para consultas rápidas
    pedido_id_externo = models.CharField(
        max_length=100, db_index=True, verbose_name="ID do Pedido no Canal"
    )

    # Status textual cru reportado pela API externa do marketplace (ex.: 'paid', 'shipped')
    status_externo = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Status no Marketplace"
    )

    # Status operacional padronizado no ecossistema do Hub conforme StatusPedidoEnum
    status = models.CharField(
        max_length=20, choices=StatusPedidoEnum.choices, default=StatusPedidoEnum.PAGO,
        verbose_name="Status no Hub"
    )

    # Nome completo ou razão social do comprador final informado pelo marketplace
    comprador_nome = models.CharField(
        max_length=150, blank=True, null=True, verbose_name="Nome do Comprador"
    )

    # Documento de identificação fiscal do comprador (CPF ou CNPJ)
    comprador_documento = models.CharField(
        max_length=30, blank=True, null=True, verbose_name="Documento do Comprador"
    )

    # Valor bruto total consolidado do pedido incluindo produtos e frete
    valor_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor Total do Pedido (R$)"
    )

    # Valor cobrado pelo frete e transporte das mercadorias
    valor_frete = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor do Frete (R$)"
    )

    # Data e hora exatas da transação registradas no sistema do canal externo
    data_criacao_externa = models.DateTimeField(
        null=True, blank=True, verbose_name="Data no Marketplace"
    )

    # Flag booleana indicando se o processamento e a baixa de estoque ocorreram com êxito
    processado_com_sucesso = models.BooleanField(
        default=True, verbose_name="Processado com Sucesso"
    )

    # Flag de auditoria que sinaliza se algum item deste pedido gerou saldo negativo no inventário (RN-06)
    teve_ruptura_estoque = models.BooleanField(
        default=False, verbose_name="Houve Ruptura de Estoque"
    )

    # Armazena na íntegra o JSON bruto recebido do webhook ou consulta de conciliação para auditoria técnica
    payload_original = models.JSONField(
        default=dict, blank=True, verbose_name="Payload Original do Webhook"
    )

    # Timestamp de gravação inicial do registro de pedido no banco do Hub
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Recebido no Hub em"
    )

    # Timestamp de última modificação cadastral deste pedido
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    # Configurações de metadados do modelo
    class Meta:
        # Nome amigável no singular
        verbose_name = "Pedido de Venda"

        # Nome amigável no plural
        verbose_name_plural = "Pedidos de Venda"

        # Garante a unicidade do pedido externo por loja e canal de origem
        unique_together = ('loja', 'canal_origem', 'pedido_id_externo')

        # Constraint a nível de tabela assegurando que um ID externo não se repita no mesmo canal
        constraints = [
            models.UniqueConstraint(
                fields=['canal_origem', 'pedido_id_externo'],
                name='unique_pedido_canal_id_externo'
            )
        ]

        # Ordenação padrão decrescente pela data de recebimento (pedidos mais recentes primeiro)
        ordering = ['-criado_em']

    # Representação textual legível da instância do pedido
    def __str__(self):
        return f"[{self.get_canal_origem_display()}] Pedido #{self.pedido_id_externo} — R$ {self.valor_total} ({self.loja.nome})"

    # Propriedade utilitária para acesso padronizado ao número externo do pedido
    @property
    def numero_pedido(self) -> str:
        return self.pedido_id_externo

    # Propriedade utilitária para obter a identificação do canal de venda
    @property
    def canal(self) -> str:
        return self.canal_origem

    # Propriedade utilitária que expõe a instância de ContaMarketplace vinculada
    @property
    def conta(self):
        return self.conta_marketplace


# Declaração do modelo dos itens de linha que compõem o pedido de venda
class ItemPedidoVenda(models.Model):
    # Início do bloco de docstring que detalha o rastreamento atômico de saldos e controle de ruptura
    """
    O QUE FAZ: Itens e produtos associados a um Pedido de Venda.
    POR QUE FAZ: Registra a dedução atômica de estoque e rastreia saldos anteriores e posteriores (RN-05).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Herda o tenant do pedido pai.
    """
    # Fim da docstring explicativa

    # Opções válidas para o status de vínculo do item comercial com o estoque físico interno
    STATUS_INTEGRACAO_CHOICES = [
        ('vinculado', 'Vinculado'),
        ('pendente_vinculo', 'Pendente de Vínculo'),
    ]

    # Vínculo com o pedido de venda correspondente com remoção em cascata
    pedido = models.ForeignKey(
        PedidoVenda, on_delete=models.CASCADE, related_name='itens', verbose_name="Pedido"
    )

    # Chave estrangeira para o produto físico associado no catálogo do Hub (pode ser nula se pendente de vínculo)
    produto = models.ForeignKey(
        Produto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_vendidos', verbose_name="Produto no Hub"
    )

    # Vínculo com a entidade AnuncioMarketplace comercial que originou o item vendido
    anuncio_marketplace = models.ForeignKey(
        AnuncioMarketplace, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_vendidos', verbose_name="Anúncio Vinculado"
    )

    # Identificador externo do item no marketplace (ex.: MLB123456789)
    item_id_externo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="ID Externo do Item"
    )

    # Título ou descrição comercial do anúncio no instante da compra
    titulo_anuncio = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Título no Marketplace"
    )

    # Quantidade de unidades comercializadas deste item na venda
    quantidade = models.IntegerField(
        default=1, verbose_name="Quantidade Vendida"
    )

    # Preço unitário de venda cobrado por este item
    preco_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Preço Unitário (R$)"
    )

    # Indica se o SKU vendido possui relacionamento ativo com o catálogo ou se necessita conciliação manual
    status_integracao = models.CharField(
        max_length=30,
        choices=STATUS_INTEGRACAO_CHOICES,
        default='vinculado',
        verbose_name="Status de Integração do Item"
    )

    # Flag booleana indicando se o decremento de inventário físico já foi aplicado com sucesso
    estoque_baixado = models.BooleanField(
        default=False, verbose_name="Estoque Baixado Automaticamente"
    )

    # Registro de auditoria do saldo físico imediatamente anterior à baixa
    estoque_anterior = models.IntegerField(
        null=True, blank=True, verbose_name="Saldo de Estoque Anterior"
    )

    # Registro de auditoria do saldo físico resultante imediatamente após a baixa
    estoque_posterior = models.IntegerField(
        null=True, blank=True, verbose_name="Saldo de Estoque Posterior"
    )

    # Flag que acusa ocorrência de ruptura de estoque quando o saldo pós-venda fica menor que zero
    ruptura_estoque = models.BooleanField(
        default=False, verbose_name="Alerta de Ruptura (Saldo Negativo)"
    )

    # Configurações de metadados do modelo ItemPedidoVenda
    class Meta:
        verbose_name = "Item do Pedido de Venda"
        verbose_name_plural = "Itens dos Pedidos de Venda"

    # Representação textual do item vendido exibindo quantidade, título/ID e preço unitário
    def __str__(self):
        return f"{self.quantidade}x {self.titulo_anuncio or self.item_id_externo} (R$ {self.preco_unitario})"

    # Propriedade utilitária para leitura segura do ID externo do item
    @property
    def item_id(self) -> str:
        return self.item_id_externo or ""


# Aliases de compatibilidade para evitar quebras em módulos e códigos legados
Pedido = PedidoVenda
ItemPedido = ItemPedidoVenda
