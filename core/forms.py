# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from .models import Loja, PerfilUsuario, Categoria, Produto, HistoricoPreco
from .enums import (
    PapelUsuarioEnum, StatusProdutoEnum, StatusSincronizacaoEnum, TipoAjusteEstoqueEnum
)
from .permissions import (
    usuario_is_dev, usuario_is_admin, pode_criar_usuario, pode_alterar_papel,
    pode_alterar_preco, pode_ajustar_estoque_geral
)


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
        self.fields['slug'].required = False
        self.fields['pais'].initial = 'Brasil'

    def clean_cnpj(self):
        return self.cleaned_data.get('cnpj', '').strip()

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        nome = self.cleaned_data.get('nome', '').strip()
        if not slug and nome:
            slug = slugify(nome)
        return slug


class UsuarioCreateForm(forms.Form):
    """
    Formulário unificado para criação de Usuário e PerfilUsuario com controle RBAC dinâmico.
    Adapta as opções de Loja e Papel com base no perfil do autor da ação.
    """
    username = forms.CharField(
        label="Nome de Usuário (Login)",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ex: joao.silva',
            'autofocus': 'autofocus'
        })
    )
    first_name = forms.CharField(
        label="Primeiro Nome",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'João'})
    )
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Silva'})
    )
    email = forms.EmailField(
        label="E-mail",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'joao@empresa.com.br'})
    )
    password1 = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo de 8 caracteres'})
    )
    password2 = forms.CharField(
        label="Confirmação de Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite a senha novamente'})
    )
    papel = forms.ChoiceField(
        label="Papel de Acesso (RBAC)",
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        empty_label="— Selecione uma Loja —",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_active = forms.BooleanField(
        label="Conta Ativa",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)

        if usuario_is_dev(self.autor):
            self.fields['papel'].choices = PapelUsuarioEnum.choices
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].help_text = "Obrigatório para papéis não-DEV. Deixe vazio para escopo global DEV."
        elif usuario_is_admin(self.autor):
            self.fields['papel'].choices = [
                (PapelUsuarioEnum.SUPERVISOR, 'Supervisor da Loja (SUPERVISOR)'),
                (PapelUsuarioEnum.USUARIO, 'Usuário Padrão da Loja (USUÁRIO)'),
            ]
            loja_admin = getattr(self.autor.perfil, 'loja', None)
            if loja_admin:
                self.fields['loja'].queryset = Loja.objects.filter(id=loja_admin.id)
                self.fields['loja'].initial = loja_admin
                self.fields['loja'].disabled = True
                self.fields['loja'].help_text = f"Vinculado compulsoriamente à sua loja: {loja_admin.nome}"
        else:
            self.fields['papel'].choices = []
            self.fields['loja'].queryset = Loja.objects.none()

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        papel = cleaned_data.get('papel')
        loja = cleaned_data.get('loja')

        if p1 and p2 and p1 != p2:
            self.add_error('password2', "As senhas digitadas não conferem.")
        if p1 and len(p1) < 8:
            self.add_error('password1', "A senha deve conter no mínimo 8 caracteres.")

        if usuario_is_admin(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja

        if not pode_criar_usuario(self.autor, papel, loja):
            raise ValidationError(
                "Você não possui permissão para cadastrar este papel de usuário para a loja informada."
            )

        if papel != PapelUsuarioEnum.DEV and not loja:
            self.add_error('loja', "A seleção de uma Loja é obrigatória para este papel.")

        return cleaned_data

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            email=data.get('email', ''),
            password=data['password1'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            is_active=data.get('is_active', True)
        )
        PerfilUsuario.objects.create(
            usuario=user,
            papel=data['papel'],
            loja=data['loja'] if data['papel'] != PapelUsuarioEnum.DEV else None
        )
        return user


class UsuarioUpdateForm(forms.ModelForm):
    """
    Formulário para edição cadastral e alteração de papel de um usuário existente.
    """
    papel = forms.ChoiceField(
        label="Papel de Acesso (RBAC)",
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Primeiro Nome'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sobrenome'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@empresa.com.br'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)
        user_alvo = self.instance
        perfil_alvo = getattr(user_alvo, 'perfil', None)

        if usuario_is_dev(self.autor):
            self.fields['papel'].choices = PapelUsuarioEnum.choices
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
        elif usuario_is_admin(self.autor):
            self.fields['papel'].choices = [
                (PapelUsuarioEnum.SUPERVISOR, 'Supervisor da Loja (SUPERVISOR)'),
                (PapelUsuarioEnum.USUARIO, 'Usuário Padrão da Loja (USUÁRIO)'),
            ]
            self.fields['loja'].queryset = Loja.objects.filter(id=self.autor.perfil.loja_id)
            self.fields['loja'].disabled = True

        if perfil_alvo:
            self.fields['papel'].initial = perfil_alvo.papel
            self.fields['loja'].initial = perfil_alvo.loja

        if self.autor == user_alvo:
            self.fields['is_active'].disabled = True
            self.fields['papel'].disabled = True
            self.fields['loja'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        novo_papel = cleaned_data.get('papel')
        user_alvo = self.instance
        perfil_alvo = getattr(user_alvo, 'perfil', None)

        if perfil_alvo and novo_papel != perfil_alvo.papel:
            if not pode_alterar_papel(self.autor, user_alvo, novo_papel):
                raise ValidationError("Você não possui permissão para alterar o papel deste usuário.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and hasattr(user, 'perfil'):
            perfil = user.perfil
            novo_papel = self.cleaned_data.get('papel')
            nova_loja = self.cleaned_data.get('loja')
            
            if novo_papel and not self.fields['papel'].disabled:
                perfil.papel = novo_papel
                if novo_papel == PapelUsuarioEnum.DEV:
                    perfil.loja = None
                elif nova_loja and not self.fields['loja'].disabled:
                    perfil.loja = nova_loja
                perfil.save()
        return user


class UsuarioPasswordResetAdminForm(forms.Form):
    """
    Formulário para redefinição de senha de usuário subordinado por DEV ou ADMIN.
    """
    nova_senha1 = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo de 8 caracteres'})
    )
    nova_senha2 = forms.CharField(
        label="Confirmação da Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite a senha novamente'})
    )

    def clean(self):
        cleaned_data = super().clean()
        s1 = cleaned_data.get('nova_senha1')
        s2 = cleaned_data.get('nova_senha2')

        if s1 and s2 and s1 != s2:
            self.add_error('nova_senha2', "As senhas digitadas não conferem.")
        if s1 and len(s1) < 8:
            self.add_error('nova_senha1', "A nova senha deve conter no mínimo 8 caracteres.")
        return cleaned_data

    def save(self, user):
        user.set_password(self.cleaned_data['nova_senha1'])
        user.save()
        return user


# ==============================================================================
# FORMULÁRIOS DE CATEGORIAS E PRODUTOS (RF-03 / RN-01 / RN-02 / RN-06 / RN-09)
# ==============================================================================

class CategoriaForm(forms.ModelForm):
    """
    Formulário para cadastro e edição de Categoria de Produtos com isolamento multi-tenant.
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
                'placeholder': 'Ex: Calçados Masculinos, Eletrônicos...',
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
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
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
    Formulário unificado de Produto com controle de permissões por perfil (RN-09):
    - DEV/ADMIN/SUPERVISOR: Acesso total a descritivo, preço e estoque.
    - USUARIO: Acesso permitido apenas a dados descritivos (Preço e Estoque ficam somente leitura).
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
            'preco', 'estoque', 'status', 'meli_item_id'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={
                'class': 'form-control font-monospace text-uppercase',
                'placeholder': 'Ex: CAM-POLO-AZ-G',
                'autofocus': 'autofocus'
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Camisa Polo Masculina Azul Tamanho G'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-select'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descrição completa e especificações do produto...'
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
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'meli_item_id': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Ex: MLB123456789 (Opcional)'
            }),
        }

    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)

        # Determina a loja efetiva deste formulário
        if self.instance.pk:
            loja_efetiva = self.instance.loja
        elif usuario_is_dev(self.autor):
            loja_efetiva = None
        else:
            loja_efetiva = getattr(self.autor.perfil, 'loja', None) if self.autor else None

        # Configuração do campo Loja
        if usuario_is_dev(self.autor):
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].required = True
            if self.instance.pk:
                self.fields['loja'].initial = self.instance.loja
        else:
            self.fields['loja'].queryset = Loja.objects.filter(id=loja_efetiva.id) if loja_efetiva else Loja.objects.none()
            self.fields['loja'].initial = loja_efetiva
            self.fields['loja'].disabled = True

        # Filtra Categorias pela loja efetiva
        if loja_efetiva:
            self.fields['categoria'].queryset = Categoria.objects.filter(loja=loja_efetiva, ativo=True).order_by('nome')
        elif usuario_is_dev(self.autor) and not self.instance.pk:
            self.fields['categoria'].queryset = Categoria.objects.filter(ativo=True).order_by('loja__nome', 'nome')
        else:
            self.fields['categoria'].queryset = Categoria.objects.none()

        # RN-09: Restrições do perfil USUARIO sobre Preço e Estoque
        if not pode_alterar_preco(self.autor):
            self.fields['preco'].disabled = True
            self.fields['preco'].help_text = "Seu perfil não possui permissão para alterar o preço de venda (RN-09)."

        if not pode_ajustar_estoque_geral(self.autor):
            self.fields['estoque'].disabled = True
            self.fields['estoque'].help_text = "Ajuste geral bloqueado para o seu perfil. Para perdas/avarias, utilize o fluxo 'Baixa por Avaria' (RN-09)."

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
        
        # Garante a loja correta
        if not usuario_is_dev(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja
        else:
            loja = cleaned_data.get('loja')

        if not loja:
            self.add_error('loja', "A vinculação a uma Loja é obrigatória.")

        # RN-02: Valida unicidade de SKU por loja
        sku = cleaned_data.get('sku')
        if loja and sku:
            qs = Produto.objects.filter(loja=loja, sku=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('sku', f"Já existe um produto com o SKU '{sku}' cadastrado nesta loja (RN-02).")

        # RN-06: Validação de preços e estoques não negativos
        preco = cleaned_data.get('preco')
        estoque = cleaned_data.get('estoque')

        # Se campos estiverem desabilitados (USUARIO), restaura os valores originais da instância
        if not pode_alterar_preco(self.autor):
            if self.instance.pk:
                preco = self.instance.preco
                cleaned_data['preco'] = preco
            else:
                preco = Decimal('0.00')
                cleaned_data['preco'] = preco

        if not pode_ajustar_estoque_geral(self.autor):
            if self.instance.pk:
                estoque = self.instance.estoque
                cleaned_data['estoque'] = estoque
            else:
                estoque = 0
                cleaned_data['estoque'] = estoque

        if preco is not None and preco < Decimal('0.00'):
            self.add_error('preco', "O preço de venda não pode ser negativo (RN-06).")
        if estoque is not None and estoque < 0:
            self.add_error('estoque', "O saldo de estoque não pode ser negativo (RN-06).")

        # Validação de compatibilidade da Categoria com a Loja
        categoria = cleaned_data.get('categoria')
        if categoria and loja and categoria.loja_id != loja.id:
            self.add_error('categoria', "A categoria selecionada não pertence à loja deste produto.")

        return cleaned_data


class ProdutoBaixaAvariaForm(forms.Form):
    """
    Formulário para baixa pontual de estoque por motivo de avaria ou perda (RN-09).
    Permitido para todos os usuários autenticados da loja (inclusive USUARIO).
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
            'placeholder': 'Ex: Produto avariado no transporte interno / Caixa molhada'
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
    Formulário para ajuste geral de saldo de estoque por gestores (DEV, ADMIN, SUPERVISOR).
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
            'placeholder': 'Ex: Balanço físico mensal / Entrada de lote adicional'
        })
    )


