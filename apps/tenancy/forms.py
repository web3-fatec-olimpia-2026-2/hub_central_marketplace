# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo forms do framework Django para criação e validação de formulários HTML
from django import forms

# Importa o modelo User nativo do Django para autenticação e gestão cadastral de contas
from django.contrib.auth.models import User

# Importa o utilitário slugify para converter nomes em identificadores amigáveis de URL (slugs)
from django.utils.text import slugify

# Importa ValidationError para emissão de mensagens de validação e bloqueios de formulários
from django.core.exceptions import ValidationError

# Importa os modelos de domínio de governança: Loja (tenant), PerfilUsuario (vínculo RBAC) e ModuloLoja (feature flags)
from .models import Loja, PerfilUsuario, ModuloLoja

# Importa as enumerações de papéis de usuários (RBAC) e módulos contratáveis do sistema
from .enums import PapelUsuarioEnum, ModuloSistemaEnum

# Importa funções especialistas de validação hierárquica e permissões granulares de acesso
from .permissions import usuario_is_dev, usuario_is_admin, pode_criar_usuario, pode_alterar_papel


# Declaração do ModelForm para cadastro, provisionamento e edição cadastral de tenants (Lojas)
class LojaForm(forms.ModelForm):
    # Início do bloco de docstring que documenta a finalidade, requisitos RF-01/RN-07, permissões e papel no multi-tenancy
    """
    O QUE FAZ: Formulário de cadastro, provisionamento e edição de Lojas (Tenants).
    POR QUE FAZ: Valida dados cadastrais, formatação de CNPJ e geração de identificador slug único.
    PERMISSÕES RBAC: Restrito ao perfil DEV (RF-01 / RN-07).
    MULTI-TENANCY: Criação e manutenção da raiz dos tenants.
    """
    # Fim da docstring explicativa

    # Metaclasse com configurações de vinculação ao modelo Loja
    class Meta:
        # Define o modelo gerenciado
        model = Loja

        # Lista de campos persistíveis expostos no formulário
        fields = [
            'nome', 'slug', 'cnpj', 'inscricao_estadual',
            'telefone', 'email',
            'cep', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'pais',
            'ativo',
        ]

        # Mapeamento de widgets para injeção de classes CSS (Bootstrap), placeholders e comportamentos HTML5
        widgets = {
            # Campo de nome com foco automático ao carregar a página
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Loja Matriz E-commerce',
                'autofocus': 'autofocus'
            }),
            # Campo slug para rota amigável
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gerado automaticamente a partir do nome'
            }),
            # Campo de CNPJ com limitação de tamanho e máscara visual sugerida
            'cnpj': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00.000.000/0000-00',
                'maxlength': '20'
            }),
            # Campo para inscrição estadual
            'inscricao_estadual': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 123.456.789.000 ou Isento'
            }),
            # Campo para contato telefônico
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(00) 00000-0000'
            }),
            # Campo de e-mail institucional
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contato@loja.com.br'
            }),
            # Campo de CEP
            'cep': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00000-000',
                'maxlength': '10'
            }),
            # Campo de logradouro
            'endereco': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Rua, Avenida, Alameda...'
            }),
            # Campo de número predial
            'numero': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123'
            }),
            # Campo de complemento
            'complemento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Sala 101, Galpão B...'
            }),
            # Campo de bairro
            'bairro': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Centro, Distrito Industrial...'
            }),
            # Campo de município
            'cidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'São Paulo'
            }),
            # Dropdown de seleção de Unidade Federativa
            'estado': forms.Select(attrs={
                'class': 'form-select'
            }),
            # Campo de país com valor padrão
            'pais': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brasil'
            }),
            # Checkbox de ativação operacional do tenant
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    # Construtor do formulário que ajusta obrigatoriedades e valores iniciais
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Permite submissão sem slug manual para que seja preenchido no clean_slug
        self.fields['slug'].required = False
        # Torna o país opcional e preenche 'Brasil' como padrão
        self.fields['pais'].required = False
        self.fields['pais'].initial = 'Brasil'

    # Método de limpeza e sanitização do CNPJ removendo espaços em branco acidentais
    def clean_cnpj(self):
        return self.cleaned_data.get('cnpj', '').strip()

    # Método de limpeza que gera o slug automaticamente caso o operador o deixe em branco
    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        nome = self.cleaned_data.get('nome', '').strip()
        # Se não digitado, gera o slug a partir da conversão kebab-case do nome da loja
        if not slug and nome:
            slug = slugify(nome)
        return slug


