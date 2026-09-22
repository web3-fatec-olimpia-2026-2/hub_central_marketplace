# Os códigos foram gerados com auxilio de I.A.

# Importa a classe Decimal para manipulação financeira e operações aritméticas com precisão monetária
from decimal import Decimal

# Importa o módulo de formulários do framework Django
from django import forms

# Importa a função utilitária slugify para converter títulos e nomes em slugs normalizados para URLs
from django.utils.text import slugify

# Importa a exceção de validação padrão utilizada para interceptar e disparar erros de formulário
from django.core.exceptions import ValidationError

# Importa o modelo Loja que representa a entidade inquilina (tenant) no sistema
from apps.tenancy.models import Loja

# Importa as funções auxiliares que avaliam permissões de perfil (RBAC) para regras de negócio específicas
from apps.tenancy.permissions import (
    usuario_is_dev, pode_alterar_preco, pode_ajustar_estoque_geral
)

# Importa o modelo de Contas de Marketplace integradas
from apps.marketplaces.models import ContaMarketplace

# Importa as entidades de Categoria, Produto e Anúncio vinculadas ao catálogo
from .models import Categoria, Produto, AnuncioMarketplace

# Importa os enums que padronizam o status do produto e os tipos de movimentação de estoque
from .enums import StatusProdutoEnum, TipoAjusteEstoqueEnum


