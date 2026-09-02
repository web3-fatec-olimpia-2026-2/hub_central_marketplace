# Os códigos foram gerados com auxilio de I.A.
from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from .models import Loja, PerfilUsuario, ModuloLoja
from .enums import PapelUsuarioEnum, ModuloSistemaEnum
from .permissions import usuario_is_dev, usuario_is_admin, pode_criar_usuario, pode_alterar_papel


class LojaForm(forms.ModelForm):
    """
    O QUE FAZ: Formulário de cadastro, provisionamento e edição de Lojas (Tenants).
    POR QUE FAZ: Valida dados cadastrais, formatação de CNPJ e geração de identificador slug único.
    PERMISSÕES RBAC: Restrito ao perfil DEV (RF-01 / RN-07).
    MULTI-TENANCY: Criação e manutenção da raiz dos tenants.
    """
    class Meta:
        model = Loja
        fields = [
            'nome', 'slug', 'cnpj', 'inscricao_estadual',
            'telefone', 'email',
            'cep', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'pais',
            'ativo',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Loja Matriz E-commerce',
                'autofocus': 'autofocus'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gerado automaticamente a partir do nome'
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['pais'].required = False
        self.fields['pais'].initial = 'Brasil'

    def clean_cnpj(self):
        return self.cleaned_data.get('cnpj', '').strip()

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        nome = self.cleaned_data.get('nome', '').strip()
        if not slug and nome:
            slug = slugify(nome)
        return slug


class LojaModulosForm(forms.Form):
    """
    O QUE FAZ: Formulário para o usuário DEV ativar ou desativar os módulos do sistema para uma Loja.
    POR QUE FAZ: Implementa interface amigável para alternância de Feature Flags por tenant.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Modifica as flags de uma loja específica.
    """
    def __init__(self, *args, loja: Loja = None, **kwargs):
        self.loja = loja
        super().__init__(*args, **kwargs)

        # Garante que todos os módulos padrão existam no banco
        if self.loja:
            self.loja.garantir_modulos_padrao()
            modulos_existentes = {m.modulo: m.ativo for m in self.loja.modulos.all()}

            for choice_val, choice_label in ModuloSistemaEnum.choices:
                self.fields[f"modulo_{choice_val}"] = forms.BooleanField(
                    label=choice_label,
                    required=False,
                    initial=modulos_existentes.get(choice_val, True),
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )

    def save(self):
        if not self.loja:
            return
        for choice_val, _ in ModuloSistemaEnum.choices:
            campo_nome = f"modulo_{choice_val}"
            if campo_nome in self.cleaned_data:
                ativo = self.cleaned_data[campo_nome]
                ModuloLoja.objects.update_or_create(
                    loja=self.loja,
                    modulo=choice_val,
                    defaults={'ativo': ativo}
                )


class UsuarioCreateForm(forms.Form):
    """
    O QUE FAZ: Formulário unificado para criação de Usuário e PerfilUsuario com controle dinâmico RBAC.
    POR QUE FAZ: Valida permissões hierárquicas (DEV cria qualquer usuário; ADMIN cria SUPERVISOR/USUARIO em sua loja).
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Vínculo automático ou restrito à loja do autor.
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
    O QUE FAZ: Formulário de edição de dados cadastrais e papel de um usuário existente.
    POR QUE FAZ: Impede alterações indevidas de papel ou loja por usuários sem privilégios.
    PERMISSÕES RBAC: DEV e ADMIN (apenas subordinados).
    MULTI-TENANCY: Isolado por loja.
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
    O QUE FAZ: Formulário de redefinição de senha administrativa por gestores.
    POR QUE FAZ: Permite que administradores definam novas credenciais para subordinados.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Restrito à própria loja para ADMIN.
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
