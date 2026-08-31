from django import forms
from django.utils.text import slugify
from .models import Loja


class LojaForm(forms.ModelForm):
    """
    Formulário para provisionamento e edição de Lojas (Tenants) pelo perfil DEV.
    """
    class Meta:
        model = Loja
        fields = [
            'nome', 'slug', 'cnpj', 'inscricao_estadual',
            'telefone', 'email',
            'cep', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'pais',
            'ativo',
            'meli_client_id', 'meli_client_secret',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Loja Matriz E-commerce',
                'autofocus': 'autofocus'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gerado automaticamente a partir do nome (ou defina um personalizado)'
            }),
            'cnpj': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00.000.000/0000-00',
                'maxlength': '20'
            }),
            'inscricao_estadual': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 123.456.789.000 ou Isento'
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(00) 00000-0000'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contato@loja.com.br'
            }),
            'cep': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00000-000',
                'maxlength': '10'
            }),
            'endereco': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Rua, Avenida, Alameda...'
            }),
            'numero': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123'
            }),
            'complemento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Sala 101, Galpão B...'
            }),
            'bairro': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Centro, Distrito Industrial...'
            }),
            'cidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'São Paulo'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select'
            }),
            'pais': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brasil'
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'meli_client_id': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Application ID do Mercado Livre Developers'
            }),
            'meli_client_secret': forms.PasswordInput(render_value=True, attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Secret Key do Mercado Livre Developers'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O campo slug não é obrigatório no form pois é gerado automaticamente a partir do nome
        self.fields['slug'].required = False
        self.fields['pais'].initial = 'Brasil'

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get('cnpj', '').strip()
        # Normalização básica de caracteres
        return cnpj

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        nome = self.cleaned_data.get('nome', '').strip()
        if not slug and nome:
            slug = slugify(nome)
        return slug
