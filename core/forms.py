from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from .models import Loja, PerfilUsuario
from .enums import PapelUsuarioEnum
from .permissions import (
    usuario_is_dev, usuario_is_admin, pode_criar_usuario, pode_alterar_papel
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
            # DEV pode criar qualquer papel
            self.fields['papel'].choices = PapelUsuarioEnum.choices
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].help_text = "Obrigatório para papéis não-DEV. Deixe vazio para escopo global DEV."
        elif usuario_is_admin(self.autor):
            # ADMIN pode criar apenas SUPERVISOR e USUARIO na sua própria loja
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

        # Se o campo loja estiver desabilitado (ADMIN), recuperar a loja do perfil do autor
        if usuario_is_admin(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja

        # Validação de escopo e permissão de criação
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

        # Impede que o usuário desative a própria conta ou altere o próprio papel
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

