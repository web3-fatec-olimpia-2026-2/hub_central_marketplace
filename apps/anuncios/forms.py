# Os códigos foram gerados com auxilio de I.A.
"""
Formulários e Formsets para o Módulo de Anúncios e Composições Comerciais (ADR-003 e ADR-009).
Suporta criação manual direta de anúncios e gestão de composições heterogêneas multiproduto (kits/combos).
"""
from decimal import Decimal
from django import forms
from django.core.validators import MinValueValidator

from apps.tenancy.permissions import usuario_is_dev
from apps.marketplaces.models import ContaMarketplace
from apps.catalogo.models import Produto
from apps.catalogo.enums import StatusProdutoEnum
from apps.anuncios.models import Anuncio, AnuncioComposicao


class AnuncioForm(forms.ModelForm):
    """
    Formulário para cadastro e edição manual direta de Anúncios nos Marketplaces.
    Isola a seleção de ContaMarketplace estritamente ao tenant do usuário logado (ADR-003).
    """
    class Meta:
        model = Anuncio
        fields = [
            'conta',
            'item_id_externo',
            'titulo',
            'sku_vendedor',
            'preco_venda',
            'status'
        ]
        widgets = {
            'conta': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'item_id_externo': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Ex: MLB123456789 ou SKU-EXTERNO',
                'required': True
            }),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título comercial exibido no marketplace',
                'required': True
            }),
            'sku_vendedor': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Código SKU comercial do anúncio'
            }),
            'preco_venda': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00',
                'required': True
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Escopo Multi-Tenant de Contas (ADR-003):
        # Em edição de anúncio existente, a conta pertence estritamente à loja do anúncio (mesmo para DEV).
        if self.instance and getattr(self.instance, 'conta_id', None):
            loja_anuncio = self.instance.conta.loja
            self.fields['conta'].queryset = ContaMarketplace.objects.filter(
                loja=loja_anuncio, ativo=True
            ).order_by('apelido_conta')
        elif user:
            if usuario_is_dev(user):
                self.fields['conta'].queryset = ContaMarketplace.objects.filter(
                    ativo=True
                ).select_related('loja').order_by('apelido_conta')
            else:
                perfil = getattr(user, 'perfil', None)
                loja = getattr(perfil, 'loja', None) if perfil else None
                if loja:
                    self.fields['conta'].queryset = ContaMarketplace.objects.filter(
                        loja=loja, ativo=True
                    ).order_by('apelido_conta')
                else:
                    self.fields['conta'].queryset = ContaMarketplace.objects.none()

        self.fields['conta'].empty_label = "Selecione a conta de integração..."


class AnuncioComposicaoItemForm(forms.ModelForm):
    """
    Formulário individual para cada componente físico vinculado ao Anúncio na Composição (Ficha Técnica).
    Garante isolamento estrito por Loja mesmo quando acessado por operador com papel DEV.
    """
    quantidade = forms.IntegerField(
        min_value=1,
        validators=[MinValueValidator(1)],
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control text-center fw-bold input-item-qtd',
            'min': 1,
            'value': 1,
            'placeholder': '1'
        })
    )

    class Meta:
        model = AnuncioComposicao
        fields = ['produto', 'quantidade']
        widgets = {
            'produto': forms.Select(attrs={
                'class': 'form-select select-item-produto',
                'required': True
            }),
        }

    def __init__(self, *args, loja=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loja = loja
        self.user = user

        # Se não informada diretamente, infere a loja a partir da instância do anúncio
        if not self.loja and self.instance and getattr(self.instance, 'anuncio_id', None):
            self.loja = self.instance.anuncio.conta.loja

        # Escopo Multi-Tenant Estrito de Produtos (ADR-003):
        # Mesmo para usuário DEV, os produtos DEVEM ser restritos à loja do anúncio em questão.
        if self.loja:
            self.fields['produto'].queryset = Produto.objects.filter(
                loja=self.loja, status=StatusProdutoEnum.ATIVO
            ).order_by('nome')
        elif user and not usuario_is_dev(user):
            perfil = getattr(user, 'perfil', None)
            loja_user = getattr(perfil, 'loja', None) if perfil else None
            if loja_user:
                self.fields['produto'].queryset = Produto.objects.filter(
                    loja=loja_user, status=StatusProdutoEnum.ATIVO
                ).order_by('nome')
            else:
                self.fields['produto'].queryset = Produto.objects.none()
        else:
            # DEV sem loja vinculada à conta ainda não pode vincular produtos aleatórios
            self.fields['produto'].queryset = Produto.objects.none()

        self.fields['produto'].empty_label = "Selecione um produto físico do catálogo..."


class BaseAnuncioComposicaoFormSet(forms.BaseInlineFormSet):
    """
    Formset com validações de integridade e multi-tenancy para composições de anúncios:
    1. Impede a duplicação do mesmo produto físico em mais de uma linha de composição.
    2. Garante que todos os produtos pertençam estritamente à mesma Loja da conta do anúncio (ADR-003), inclusive para usuário DEV.
    """
    def __init__(self, *args, loja=None, user=None, **kwargs):
        self.loja = loja
        self.user = user
        if not self.loja and self.instance and getattr(self.instance, 'conta_id', None):
            self.loja = self.instance.conta.loja
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        loja_efetiva = self.loja
        if not loja_efetiva and self.instance and getattr(self.instance, 'conta_id', None):
            loja_efetiva = self.instance.conta.loja
        kwargs['loja'] = loja_efetiva
        kwargs['user'] = self.user
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        produtos_vistos = set()
        loja_alvo = self.loja

        if self.instance and getattr(self.instance, 'conta_id', None):
            loja_alvo = self.instance.conta.loja

        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            produto = form.cleaned_data.get('produto')
            if produto:
                # 1. Validação de Unicidade no Anúncio: mesmo produto não pode aparecer mais de uma vez
                if produto.id in produtos_vistos:
                    raise forms.ValidationError(
                        f"O produto '{produto.nome}' (SKU: {produto.sku}) foi adicionado mais de uma vez na composição. "
                        f"Agrupe as unidades desejadas em uma única linha."
                    )
                produtos_vistos.add(produto.id)

                # 2. Validação Multi-Tenant Estrita (ADR-003) mesmo para DEV: produto deve pertencer à mesma Loja
                if loja_alvo and produto.loja_id != loja_alvo.id:
                    raise forms.ValidationError(
                        f"O produto '{produto.nome}' pertence à loja '{produto.loja.nome}', mas a conta do anúncio "
                        f"pertence à loja '{loja_alvo.nome}'. Todos os componentes devem pertencer ao mesmo Tenant."
                    )


AnuncioComposicaoInlineFormSet = forms.inlineformset_factory(
    Anuncio,
    AnuncioComposicao,
    form=AnuncioComposicaoItemForm,
    formset=BaseAnuncioComposicaoFormSet,
    extra=1,
    can_delete=True
)


class AnuncioComposicaoForm(forms.ModelForm):
    """
    Formulário para vincular pontualmente um produto físico a um anúncio existente (via modal/detail).
    """
    class Meta:
        model = AnuncioComposicao
        fields = ['produto', 'quantidade']
        widgets = {
            'produto': forms.Select(attrs={'class': 'form-select select2'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
        }

    def __init__(self, *args, anuncio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if anuncio:
            loja = anuncio.conta.loja
            self.fields['produto'].queryset = Produto.objects.filter(
                loja=loja, status=StatusProdutoEnum.ATIVO
            ).order_by('nome')
