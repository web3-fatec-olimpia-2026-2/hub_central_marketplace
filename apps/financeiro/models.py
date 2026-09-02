# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django.db import models

from apps.tenancy.models import Loja

MARKETPLACE_CHOICES = [
    ('mercadolivre_classico', 'Mercado Livre — Clássico (12% comissão)'),
    ('mercadolivre_premium', 'Mercado Livre — Premium (17% comissão)'),
    ('shopee', 'Shopee (14% comissão)'),
    ('magalu', 'Magazine Luiza (16% comissão)'),
    ('amazon', 'Amazon (15% comissão)'),
]


class ConfiguracaoTaxasLoja(models.Model):
    """
    O QUE FAZ: Parâmetros fiscais, de custos fixos e margens de segurança específicos de cada Loja (Tenant).
    POR QUE FAZ: Permite ao lojista configurar sua alíquota do Simples Nacional / Lucro Presumido, custos fixos e margem mínima.
    PERMISSÕES RBAC: DEV e ADMIN (edição); SUPERVISOR (leitura).
    MULTI-TENANCY: Relação OneToOneField estrita com Loja.
    """
    loja = models.OneToOneField(
        Loja, on_delete=models.CASCADE, related_name='config_taxas', verbose_name="Loja (Tenant)"
    )
    aliquota_imposto = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.0400'),
        verbose_name="Alíquota de Imposto (ex: 0.04 = 4%)",
        help_text="Percentual de imposto sobre faturamento bruto (Simples Nacional / ICMS)."
    )
    custo_embalagem_padrao = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('2.50'),
        verbose_name="Custo de Embalagem Padrão (R$)",
        help_text="Valor padrão aplicado a produtos que não possuem custo específico de embalagem."
    )
    margem_minima_seguranca = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.1500'),
        verbose_name="Margem Líquida Mínima de Segurança (ex: 0.15 = 15%)",
        help_text="Piso mínimo de margem desejada pela loja para classificar uma promoção como viável."
    )
    custos_fixos_mensais = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True,
        verbose_name="Custos Fixos Mensais da Operação (R$)",
        help_text="Soma de aluguel, salários, softwares e utilidades da loja."
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Configuração de Taxas da Loja"
        verbose_name_plural = "Configurações de Taxas das Lojas"

    def __str__(self):
        return f"Configurações Fiscais — {self.loja.nome}"


class ParametroCanalMarketplace(models.Model):
    """
    O QUE FAZ: Regras e taxas tarifárias por canal de marketplace (comissão %, piso de frete grátis e taxa fixa).
    POR QUE FAZ: Base do motor de formação de preço e resolução do frete por partes (Piecewise Linear).
    PERMISSÕES RBAC: DEV e ADMIN (edição); SUPERVISOR (leitura).
    MULTI-TENANCY: FK para Loja e unicidade composta ('loja', 'marketplace').
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='parametros_canais', verbose_name="Loja (Tenant)"
    )
    marketplace = models.CharField(
        max_length=50, choices=MARKETPLACE_CHOICES, verbose_name="Canal de Marketplace / Categoria de Anúncio"
    )
    comissao_padrao = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.1600'),
        verbose_name="Comissão do Marketplace (ex: 0.16 = 16%)",
        help_text="Taxa percentual cobrada pelo marketplace sobre o valor de venda."
    )
    frete_gratis_piso = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('79.00'),
        verbose_name="Piso de Frete Grátis Obrigatório (R$)",
        help_text="Acima deste valor, o frete é obrigatório e subsidiado pelo vendedor."
    )
    taxa_frete_acima_limite = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('18.00'),
        verbose_name="Custo de Frete Acima do Piso (R$)",
        help_text="Valor fixo debitado do vendedor para envios acima do piso de frete grátis."
    )
    taxa_fixa_abaixo_limite = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('6.00'),
        verbose_name="Taxa Fixa por Item Abaixo do Piso (R$)",
        help_text="Taxa administrativa cobrada em vendas de baixo ticket."
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Parâmetro de Canal de Marketplace"
        verbose_name_plural = "Parâmetros de Canais de Marketplaces"
        unique_together = ('loja', 'marketplace')

    def __str__(self):
        return f"[{self.get_marketplace_display()}] {self.loja.nome}"