class LojaIntegracaoMeliForm(forms.ModelForm):
    """
    Formulário para configuração das credenciais de integração com a API do Mercado Livre (RF-05)
    e políticas de Broadcast Multi-Canal (RF-08).
    Acessível por DEV (qualquer loja) e ADMIN (sua própria loja).
    """
    class Meta:
        model = Loja
        fields = [
            'meli_client_id', 'meli_client_secret', 'meli_access_token', 'meli_refresh_token',
            'sincronizar_canal_origem_venda', 'shopee_ativo', 'magalu_ativo'
        ]
        widgets = {
            'meli_client_id': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Ex: 1234567890123456',
                'autocomplete': 'off',
            }),
            'meli_client_secret': forms.PasswordInput(render_value=True, attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Secret da aplicação no Mercado Livre Developers',
                'autocomplete': 'new-password',
            }),
            'meli_access_token': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'APP_USR-...',
                'autocomplete': 'off',
            }),
            'meli_refresh_token': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'TG-...',
                'autocomplete': 'off',
            }),
            'sincronizar_canal_origem_venda': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'shopee_ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'magalu_ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        help_texts = {
            'meli_client_id': 'App ID gerado no portal de desenvolvedores do Mercado Livre.',
            'meli_client_secret': 'Chave secreta correspondente ao seu App ID.',
            'meli_access_token': 'Token de acesso OAuth 2.0 ativo.',
            'meli_refresh_token': 'Token utilizado para renovação automática do Access Token quando expirado.',
            'sincronizar_canal_origem_venda': 'Por padrão (desmarcado), assume-se que o canal onde a venda ocorreu já abateu o estoque internamente. Marque caso o marketplace espere atualização explícita.',
            'shopee_ativo': 'Habilita o broadcast automático de estoque para o canal Shopee.',
            'magalu_ativo': 'Habilita o broadcast automático de estoque para o canal Magazine Luiza.',
        }


