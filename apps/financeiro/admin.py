# Os códigos foram gerados com auxilio de I.A.
from django.contrib import admin
from .models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace


@admin.register(ConfiguracaoTaxasLoja)
class ConfiguracaoTaxasLojaAdmin(admin.ModelAdmin):
    list_display = ('loja', 'aliquota_imposto', 'custo_embalagem_padrao', 'margem_minima_seguranca', 'custos_fixos_mensais')
    search_fields = ('loja__nome',)


@admin.register(ParametroCanalMarketplace)
class ParametroCanalMarketplaceAdmin(admin.ModelAdmin):
    list_display = ('loja', 'marketplace', 'comissao_padrao', 'frete_gratis_piso', 'taxa_frete_acima_limite', 'taxa_fixa_abaixo_limite')
    list_filter = ('marketplace', 'loja')
    search_fields = ('loja__nome', 'marketplace')
