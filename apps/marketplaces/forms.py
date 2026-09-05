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
            'loja', 'canal', 'apelido_conta', 'ativo'
        ]
        widgets = {
            'canal': forms.Select(attrs={'class': 'form-select'}),
            'apelido_conta': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Loja Principal ML, Shopee Oficial...',
                'autofocus': 'autofocus'
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

        # Imutabilidade estrita na tela de edição: Canal e Loja não podem ser alterados
        if self.instance and self.instance.pk:
            self.fields['canal'].disabled = True
            self.fields['canal'].help_text = "O canal de marketplace é imutável após a criação da conta."
            self.fields['loja'].disabled = True
            self.fields['loja'].help_text = "A loja (tenant) vinculada é imutável após a criação da conta."

    def clean(self):
        cleaned_data = super().clean()

        # Em edição, canal e loja são estritamente imutáveis e assumem os valores da instância original
        if self.instance and self.instance.pk:
            loja = self.instance.loja
            canal = self.instance.canal
            cleaned_data['loja'] = loja
            cleaned_data['canal'] = canal
        else:
            if not usuario_is_dev(self.autor):
                loja = getattr(self.autor.perfil, 'loja', None) if self.autor else None
                cleaned_data['loja'] = loja
            else:
                loja = cleaned_data.get('loja')
            canal = cleaned_data.get('canal')

        if not loja:
            self.add_error('loja', "A seleção de uma Loja é obrigatória.")

        if not canal:
            self.add_error('canal', "A seleção de um Canal é obrigatória.")

        apelido_conta = cleaned_data.get('apelido_conta')
        seller_id = cleaned_data.get('seller_id_externo')

        # 1. Trava Loja + Canal (apenas 1 conexão ativa por canal por loja)
        if loja and canal:
            qs_canal = ContaMarketplace.objects.filter(loja=loja, canal=canal)
            if self.instance and self.instance.pk:
                qs_canal = qs_canal.exclude(pk=self.instance.pk)
            if qs_canal.exists():
                canal_display = dict(CanalMarketplaceEnum.choices).get(canal, canal)
                self.add_error('canal', f"A loja '{loja.nome}' já possui uma conexão para o canal {canal_display}.")

        # 2. Trava Canal + Seller ID Externo (não pode ser reaproveitado por outra loja)
        if canal and seller_id:
            qs_seller = ContaMarketplace.objects.filter(canal=canal, seller_id_externo=seller_id)
            if self.instance and self.instance.pk:
                qs_seller = qs_seller.exclude(pk=self.instance.pk)
            if qs_seller.exists():
                canal_display = dict(CanalMarketplaceEnum.choices).get(canal, canal)
                self.add_error('seller_id_externo', f"O Seller ID Externo '{seller_id}' já está em uso por outra conta no canal {canal_display}.")

        # 3. Trava Loja + Apelido da Conta (único dentro da loja)
        if loja and apelido_conta:
            qs_apelido = ContaMarketplace.objects.filter(loja=loja, apelido_conta=apelido_conta)
            if self.instance and self.instance.pk:
                qs_apelido = qs_apelido.exclude(pk=self.instance.pk)
            if qs_apelido.exists():
                self.add_error('apelido_conta', f"Já existe uma conta com o apelido '{apelido_conta}' cadastrada para esta loja.")

        return cleaned_data