class ProdutoSincronizacaoLoteForm(forms.Form):
    """
    Formulário para validação de IDs de produtos selecionados para sincronização em lote.
    """
    produtos_ids = forms.CharField(widget=forms.HiddenInput())

    def clean_produtos_ids(self):
        raw_ids = self.cleaned_data.get('produtos_ids', '').strip()
        if not raw_ids:
            raise ValidationError("Nenhum produto foi selecionado para sincronização.")
        try:
            ids = [int(x.strip()) for x in raw_ids.split(',') if x.strip()]
        except ValueError:
            raise ValidationError("Lista de identificadores de produtos inválida.")
        if not ids:
            raise ValidationError("Nenhum produto válido selecionado.")
        return ids


class ProdutoBroadcastLoteForm(forms.Form):
    """
    Formulário para validação de IDs de produtos selecionados para broadcast multi-canal em lote (RF-08).
    """
    produtos_ids = forms.CharField(widget=forms.HiddenInput())

    def clean_produtos_ids(self):
        raw_ids = self.cleaned_data.get('produtos_ids', '').strip()
        if not raw_ids:
            raise ValidationError("Nenhum produto foi selecionado para broadcast.")
        try:
            ids = [int(x.strip()) for x in raw_ids.split(',') if x.strip()]
        except ValueError:
            raise ValidationError("Lista de identificadores de produtos inválida.")
        if not ids:
            raise ValidationError("Nenhum produto válido selecionado.")
        return ids




