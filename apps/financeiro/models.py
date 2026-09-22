# Os códigos foram gerados com auxilio de I.A.

# Importa a classe Decimal para cálculos monetários e percentuais exatos, prevenindo imprecisões de ponto flutuante
from decimal import Decimal

# Importa o módulo central de modelos ORM do framework Django
from django.db import models

# Importa o modelo Loja que representa a entidade do tenant para isolamento de dados
from apps.tenancy.models import Loja

# Lista de opções tupladas para mapeamento dos canais de marketplace e modalidades tarifárias suportadas
MARKETPLACE_CHOICES = [
    # Opção para a modalidade clássica do Mercado Livre com taxa padrão de 12%
    ('mercadolivre_classico', 'Mercado Livre — Clássico (12% comissão)'),
    # Opção para a modalidade premium do Mercado Livre com taxa padrão de 17%
    ('mercadolivre_premium', 'Mercado Livre — Premium (17% comissão)'),
    # Opção para a plataforma Shopee com comissão base de 14%
    ('shopee', 'Shopee (14% comissão)'),
    # Opção para o canal Magazine Luiza com comissão padrão de 16%
    ('magalu', 'Magazine Luiza (16% comissão)'),
    # Opção para o canal Amazon com taxa comissional de 15%
    ('amazon', 'Amazon (15% comissão)'),
]


# Modelo representativo das diretrizes fiscais, operacionais e de margem de lucro exclusivas da loja
class ConfiguracaoTaxasLoja(models.Model):
    # Início do bloco de docstring que documenta o objetivo, conformidade tributária e restrições RBAC do modelo
    """
    O QUE FAZ: Parâmetros fiscais, de custos fixos e margens de segurança específicos de cada Loja (Tenant).
    POR QUE FAZ: Permite ao lojista configurar sua alíquota do Simples Nacional / Lucro Presumido, custos fixos e margem mínima.
    PERMISSÕES RBAC: DEV e ADMIN (edição); SUPERVISOR (leitura).
    MULTI-TENANCY: Relação OneToOneField estrita com Loja.
    """
    # Fim do bloco de docstring explicativo do modelo

    # Relacionamento 1:1 obrigatório com a Loja com exclusão em cascata (cada loja possui apenas uma configuração fiscal ativa)
    loja = models.OneToOneField(
        Loja, on_delete=models.CASCADE, related_name='config_taxas', verbose_name="Loja (Tenant)"
    )

    # Alíquota tributária percentual (armazenada em formato decimal com 4 casas, padrão 0.0400 = 4%)
    aliquota_imposto = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.0400'),
        verbose_name="Alíquota de Imposto (ex: 0.04 = 4%)",
        help_text="Percentual de imposto sobre faturamento bruto (Simples Nacional / ICMS)."
    )

    # Custo padrão de materiais de expedição e embalagem aplicado a itens que não tenham custo individualizado
    custo_embalagem_padrao = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('2.50'),
        verbose_name="Custo de Embalagem Padrão (R$)",
        help_text="Valor padrão aplicado a produtos que não possuem custo específico de embalagem."
    )

    # Margem líquida mínima aceitável utilizada como piso para validar a viabilidade de campanhas e promoções (padrão 0.1500 = 15%)
    margem_minima_seguranca = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.1500'),
        verbose_name="Margem Líquida Mínima de Segurança (ex: 0.15 = 15%)",
        help_text="Piso mínimo de margem desejada pela loja para classificar uma promoção como viável."
    )

    # Custo operacional fixo total do mês para rateio e apuração de ponto de equilíbrio (breakeven)
    custos_fixos_mensais = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True,
        verbose_name="Custos Fixos Mensais da Operação (R$)",
        help_text="Soma de aluguel, salários, softwares e utilidades da loja."
    )

    # Carimbo temporal de data e hora em que a configuração fiscal foi criada no banco
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    # Carimbo temporal atualizado automaticamente a cada modificação nos dados da configuração
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Metadados de exibição no Django Admin
    class Meta:
        verbose_name = "Configuração de Taxas da Loja"
        verbose_name_plural = "Configurações de Taxas das Lojas"

    # Representação textual legível exibindo o nome da loja dona da configuração fiscal
    def __str__(self):
        return f"Configurações Fiscais — {self.loja.nome}"


# Modelo que parametriza as tarifas de comissão, frete subsidiado e taxas fixas específicas de cada marketplace
class ParametroCanalMarketplace(models.Model):
    # Início do bloco de docstring documentando a modelagem da precificação por partes (Piecewise Linear)
    """
    O QUE FAZ: Regras e taxas tarifárias por canal de marketplace (comissão %, piso de frete grátis e taxa fixa).
    POR QUE FAZ: Base do motor de formação de preço e resolução do frete por partes (Piecewise Linear).
    PERMISSÕES RBAC: DEV e ADMIN (edição); SUPERVISOR (leitura).
    MULTI-TENANCY: FK para Loja e unicidade composta ('loja', 'marketplace').
    """
    # Fim do bloco de docstring dos parâmetros de canais

    # Chave estrangeira que vincula a parametrização à Loja dona das regras comerciais
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='parametros_canais', verbose_name="Loja (Tenant)"
    )

    # Canal de integração parametrizado de acordo com as opções definidas em MARKETPLACE_CHOICES
    marketplace = models.CharField(
        max_length=50, choices=MARKETPLACE_CHOICES, verbose_name="Canal de Marketplace / Categoria de Anúncio"
    )

    # Percentual da comissão administrativa cobrada pelo canal (padrão 0.1600 = 16%)
    comissao_padrao = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.1600'),
        verbose_name="Comissão do Marketplace (ex: 0.16 = 16%)",
        help_text="Taxa percentual cobrada pelo marketplace sobre o valor de venda."
    )

    # Valor de corte monetário no ticket da oferta a partir do qual o frete grátis torna-se compulsório (ex: R$ 79,00)
    frete_gratis_piso = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('79.00'),
        verbose_name="Piso de Frete Grátis Obrigatório (R$)",
        help_text="Acima deste valor, o frete é obrigatório e subsidiado pelo vendedor."
    )

    # Custo fixo de frete transferido ao lojista quando o anúncio atinge ou supera o piso de frete grátis
    taxa_frete_acima_limite = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('18.00'),
        verbose_name="Custo de Frete Acima do Piso (R$)",
        help_text="Valor fixo debitado do vendedor para envios acima do piso de frete grátis."
    )

    # Taxa fixa cobrada pela plataforma parceira para transações de baixo valor comercial (abaixo do piso de frete grátis)
    taxa_fixa_abaixo_limite = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('6.00'),
        verbose_name="Taxa Fixa por Item Abaixo do Piso (R$)",
        help_text="Taxa administrativa cobrada em vendas de baixo ticket."
    )

    # Data e hora do registro inicial dos parâmetros do canal
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    # Data e hora da última mutação cadastral nos parâmetros tarifários
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Metadados e restrições de integridade relacional
    class Meta:
        verbose_name = "Parâmetro de Canal de Marketplace"
        verbose_name_plural = "Parâmetros de Canais de Marketplaces"
        # Restrição de unicidade composta impedindo duplicação de regras do mesmo marketplace para a mesma Loja
        unique_together = ('loja', 'marketplace')

    # Representação em texto exibindo o nome comercial formatado do canal e a loja associada
    def __str__(self):
        return f"[{self.get_marketplace_display()}] {self.loja.nome}"