# Declaração do formulário para alternância direta de feature flags de módulos de uma Loja
class LojaModulosForm(forms.Form):
    # Início do bloco de docstring estrutural
    """
    O QUE FAZ: Formulário para o usuário DEV ativar ou desativar os módulos do sistema para uma Loja.
    POR QUE FAZ: Implementa interface amigável para alternância de Feature Flags por tenant.
    PERMISSÕES RBAC: Exclusivo para perfil DEV.
    MULTI-TENANCY: Modifica as flags de uma loja específica.
    """
    # Fim da docstring explicativa

    # Construtor dinâmico que recebe a instância da loja e cria os campos booleanos em tempo de execução
    def __init__(self, *args, loja: Loja = None, **kwargs):
        self.loja = loja
        super().__init__(*args, **kwargs)

        # Garante que todos os módulos padrão existam no banco
        # Provisiona registros padrão na tabela associativa caso a loja seja recém-criada
        if self.loja:
            self.loja.garantir_modulos_padrao()
            # Mapeia o status corrente de cada módulo da loja em um dicionário
            modulos_existentes = {m.modulo: m.ativo for m in self.loja.modulos.all()}

            # Cria dinamicamente um campo Checkbox para cada opção do enum ModuloSistemaEnum
            for choice_val, choice_label in ModuloSistemaEnum.choices:
                self.fields[f"modulo_{choice_val}"] = forms.BooleanField(
                    label=choice_label,
                    required=False,
                    initial=modulos_existentes.get(choice_val, True),
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )

    # Método que persiste as alterações das feature flags no banco de dados
    def save(self):
        # Aborta se nenhuma loja estiver vinculada ao formulário
        if not self.loja:
            return
        # Itera pelas opções conhecidas de módulos do sistema
        for choice_val, _ in ModuloSistemaEnum.choices:
            campo_nome = f"modulo_{choice_val}"
            # Se o campo submetido constar nos dados limpos, executa atualização idempotente
            if campo_nome in self.cleaned_data:
                ativo = self.cleaned_data[campo_nome]
                ModuloLoja.objects.update_or_create(
                    loja=self.loja,
                    modulo=choice_val,
                    defaults={'ativo': ativo}
                )


