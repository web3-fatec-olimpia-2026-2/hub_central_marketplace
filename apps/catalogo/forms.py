# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django import forms
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from apps.tenancy.models import Loja
from apps.tenancy.permissions import (
    usuario_is_dev, pode_alterar_preco, pode_ajustar_estoque_geral
)
from apps.marketplaces.models import ContaMarketplace
from .models import Categoria, Produto, AnuncioMarketplace
from .enums import StatusProdutoEnum, TipoAjusteEstoqueEnum


class CategoriaForm(forms.ModelForm):
    """
    O QUE FAZ: Formulário de cadastro e edição de Categoria de Produtos com isolamento multi-tenant.
    POR QUE FAZ: Valida nome, descrição e unicidade de slug por loja.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Vínculo automático à loja do autor.
    """
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Categoria
        fields = ['loja', 'nome', 'slug', 'descricao', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Calçados Masculinos, Informática...',
                'autofocus': 'autofocus'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gerado automaticamente a partir do nome'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição opcional da categoria...'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

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

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        nome = self.cleaned_data.get('nome', '').strip()
        if not slug and nome:
            slug = slugify(nome)
        return slug

    def clean(self):
        cleaned_data = super().clean()
        loja = cleaned_data.get('loja')
        if not usuario_is_dev(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja

        if not loja:
            self.add_error('loja', "A vinculação a uma Loja é obrigatória.")

        slug = cleaned_data.get('slug')
        if loja and slug:
            qs = Categoria.objects.filter(loja=loja, slug=slug)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('slug', f"Já existe uma categoria com o identificador '{slug}' nesta loja.")

        return cleaned_data


class ProdutoForm(forms.ModelForm):
    """
    O QUE FAZ: Formulário de cadastro e edição de Produto com controle de preço/estoque por perfil (RN-09).
    POR QUE FAZ: DEV, ADMIN e SUPERVISOR alteram preço e estoque mestre; USUARIO altera apenas dados descritivos (RN-09).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (Total); USUARIO (Descritivos apenas).
    MULTI-TENANCY: Validação estrita por loja do autor.
    """
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Produto
        fields = [
            'loja', 'categoria', 'sku', 'nome', 'descricao',
            'preco', 'estoque', 'status',
            'custo_aquisicao', 'custo_embalagem', 'modalidade_full'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={
                'class': 'form-control font-monospace text-uppercase',
                'placeholder': 'Ex: NOTE-DELL-G15',
                'autofocus': 'autofocus'
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Notebook Dell G15 16GB SSD 512GB'
            }),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Especificações técnicas e descrição do produto...'
            }),
            'preco': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': '0.00'
            }),
            'estoque': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0'
            }),
            'custo_aquisicao': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': '0.00'
            }),
            'custo_embalagem': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': '0.00 (0 para padrão)'
            }),
            'modalidade_full': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            loja_efetiva = self.instance.loja
        elif usuario_is_dev(self.autor):
            loja_efetiva = None
        else:
            loja_efetiva = getattr(self.autor.perfil, 'loja', None) if self.autor else None

        if usuario_is_dev(self.autor):
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].required = True
            if self.instance.pk:
                self.fields['loja'].initial = self.instance.loja
        else:
            self.fields['loja'].queryset = Loja.objects.filter(id=loja_efetiva.id) if loja_efetiva else Loja.objects.none()
            self.fields['loja'].initial = loja_efetiva
            self.fields['loja'].disabled = True

        if loja_efetiva:
            self.fields['categoria'].queryset = Categoria.objects.filter(loja=loja_efetiva, ativo=True).order_by('nome')
        elif usuario_is_dev(self.autor) and not self.instance.pk:
            self.fields['categoria'].queryset = Categoria.objects.filter(ativo=True).order_by('loja__nome', 'nome')
        else:
            self.fields['categoria'].queryset = Categoria.objects.none()

        # RN-09: Restrições de USUARIO
        if not pode_alterar_preco(self.autor):
            self.fields['preco'].disabled = True
            self.fields['preco'].help_text = "Seu perfil possui permissão de leitura sobre preços de venda (RN-09)."

        if not pode_ajustar_estoque_geral(self.autor):
            self.fields['estoque'].disabled = True
            self.fields['estoque'].help_text = "Ajuste geral restrito a gestores. Para avarias/perdas, utilize 'Baixa por Avaria' (RN-09)."

        self.fields['custo_aquisicao'].required = False
        self.fields['custo_embalagem'].required = False
        self.fields['modalidade_full'].required = False

    def clean_sku(self):
        sku = self.cleaned_data.get('sku', '').strip().upper()
        if not sku:
            raise ValidationError("O código SKU é obrigatório.")
        return sku

    def clean_estoque(self):
        estoque = self.cleaned_data.get('estoque')
        if estoque is not None and estoque < 0:
            raise ValidationError("O saldo de estoque não pode ser negativo no cadastro manual (RN-06).")
        return estoque

    def clean(self):
        cleaned_data = super().clean()

        if not usuario_is_dev(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja
        else:
            loja = cleaned_data.get('loja')

        if not loja:
            self.add_error('loja', "A vinculação a uma Loja é obrigatória.")

        sku = cleaned_data.get('sku')
        if loja and sku:
            qs = Produto.objects.filter(loja=loja, sku=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('sku', f"Já existe um produto com o SKU '{sku}' cadastrado nesta loja (RN-02).")

        preco = cleaned_data.get('preco')
        estoque = cleaned_data.get('estoque')

        # Se campos estiverem desabilitados para USUARIO, preserva valores da instância
        if not pode_alterar_preco(self.autor):
            preco = self.instance.preco if self.instance.pk else Decimal('0.00')
            cleaned_data['preco'] = preco

        if not pode_ajustar_estoque_geral(self.autor):
            estoque = self.instance.estoque if self.instance.pk else 0
            cleaned_data['estoque'] = estoque

        if preco is not None and preco < Decimal('0.00'):
            self.add_error('preco', "O preço de venda não pode ser negativo (RN-06).")
        if estoque is not None and estoque < 0:
            self.add_error('estoque', "O saldo de estoque não pode ser negativo (RN-06).")

        categoria = cleaned_data.get('categoria')
        if categoria and loja and categoria.loja_id != loja.id:
            self.add_error('categoria', "A categoria selecionada não pertence à loja deste produto.")

        return cleaned_data


class AnuncioMarketplaceForm(forms.ModelForm):
    """
    O QUE FAZ: Formulário para vincular um Anúncio em marketplace externo (MLB..., Shopee ID) a um Produto local.
    POR QUE FAZ: Permite associar o mesmo SKU a múltiplos canais de venda.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Filtra as contas de marketplace pertencentes à loja do produto.
    """
    class Meta:
        model = AnuncioMarketplace
        fields = ['conta_marketplace', 'item_id_externo', 'status_anuncio', 'preco_sincronizado', 'link_anuncio']
        widgets = {
            'conta_marketplace': forms.Select(attrs={'class': 'form-select'}),
            'item_id_externo': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Ex: MLB1234567890 ou 10029381'
            }),
            'status_anuncio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ativo, pausado...'
            }),
            'preco_sincronizado': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Preço anunciado no canal'
            }),
            'link_anuncio': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://...'
            }),
        }

    def __init__(self, *args, produto: Produto = None, **kwargs):
        self.produto = produto
        super().__init__(*args, **kwargs)
        if self.produto:
            self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                loja=self.produto.loja, ativo=True
            )

    def clean(self):
        cleaned_data = super().clean()
        conta = cleaned_data.get('conta_marketplace')
        item_id = cleaned_data.get('item_id_externo')

        if conta and item_id:
            qs = AnuncioMarketplace.objects.filter(conta_marketplace=conta, item_id_externo=item_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('item_id_externo', "Este identificador de anúncio já está vinculado a esta conta.")

        return cleaned_data


class ProdutoBaixaAvariaForm(forms.Form):
    """
    O QUE FAZ: Formulário de baixa pontual de estoque por motivo de avaria ou perda física (RN-09).
    POR QUE FAZ: Permite que todos os usuários autenticados da loja (inclusive USUARIO) registrem perdas operacionais com motivo obrigatório.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Restrito ao produto da loja do usuário.
    """
    quantidade = forms.IntegerField(
        label="Quantidade da Baixa",
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'placeholder': 'Ex: 1, 2, 5...',
            'autofocus': 'autofocus'
        })
    )
    tipo_baixa = forms.ChoiceField(
        label="Motivo da Baixa",
        choices=[
            (TipoAjusteEstoqueEnum.SAIDA_AVARIA, 'Avaria / Defeito no Produto'),
            (TipoAjusteEstoqueEnum.SAIDA_PERDA, 'Perda / Extravio no Estoque'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    justificativa = forms.CharField(
        label="Justificativa / Descrição do Ocorrido (Obrigatório)",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Produto avariado na embalagem / Caixa danificada'
        })
    )

    def __init__(self, *args, produto=None, **kwargs):
        self.produto = produto
        super().__init__(*args, **kwargs)

    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade', 0)
        if self.produto:
            if self.produto.estoque <= 0:
                raise ValidationError("Este produto já está com saldo de estoque zerado.")
            if quantidade > self.produto.estoque:
                raise ValidationError(
                    f"A quantidade informada ({quantidade}) é maior do que o saldo atual ({self.produto.estoque})."
                )
        return quantidade


class ProdutoAjusteEstoqueForm(forms.Form):
    """
    O QUE FAZ: Formulário para ajuste geral de saldo de estoque por gestores.
    POR QUE FAZ: Balanço físico e entradas de lote por gestores autorizados (DEV, ADMIN, SUPERVISOR).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (USUARIO é bloqueado por RN-09).
    MULTI-TENANCY: Restrito à loja do usuário.
    """
    novo_estoque = forms.IntegerField(
        label="Novo Saldo de Estoque",
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'placeholder': 'Digite o novo saldo físico total...',
            'autofocus': 'autofocus'
        })
    )
    tipo_ajuste = forms.ChoiceField(
        label="Tipo de Movimentação",
        choices=TipoAjusteEstoqueEnum.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    justificativa = forms.CharField(
        label="Justificativa do Ajuste",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Balanço físico mensal / Entrada de estoque'
        })
    )


