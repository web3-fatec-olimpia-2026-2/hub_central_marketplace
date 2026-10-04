# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Formulários de configuração de parâmetros fiscais de loja e tarifas por canal de marketplace.
POR QUE FAZ: Desacopla a gestão de taxas e comissões do Django Admin para a interface padrão do Hub.
PERMISSÕES RBAC: DEV e ADMIN (edição); restrito pelo isolamento multi-tenant.
MULTI-TENANCY: Usuários comuns operam apenas os parâmetros de sua própria loja.
"""

from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError

from apps.tenancy.models import Loja
from apps.tenancy.permissions import usuario_is_dev
from .models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace, MARKETPLACE_CHOICES


class ConfiguracaoTaxasLojaForm(forms.ModelForm):
    """
    Formulário para parametrização fiscal, custos fixos e margens de segurança de uma Loja.
    """
    class Meta:
        model = ConfiguracaoTaxasLoja
        fields = [
            'aliquota_imposto',
            'custo_embalagem_padrao',
            'margem_minima_seguranca',
            'custos_fixos_mensais',
        ]
        widgets = {
            'aliquota_imposto': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'min': '0',
                'max': '1',
                'placeholder': '0.0400'
            }),
            'custo_embalagem_padrao': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '2.50'
            }),
            'margem_minima_seguranca': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'min': '0',
                'max': '1',
                'placeholder': '0.1500'
            }),
            'custos_fixos_mensais': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
        }

    def clean_aliquota_imposto(self):
        val = self.cleaned_data.get('aliquota_imposto')
        if val is not None and (val < 0 or val > 1):
            raise ValidationError("A alíquota de imposto deve estar entre 0.0000 (0%) e 1.0000 (100%).")
        return val

    def clean_margem_minima_seguranca(self):
        val = self.cleaned_data.get('margem_minima_seguranca')
        if val is not None and (val < 0 or val > 1):
            raise ValidationError("A margem mínima de segurança deve estar entre 0.0000 (0%) e 1.0000 (100%).")
        return val


class ParametroCanalMarketplaceForm(forms.ModelForm):
    """
    Formulário para definição e edição de tarifas e comissões por canal de marketplace.
    """
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = ParametroCanalMarketplace
        fields = [
            'loja',
            'marketplace',
            'comissao_padrao',
            'frete_gratis_piso',
            'taxa_frete_acima_limite',
            'taxa_fixa_abaixo_limite',
        ]
        widgets = {
            'marketplace': forms.Select(attrs={'class': 'form-select'}),
            'comissao_padrao': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'min': '0',
                'max': '1',
                'placeholder': '0.1600'
            }),
            'frete_gratis_piso': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '79.00'
            }),
            'taxa_frete_acima_limite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '18.00'
            }),
            'taxa_fixa_abaixo_limite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '6.00'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        is_dev = usuario_is_dev(self.user)
        if is_dev:
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].required = True
        else:
            # Para operador de loja, a loja é fixada automaticamente
            perfil = getattr(self.user, 'perfil', None) if self.user else None
            loja_usuario = perfil.loja if perfil else None
            if loja_usuario:
                self.fields['loja'].queryset = Loja.objects.filter(pk=loja_usuario.pk)
                self.fields['loja'].initial = loja_usuario
                self.fields['loja'].widget = forms.HiddenInput()
                self.fields['loja'].required = False
            else:
                self.fields['loja'].widget = forms.HiddenInput()
                self.fields['loja'].required = False

        if self.instance and self.instance.pk:
            # Na edição de parâmetro existente, marketplace e loja não devem ser alterados
            self.fields['marketplace'].disabled = True
            if 'loja' in self.fields:
                self.fields['loja'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        is_dev = usuario_is_dev(self.user)

        if not is_dev:
            perfil = getattr(self.user, 'perfil', None) if self.user else None
            if perfil and perfil.loja:
                cleaned_data['loja'] = perfil.loja
            else:
                raise ValidationError("Usuário não possui loja associada para configurar parâmetros.")

        # Valida duplicidade ao criar
        if not self.instance.pk:
            loja = cleaned_data.get('loja')
            marketplace = cleaned_data.get('marketplace')
            if loja and marketplace:
                if ParametroCanalMarketplace.objects.filter(loja=loja, marketplace=marketplace).exists():
                    raise ValidationError(f"A loja '{loja.nome}' já possui parâmetros configurados para este marketplace.")

        return cleaned_data