# Formulário baseado em modelo para cadastro e manutenção de Categorias de produtos
class CategoriaForm(forms.ModelForm):
    # Docstring documentando a responsabilidade arquitetural, validações de unicidade e isolamento multi-tenant
    """
    O QUE FAZ: Formulário de cadastro e edição de Categoria de Produtos com isolamento multi-tenant.
    POR QUE FAZ: Valida nome, descrição e unicidade de slug por loja.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Vínculo automático à loja do autor.
    """

    # Campo de seleção da Loja dona da categoria, inicializado com queryset vazio por proteção defensiva
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Metadados internos vinculando o formulário à entidade Categoria
    class Meta:
        model = Categoria
        fields = ['loja', 'nome', 'slug', 'descricao', 'ativo']
        # Dicionário de customização visual dos elementos de interface HTML (widgets)
        widgets = {
            # Campo de texto para o nome com foco automático na renderização
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Calçados Masculinos, Informática...',
                'autofocus': 'autofocus'
            }),
            # Campo de texto para o slug com texto de orientação sobre geração automática
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gerado automaticamente a partir do nome'
            }),
            # Área de texto multilinha para descrição da categoria
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição opcional da categoria...'
            }),
            # Checkbox com estilo Bootstrap para ativação/desativação da categoria
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # Construtor customizado para isolar a loja conforme o usuário autor da requisição
    def __init__(self, *args, autor=None, **kwargs):
        # Armazena o usuário autor na instância do formulário
        self.autor = autor
        # Invoca a inicialização padrão da classe ModelForm
        super().__init__(*args, **kwargs)
        # Define o campo slug como opcional no HTML para permitir que o backend gere caso não seja digitado
        self.fields['slug'].required = False

        # Se o usuário possuir papel global de desenvolvedor (DEV)
        if usuario_is_dev(self.autor):
            # Disponibiliza todas as lojas ativas ordenadas por nome para seleção livre
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            # Torna a seleção explícita da loja obrigatória para o desenvolvedor
            self.fields['loja'].required = True
            # Se for edição de categoria já existente, pré-seleciona a loja da instância
            if self.instance.pk:
                self.fields['loja'].initial = self.instance.loja
        # Fluxo para usuários regulares pertencentes a um tenant específico
        else:
            # Obtém a loja do perfil do usuário autor
            loja_autor = getattr(self.autor.perfil, 'loja', None) if self.autor else None
            # Restringe o queryset exclusivamente à loja do autor
            self.fields['loja'].queryset = Loja.objects.filter(id=loja_autor.id) if loja_autor else Loja.objects.none()
            # Pré-define a loja do autor como valor inicial
            self.fields['loja'].initial = loja_autor
            # Trava o select impedindo o usuário de alterar sua loja no front-end
            self.fields['loja'].disabled = True

    # Método de limpeza e normalização específica do campo slug
    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        nome = self.cleaned_data.get('nome', '').strip()
        # Se o usuário não informou um slug manualmente, gera a partir do nome
        if not slug and nome:
            slug = slugify(nome)
        return slug

    # Validação geral do formulário garantindo unicidade de slug por loja (tenant)
    def clean(self):
        cleaned_data = super().clean()
        loja = cleaned_data.get('loja')
        # Para usuários não-DEV, força a loja como sendo a do autor independentemente do que veio no POST
        if not usuario_is_dev(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja

        # Bloqueia a gravação caso a loja não tenha sido determinada
        if not loja:
            self.add_error('loja', "A vinculação a uma Loja é obrigatória.")

        slug = cleaned_data.get('slug')
        # Validação de unicidade: impede slugs duplicados dentro da mesma loja
        if loja and slug:
            qs = Categoria.objects.filter(loja=loja, slug=slug)
            # Em caso de edição de registro existente, desconsidera o próprio registro na checagem
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            # Dispara erro caso outro registro com o mesmo slug seja encontrado na loja
            if qs.exists():
                self.add_error('slug', f"Já existe uma categoria com o identificador '{slug}' nesta loja.")

        return cleaned_data


# Formulário principal de cadastro e edição de Produtos físicos no catálogo
class ProdutoForm(forms.ModelForm):
    # Docstring documentando a conformidade com regras RBAC de preço e estoque (RN-09)
    """
    O QUE FAZ: Formulário de cadastro e edição de Produto com controle de preço/estoque por perfil (RN-09).
    POR QUE FAZ: DEV, ADMIN e SUPERVISOR alteram preço e estoque mestre; USUARIO altera apenas dados descritivos (RN-09).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (Total); USUARIO (Descritivos apenas).
    MULTI-TENANCY: Validação estrita por loja do autor.
    """

    # Campo de seleção da Loja inquilina inicializado com queryset vazio
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Metadados relacionando o formulário à entidade Produto e declarando os campos manipuláveis
    class Meta:
        model = Produto
        fields = [
            'loja', 'categoria', 'sku', 'nome', 'descricao',
            'preco', 'estoque', 'status',
            'custo_aquisicao', 'custo_embalagem', 'modalidade_full'
        ]
        # Customização detalhada dos inputs e selects do produto
        widgets = {
            # Código SKU em maiúsculas com fonte monoespaçada
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
            # Preço com incremento centesimal
            'preco': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': '0.00'
            }),
            # Saldo físico de estoque inteiro não-negativo
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

    # Construtor que aplica as regras de segurança RBAC e isolamento multi-tenant
    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)

        # Identifica a loja efetiva da operação com base na instância ou no perfil do usuário logado
        if self.instance.pk:
            loja_efetiva = self.instance.loja
        elif usuario_is_dev(self.autor):
            loja_efetiva = None
        else:
            loja_efetiva = getattr(self.autor.perfil, 'loja', None) if self.autor else None

        # Tratamento do campo loja para usuário DEV (acesso global com seleção)
        if usuario_is_dev(self.autor):
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].required = True
            if self.instance.pk:
                self.fields['loja'].initial = self.instance.loja
        # Tratamento do campo loja para operadores regulares (bloqueado na própria loja)
        else:
            self.fields['loja'].queryset = Loja.objects.filter(id=loja_efetiva.id) if loja_efetiva else Loja.objects.none()
            self.fields['loja'].initial = loja_efetiva
            self.fields['loja'].disabled = True

        # Filtra o dropdown de categorias ativas vinculadas estritamente à loja em operação
        if loja_efetiva:
            self.fields['categoria'].queryset = Categoria.objects.filter(loja=loja_efetiva, ativo=True).order_by('nome')
        elif usuario_is_dev(self.autor) and not self.instance.pk:
            self.fields['categoria'].queryset = Categoria.objects.filter(ativo=True).order_by('loja__nome', 'nome')
        else:
            self.fields['categoria'].queryset = Categoria.objects.none()

        # RN-09: Restrições de USUARIO
        # Se o perfil não tiver permissão para alterar preço, desativa o campo na interface
        if not pode_alterar_preco(self.autor):
            self.fields['preco'].disabled = True
            self.fields['preco'].help_text = "Seu perfil possui permissão de leitura sobre preços de venda (RN-09)."

        # Se o perfil não puder realizar ajuste geral de estoque, desativa o campo
        if not pode_ajustar_estoque_geral(self.autor):
            self.fields['estoque'].disabled = True
            self.fields['estoque'].help_text = "Ajuste geral restrito a gestores. Para avarias/perdas, utilize 'Baixa por Avaria' (RN-09)."

        # Flexibiliza a obrigatoriedade de campos de custo e frete na interface
        self.fields['custo_aquisicao'].required = False
        self.fields['custo_embalagem'].required = False
        self.fields['modalidade_full'].required = False

    # Limpeza e sanitização obrigatória do código SKU
    def clean_sku(self):
        sku = self.cleaned_data.get('sku', '').strip().upper()
        if not sku:
            raise ValidationError("O código SKU é obrigatório.")
        return sku

    # Validação do campo estoque impedindo valores negativos
    def clean_estoque(self):
        estoque = self.cleaned_data.get('estoque')
        if estoque is not None and estoque < 0:
            raise ValidationError("O saldo de estoque não pode ser negativo no cadastro manual (RN-06).")
        return estoque

    # Validação cruzada do produto (loja, unicidade de SKU, integridade de valores e categorias)
    def clean(self):
        cleaned_data = super().clean()

        # Força a associação de loja para não-DEV
        if not usuario_is_dev(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja
        else:
            loja = cleaned_data.get('loja')

        if not loja:
            self.add_error('loja', "A vinculação a uma Loja é obrigatória.")

        sku = cleaned_data.get('sku')
        # Validação RN-02: Unicidade do código SKU dentro da mesma loja
        if loja and sku:
            qs = Produto.objects.filter(loja=loja, sku=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('sku', f"Já existe um produto com o SKU '{sku}' cadastrado nesta loja (RN-02).")

        preco = cleaned_data.get('preco')
        estoque = cleaned_data.get('estoque')

        # Se campos estiverem desabilitados para USUARIO, preserva valores da instância
        # Preserva os valores originais persistidos caso o usuário comum tenha submetido o formulário com campos travados
        if not pode_alterar_preco(self.autor):
            preco = self.instance.preco if self.instance.pk else Decimal('0.00')
            cleaned_data['preco'] = preco

        if not pode_ajustar_estoque_geral(self.autor):
            estoque = self.instance.estoque if self.instance.pk else 0
            cleaned_data['estoque'] = estoque

        # Validação RN-06: Impede valores negativos para preço de venda e estoque
        if preco is not None and preco < Decimal('0.00'):
            self.add_error('preco', "O preço de venda não pode ser negativo (RN-06).")
        if estoque is not None and estoque < 0:
            self.add_error('estoque', "O saldo de estoque não pode ser negativo (RN-06).")

        # Garante que a categoria selecionada pertença estritamente à mesma loja do produto
        categoria = cleaned_data.get('categoria')
        if categoria and loja and categoria.loja_id != loja.id:
            self.add_error('categoria', "A categoria selecionada não pertence à loja deste produto.")

        return cleaned_data


# Formulário para vincular uma publicação externa (anúncio de marketplace) a um produto local
class AnuncioMarketplaceForm(forms.ModelForm):
    # Docstring documentando a associação externa de marketplace ao catálogo físico
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

    # Construtor que restringe o select de contas à loja dona do produto informado
    def __init__(self, *args, produto: Produto = None, **kwargs):
        self.produto = produto
        super().__init__(*args, **kwargs)
        if self.produto:
            self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                loja=self.produto.loja, ativo=True
            )

    # Valida que o identificador de anúncio externo não esteja duplicado para a mesma conta
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


# Formulário para registro de baixas pontuais motivadas por quebras, avarias ou perdas físicas
class ProdutoBaixaAvariaForm(forms.Form):
    # Docstring detalhando o registro de perdas operacionais autorizado para todos os perfis (RN-09)
    """
    O QUE FAZ: Formulário de baixa pontual de estoque por motivo de avaria ou perda física (RN-09).
    POR QUE FAZ: Permite que todos os usuários autenticados da loja (inclusive USUARIO) registrem perdas operacionais com motivo obrigatório.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR e USUARIO.
    MULTI-TENANCY: Restrito ao produto da loja do usuário.
    """

    # Campo numérico obrigando valor inteiro de no mínimo 1 unidade
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

    # Seleção restrita apenas aos tipos de baixa física de perda ou avaria
    tipo_baixa = forms.ChoiceField(
        label="Motivo da Baixa",
        choices=[
            (TipoAjusteEstoqueEnum.SAIDA_AVARIA, 'Avaria / Defeito no Produto'),
            (TipoAjusteEstoqueEnum.SAIDA_PERDA, 'Perda / Extravio no Estoque'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Justificativa descritiva textual obrigatória para registro de auditoria
    justificativa = forms.CharField(
        label="Justificativa / Descrição do Ocorrido (Obrigatório)",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Produto avariado na embalagem / Caixa danificada'
        })
    )

    # Construtor recebendo o produto alvo
    def __init__(self, *args, produto=None, **kwargs):
        self.produto = produto
        super().__init__(*args, **kwargs)

    # Validação garantindo que a baixa não exceda o saldo físico disponível
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


# Formulário de ajuste geral do saldo de estoque físico por balanço ou inventário
class ProdutoAjusteEstoqueForm(forms.Form):
    # Docstring descrevendo a finalidade de contagem de inventário restrita a gestores
    """
    O QUE FAZ: Formulário para ajuste geral de saldo de estoque por gestores.
    POR QUE FAZ: Balanço físico e entradas de lote por gestores autorizados (DEV, ADMIN, SUPERVISOR).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (USUARIO é bloqueado por RN-09).
    MULTI-TENANCY: Restrito à loja do usuário.
    """

    # Novo saldo total físico absoluto apurado no inventário
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

    # Seleção de qualquer um dos motivos enumerados em TipoAjusteEstoqueEnum
    tipo_ajuste = forms.ChoiceField(
        label="Tipo de Movimentação",
        choices=TipoAjusteEstoqueEnum.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Texto explicativo da contagem ou entrada de lote
    justificativa = forms.CharField(
        label="Justificativa do Ajuste",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Balanço físico mensal / Entrada de estoque'
        })
    )


# Formulário para captura e validação de lotes de produtos selecionados via checkboxes
class ProdutoSincronizacaoLoteForm(forms.Form):
    # Docstring documentando a validação de IDs de produtos para ações em lote
    """
    O QUE FAZ: Validação de IDs de produtos selecionados para sincronização de preço em lote.
    """

    # Campo oculto contendo a lista de IDs separados por vírgula
    produtos_ids = forms.CharField(widget=forms.HiddenInput())

    # Converte e valida a string de IDs em uma lista segura de inteiros
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


# Formulário que viabiliza a publicação direta de uma oferta no canal parceiro (ex: Mercado Livre)
class PublicarAnuncioForm(forms.Form):
    # Docstring explicando a criação de anúncio remoto a partir do catálogo mestre
    """
    O QUE FAZ: Formulário de publicação de anúncio em marketplace para um produto do catálogo (RF-04).
    POR QUE FAZ: Permite ao operador selecionar a conta de destino, tipo de listagem (Clássico/Premium) e preço de envio.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (USUARIO bloqueado).
    MULTI-TENANCY: Filtra apenas contas da loja do produto / usuário (DEV pode ver todas com identificador da loja).
    """

    # Constantes das modalidades de anúncio aceitas na integração externa
    LISTING_TYPES = [
        ('gold_special', 'Clássico (gold_special) — Menor taxa de comissão'),
        ('gold_pro', 'Premium (gold_pro) — Parcelamento sem juros / Maior visibilidade'),
    ]

    # Campo para selecionar a conta de destino onde a oferta será publicada
    conta_marketplace = forms.ModelChoiceField(
        label="Conta de Marketplace de Destino *",
        queryset=ContaMarketplace.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Selecione a conta integrada onde o anúncio será publicado."
    )

    # Campo seletor para o tipo de exposição comercial
    listing_type_id = forms.ChoiceField(
        label="Tipo de Listagem / Exposição",
        choices=LISTING_TYPES,
        initial='gold_special',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Modalidade de anúncio no canal (ex: Clássico ou Premium no Mercado Livre)."
    )

    # Preço de venda configurado para o envio do anúncio
    preco = forms.DecimalField(
        label="Preço de Publicação (R$) *",
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control font-monospace', 'step': '0.01'}),
        help_text="Preço inicial com o qual o anúncio será publicado no marketplace."
    )

    # Identificador da categoria remota de destino com valor padrão configurado
    category_id = forms.CharField(
        label="ID da Categoria Externa (Opcional)",
        required=False,
        initial="MLB3530",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: MLB3530'}),
        help_text="Identificador da folha de categoria no canal de destino (fallback: MLB3530)."
    )

    # Construtor que pré-preenche o preço do produto e isola o menu de contas pela loja do tenant
    def __init__(self, *args, produto=None, autor=None, **kwargs):
        self.produto = produto
        self.autor = autor
        super().__init__(*args, **kwargs)

        # Se o produto foi fornecido, define seu preço físico como valor inicial sugerido
        if produto:
            self.fields['preco'].initial = produto.preco

        # Se o autor for desenvolvedor global (DEV)
        if usuario_is_dev(autor):
            # Se o produto já possui loja definida, lista as contas vinculadas a essa loja
            if produto and produto.loja:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                    loja=produto.loja, ativo=True
                ).order_by('canal', 'apelido_conta')
            # Caso contrário, permite selecionar entre todas as contas ativas
            else:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                    ativo=True
                ).select_related('loja').order_by('loja__nome', 'canal')
        # Para operadores regulares, restringe as opções estritamente às contas da própria loja
        else:
            perfil = getattr(autor, 'perfil', None)
            if perfil and perfil.loja:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.filter(
                    loja=perfil.loja, ativo=True
                ).order_by('canal', 'apelido_conta')
            else:
                self.fields['conta_marketplace'].queryset = ContaMarketplace.objects.none()