class ProdutoSincronizacaoLoteForm(forms.Form):
    """
    O QUE FAZ: Validação de IDs de produtos selecionados para sincronização de preço em lote.
    """
    produtos_ids = forms.CharField(widget=forms.HiddenInput())

    def clean_produtos_ids(self):
        raw_ids = self.cleaned_data.get('produtos_ids', '').strip()
        if not raw_ids:
            raise ValidationError("Nenhum produto foi selecionado para sincronização.")
        try:
            ids = [int(x.strip()) for x in raw_ids.split(',') if x.strip()]
        except ValueError:
            raise ValidationError("Lista de IDs inválida.")
        if not ids:
            raise ValidationError("Nenhum produto válido selecionado.")
        return ids


class PublicarAnuncioForm(forms.Form):
    """
    O QUE FAZ: Formulário de publicação de anúncio em marketplace para um produto do catálogo (RF-04).
    POR QUE FAZ: Permite ao operador selecionar a conta de destino, tipo de listagem (Clássico/Premium) e preço de envio.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO bloqueado).
    MULTI-TENANCY: Filtra apenas contas da loja do produto / usuário (DEV pode ver todas com identificador da loja).
    """
    LISTING_TYPES = [
        ('gold_special', 'Clássico (gold_special) — Menor taxa de comissão'),
        ('gold_pro', 'Premium (gold_pro) — Parcelamento sem juros / Maior visibilidade'),
    ]

    conta_marketplace = forms.ModelChoiceField(
        label="Conta de Marketplace de Destino *",
        queryset=ContaMarketplace.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Selecione a conta integrada onde o anúncio será publicado."
    )
    listing_type_id = forms.ChoiceField(
        label="Tipo de Listagem / Exposição",
        choices=LISTING_TYPES,
        initial='gold_special',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Modalidade de anúncio no canal (ex: Clássico ou Premium no Mercado Livre)."
    )
    preco = forms.DecimalField(
        label="Preço de Publicação (R$) *",
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control font-monospace', 'step': '0.01'}),
        help_text="Preço inicial com o qual o anúncio será publicado no marketplace."
    )
    category_id = forms.CharField(
        label="ID da Categoria Externa (Opcional)",
        required=False,
        initial="MLB3530",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: MLB3530'}),
        help_text="Identificador da folha de categoria no canal de destino (fallback: MLB3530)."
    )

    def __init__(self, *args, produto=None, autor=None, **kwargs):
        self.produto = produto
        self.autor = autor
        super().__init__(*args, **kwargs)

        if produto:
            self.fields['preco'].initial = produto.preco

        if usuario_is_dev(autor):
            if produto and produto.loja:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                    loja=produto.loja, ativo=True
                ).order_by('canal', 'apelido_conta')
            else:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                    ativo=True
                ).select_related('loja').order_by('loja__nome', 'canal')
        else:
            perfil = getattr(autor, 'perfil', None)
            if perfil and perfil.loja:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                    loja=perfil.loja, ativo=True
                ).order_by('canal', 'apelido_conta')
            else:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.none()
