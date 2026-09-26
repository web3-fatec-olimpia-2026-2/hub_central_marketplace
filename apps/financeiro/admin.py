# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo administrativo padrão do Django para gerenciar a interface de administração
from django.contrib import admin

# Importa as entidades de modelo de taxas da loja e parâmetros de comissão de canais
from .models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace


# Decorador para registrar a entidade de configuração tributária e custos fixos da loja no Django Admin
@admin.register(ConfiguracaoTaxasLoja)
class ConfiguracaoTaxasLojaAdmin(admin.ModelAdmin):
    # Define as colunas visíveis na listagem: organização, impostos, embalagem base, margem mínima e custos operacionais
    list_display = ('loja', 'aliquota_imposto', 'custo_embalagem_padrao', 'margem_minima_seguranca', 'custos_fixos_mensais')

    # Habilita barra de pesquisa textual buscando diretamente pelo nome da Loja (tenant)
    search_fields = ('loja__nome',)


# Decorador para registrar os parâmetros de precificação, comissão e tarifas por canal de marketplace
@admin.register(ParametroCanalMarketplace)
class ParametroCanalMarketplaceAdmin(admin.ModelAdmin):
    # Exibe as colunas principais: loja dona, marketplace, comissão percentual e regras de corte de frete grátis e taxa fixa
    list_display = ('loja', 'marketplace', 'comissao_padrao', 'frete_gratis_piso', 'taxa_frete_acima_limite', 'taxa_fixa_abaixo_limite')

    # Habilita filtros laterais para segmentação rápida por canal integrado e organização
    list_filter = ('marketplace', 'loja')

    # Habilita busca por nome da loja ou nome do canal de marketplace configurado
    search_fields = ('loja__nome', 'marketplace')