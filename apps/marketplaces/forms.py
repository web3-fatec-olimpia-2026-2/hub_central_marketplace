# Os códigos foram gerados com auxilio de I.A.
from django import forms
from django.core.exceptions import ValidationError

from apps.tenancy.models import Loja
from apps.tenancy.permissions import usuario_is_dev
from .models import ContaMarketplace
from .enums import CanalMarketplaceEnum


class ContaMarketplaceForm(forms.ModelForm):
    """
    O QUE FAZ: Formulário de cadastro e edição de Contas e Conexões de Marketplaces.
    POR QUE FAZ: Permite configurar credenciais de múltiplos canais (Mercado Livre, Shopee, Magalu, Amazon) por loja.
    PERMISSÕES RBAC: DEV e ADMIN (sua própria loja).
    MULTI-TENANCY: Vínculo automático à loja do autor (ou seleção por DEV).
    """
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = ContaMarketplace
        fields = [
            'loja', 'canal', 'apelido_conta', 'ativo',
            'client_id', 'client_secret', 'access_token', 'refresh_token',
            'seller_id_externo'
        ]
        widgets = {
            'canal': forms.Select(attrs={'class': 'form-select'}),
            'apelido_conta': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Loja Principal ML, Shopee Oficial...',
                'autofocus': 'autofocus'
            }),
            'client_id': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'App ID / Client ID'
            }),
            'client_secret': forms.PasswordInput(render_value=True, attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Client Secret / Chave Secreta'
            }),
            'access_token': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Bearer Access Token...'
            }),
            'refresh_token': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Refresh Token...'
            }),
            'seller_id_externo': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'ID do Vendedor no Marketplace (Ex: 12345678)'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)

        if usuario_is_dev(self.autor):
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].required = True
            if self.instance.pk:
                self.fields['loja'].initial = self.instance.loja
        else:
            loja_autor = getattr(self.autor.perfil, 'loja', None) if self.autor else None
            self.fields['loja'].queryset = Loja.objects.filter(id=loja_autor.id) if loja_autor else Loja.objects.none()
            self.fields['loja'].initial = loja_autor
            self.fields['loja'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        if not usuario_is_dev(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja
        else:
            loja = cleaned_data.get('loja')

        if not loja:
            self.add_error('loja', "A seleção de uma Loja é obrigatória.")

        canal = cleaned_data.get('canal')
        seller_id = cleaned_data.get('seller_id_externo')

        if loja and canal and seller_id:
            qs = ContaMarketplace.objects.filter(loja=loja, canal=canal, seller_id_externo=seller_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('seller_id_externo', "Já existe uma conta cadastrada para este canal e seller ID nesta loja.")

        return cleaned_data