# Declaração do formulário unificado de criação de novos usuários e vínculos RBAC
class UsuarioCreateForm(forms.Form):
    # Início do bloco de docstring documentando as regras hierárquicas RBAC e tenant
    """
    O QUE FAZ: Formulário unificado para criação de Usuário e PerfilUsuario com controle dinâmico RBAC.
    POR QUE FAZ: Valida permissões hierárquicas (DEV cria qualquer usuário; ADMIN cria SUPERVISOR/USUARIO em sua loja).
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Vínculo automático ou restrito à loja do autor.
    """
    # Fim da docstring explicativa

    # Campo de username para login
    username = forms.CharField(
        label="Nome de Usuário (Login)",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ex: joao.silva',
            'autofocus': 'autofocus'
        })
    )
    # Campo opcional para primeiro nome
    first_name = forms.CharField(
        label="Primeiro Nome",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'João'})
    )
    # Campo opcional para sobrenome
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Silva'})
    )
    # Campo opcional de e-mail com validação de formato
    email = forms.EmailField(
        label="E-mail",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'joao@empresa.com.br'})
    )
    # Campo para definição da senha inicial com widget de proteção de caracteres
    password1 = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo de 8 caracteres'})
    )
    # Campo para confirmação da senha digitada
    password2 = forms.CharField(
        label="Confirmação de Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite a senha novamente'})
    )
    # Dropdown para escolha do papel hierárquico (populado dinamicamente no __init__)
    papel = forms.ChoiceField(
        label="Papel de Acesso (RBAC)",
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Campo de seleção da loja tenant associada (populado dinamicamente no __init__)
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        empty_label="— Selecione uma Loja —",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Flag booleana indicando se a conta já nasce ativa para login
    is_active = forms.BooleanField(
        label="Conta Ativa",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Construtor que customiza as escolhas de papéis e lojas de acordo com a hierarquia do autor autenticado
    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)

        # Regra para usuário com perfil DEV: acesso total e irrestrito
        if usuario_is_dev(self.autor):
            self.fields['papel'].choices = PapelUsuarioEnum.choices
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].help_text = "Obrigatório para papéis não-DEV. Deixe vazio para escopo global DEV."
        # Regra para usuário com perfil ADMIN: pode criar apenas subordinados na sua própria loja
        elif usuario_is_admin(self.autor):
            # Restringe papéis elegíveis a Supervisor e Usuário Comum
            self.fields['papel'].choices = [
                (PapelUsuarioEnum.SUPERVISOR, 'Supervisor da Loja (SUPERVISOR)'),
                (PapelUsuarioEnum.USUARIO, 'Usuário Padrão da Loja (USUÁRIO)'),
            ]
            loja_admin = getattr(self.autor.perfil, 'loja', None)
            # Trava a loja compulsoriamente na mesma loja do administrador
            if loja_admin:
                self.fields['loja'].queryset = Loja.objects.filter(id=loja_admin.id)
                self.fields['loja'].initial = loja_admin
                self.fields['loja'].disabled = True
                self.fields['loja'].help_text = f"Vinculado compulsoriamente à sua loja: {loja_admin.nome}"
        # Para outros papéis sem privilégios de gestão de usuários, neutraliza os campos
        else:
            self.fields['papel'].choices = []
            self.fields['loja'].queryset = Loja.objects.none()

    # Validação unívoca de username garantindo que não colida com contas existentes
    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("Este nome de usuário já está em uso.")
        return username

    # Validação cruzada (cross-field) de senhas, permissões RBAC e regras de obrigatoriedade de tenant
    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        papel = cleaned_data.get('papel')
        loja = cleaned_data.get('loja')

        # Valida coincidência das senhas digitadas
        if p1 and p2 and p1 != p2:
            self.add_error('password2', "As senhas digitadas não conferem.")
        # Valida comprimento mínimo de 8 caracteres
        if p1 and len(p1) < 8:
            self.add_error('password1', "A senha deve conter no mínimo 8 caracteres.")

        # Se o autor for ADMIN, força a vinculação à sua loja para evitar manipulação de payloads
        if usuario_is_admin(self.autor):
            loja = getattr(self.autor.perfil, 'loja', None)
            cleaned_data['loja'] = loja

        # Checagem centralizada na matriz de permissões RBAC
        if not pode_criar_usuario(self.autor, papel, loja):
            raise ValidationError(
                "Você não possui permissão para cadastrar este papel de usuário para a loja informada."
            )

        # Exige que qualquer papel que não seja DEV tenha obrigatoriamente uma loja selecionada
        if papel != PapelUsuarioEnum.DEV and not loja:
            self.add_error('loja', "A seleção de uma Loja é obrigatória para este papel.")

        return cleaned_data

    # Método que persiste tanto o modelo User quanto a extensão PerfilUsuario
    def save(self):
        data = self.cleaned_data
        # Cria a conta de autenticação nativa do Django
        user = User.objects.create_user(
            username=data['username'],
            email=data.get('email', ''),
            password=data['password1'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            is_active=data.get('is_active', True)
        )
        # Cria o PerfilUsuario correspondente vinculando papel e isolamento de loja (None para DEV)
        PerfilUsuario.objects.create(
            usuario=user,
            papel=data['papel'],
            loja=data['loja'] if data['papel'] != PapelUsuarioEnum.DEV else None
        )
        return user


# Declaração do ModelForm para edição cadastral e atualização de papéis de usuários existentes
class UsuarioUpdateForm(forms.ModelForm):
    # Início do bloco de docstring
    """
    O QUE FAZ: Formulário de edição de dados cadastrais e papel de um usuário existente.
    POR QUE FAZ: Impede alterações indevidas de papel ou loja por usuários sem privilégios.
    PERMISSÕES RBAC: DEV e ADMIN (apenas subordinados).
    MULTI-TENANCY: Isolado por loja.
    """
    # Fim da docstring explicativa

    # Campo de escolha de papel RBAC
    papel = forms.ChoiceField(
        label="Papel de Acesso (RBAC)",
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Campo de seleção da loja tenant
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Metaclasse vinculada ao modelo nativo User
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            # Username em modo somente leitura para impedir mutação de login cadastrado
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Primeiro Nome'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sobrenome'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@empresa.com.br'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # Construtor que carrega dados do perfil e configura restrições baseadas no autor da edição
    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)
        user_alvo = self.instance
        perfil_alvo = getattr(user_alvo, 'perfil', None)

        # Configura opções para desenvolvedores (gestão global)
        if usuario_is_dev(self.autor):
            self.fields['papel'].choices = PapelUsuarioEnum.choices
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
        # Configura opções para administradores de loja (apenas subordinados na sua própria loja)
        elif usuario_is_admin(self.autor):
            self.fields['papel'].choices = [
                (PapelUsuarioEnum.SUPERVISOR, 'Supervisor da Loja (SUPERVISOR)'),
                (PapelUsuarioEnum.USUARIO, 'Usuário Padrão da Loja (USUÁRIO)'),
            ]
            self.fields['loja'].queryset = Loja.objects.filter(id=self.autor.perfil.loja_id)
            self.fields['loja'].disabled = True

        # Preenche os valores iniciais de papel e loja a partir do perfil do usuário em edição
        if perfil_alvo:
            self.fields['papel'].initial = perfil_alvo.papel
            self.fields['loja'].initial = perfil_alvo.loja

        # Trava de segurança: impede que um usuário desative a própria conta ou modifique seu próprio papel/loja
        if self.autor == user_alvo:
            self.fields['is_active'].disabled = True
            self.fields['papel'].disabled = True
            self.fields['loja'].disabled = True

    # Validação de autorização antes de confirmar a alteração de papel hierárquico
    def clean(self):
        cleaned_data = super().clean()
        novo_papel = cleaned_data.get('papel')
        user_alvo = self.instance
        perfil_alvo = getattr(user_alvo, 'perfil', None)

        # Se o papel foi modificado, valida na matriz pode_alterar_papel
        if perfil_alvo and novo_papel != perfil_alvo.papel:
            if not pode_alterar_papel(self.autor, user_alvo, novo_papel):
                raise ValidationError("Você não possui permissão para alterar o papel deste usuário.")

        return cleaned_data

    # Persiste as alterações no modelo User e atualiza o PerfilUsuario correspondente
    def save(self, commit=True):
        user = super().save(commit=commit)
        # Se commit=True e o usuário possui perfil registrado
        if commit and hasattr(user, 'perfil'):
            perfil = user.perfil
            novo_papel = self.cleaned_data.get('papel')
            nova_loja = self.cleaned_data.get('loja')

            # Atualiza o papel caso o campo não tenha sido desabilitado por travas de segurança
            if novo_papel and not self.fields['papel'].disabled:
                perfil.papel = novo_papel
                # Usuários DEV possuem loja nula por definição
                if novo_papel == PapelUsuarioEnum.DEV:
                    perfil.loja = None
                # Para outros papéis, atualiza a loja se permitido
                elif nova_loja and not self.fields['loja'].disabled:
                    perfil.loja = nova_loja
                perfil.save()
        return user


# Declaração do formulário para redefinição administrativa direta de senhas de subordinados
class UsuarioPasswordResetAdminForm(forms.Form):
    # Início do bloco de docstring explicativa
    """
    O QUE FAZ: Formulário de redefinição de senha administrativa por gestores.
    POR QUE FAZ: Permite que administradores definam novas credenciais para subordinados.
    PERMISSÕES RBAC: DEV e ADMIN.
    MULTI-TENANCY: Restrito à própria loja para ADMIN.
    """
    # Fim da docstring informativa

    # Campo para a nova senha do usuário subordinado
    nova_senha1 = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo de 8 caracteres'})
    )
    # Campo para repetição da nova senha
    nova_senha2 = forms.CharField(
        label="Confirmação da Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite a senha novamente'})
    )

    # Validação de confirmação de senha e tamanho mínimo
    def clean(self):
        cleaned_data = super().clean()
        s1 = cleaned_data.get('nova_senha1')
        s2 = cleaned_data.get('nova_senha2')

        # Valida se ambas as senhas coincidem
        if s1 and s2 and s1 != s2:
            self.add_error('nova_senha2', "As senhas digitadas não conferem.")
        # Impõe comprimento mínimo de 8 caracteres
        if s1 and len(s1) < 8:
            self.add_error('nova_senha1', "A nova senha deve conter no mínimo 8 caracteres.")
        return cleaned_data

    # Aplica a nova senha no usuário alvo via algoritmo de hash do Django (set_password)
    def save(self, user):
        user.set_password(self.cleaned_data['nova_senha1'])
        user.save()
        return user
