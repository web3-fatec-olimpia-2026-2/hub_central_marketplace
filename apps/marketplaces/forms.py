# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo de formulários do Django para construção de classes baseadas em formulários e modelos
from django import forms

# Importa a exceção de validação padrão utilizada para sinalizar erros de integridade ou lógica de negócio
from django.core.exceptions import ValidationError

# Importa o modelo Loja para manipulação de vínculos e isolamento multi-tenant
from apps.tenancy.models import Loja

# Importa a função utilitária de RBAC que verifica se o usuário autenticado possui o papel global DEV
from apps.tenancy.permissions import usuario_is_dev

# Importa o modelo de dados representativo da conta de marketplace integrada
from .models import ContaMarketplace

# Importa o enum que relaciona os marketplaces suportados pela plataforma
from .enums import CanalMarketplaceEnum


# Declaração do formulário de criação e manutenção de contas de marketplace herdando de ModelForm
class ContaMarketplaceForm(forms.ModelForm):
    # Início do bloco de docstring que documenta os objetivos, o modelo híbrido de aplicação e as permissões de acesso
    """
    O QUE FAZ: Formulário de cadastro e edição de Contas e Conexões de Marketplaces.
    POR QUE FAZ: Suporta configuração híbrida (Global SaaS vs Individual Tenant) com proteção criptográfica de segredos.
    PERMISSÕES RBAC: DEV e ADMIN (sua própria loja).
    MULTI-TENANCY: Vínculo automático à loja do autor (ou seleção por DEV).
    """
    # Fim da docstring explicativa

    # Campo de seleção de Loja inicializado vazio, com queryset dinamizado no método __init__
    loja = forms.ModelChoiceField(
        label="Loja (Tenant)",
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Campo de escolha do modo de integração (Aplicação Global Compartilhada SaaS vs Credenciais Próprias da Loja)
    tipo_aplicacao = forms.ChoiceField(
        choices=ContaMarketplace.TIPO_APLICACAO_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='GLOBAL',
        required=False,
        label="Modo de Integração da Aplicação"
    )

    # Campo para entrada pública da chave da aplicação externa (App ID / Client ID / Partner ID)
    app_key_or_id = forms.CharField(
        label="App ID (Client ID) / Partner ID",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control font-monospace',
            'placeholder': 'Ex: 1234567890123456',
            'autocomplete': 'off'
        })
    )

    # Campo protegido para inserção do segredo de cliente (Client Secret), mascarado na interface
    app_secret = forms.CharField(
        label="Client Secret / Partner Key",
        required=False,
        widget=forms.PasswordInput(render_value=True, attrs={
            'class': 'form-control font-monospace',
            'placeholder': '••••••••••••••••••••••••••••••••',
            'autocomplete': 'new-password'
        })
    )

    # Campo protegido para entrada do segredo de validação de assinatura criptográfica de webhooks
    webhook_secret = forms.CharField(
        label="Webhook Secret (Validação de Assinatura)",
        required=False,
        widget=forms.PasswordInput(render_value=True, attrs={
            'class': 'form-control font-monospace',
            'placeholder': '••••••••••••••••••••••••••••••••',
            'autocomplete': 'new-password'
        })
    )

    # Classe Meta com as definições de modelo, campos gerenciados e customização de widgets
    class Meta:
        model = ContaMarketplace
        fields = [
            'loja', 'canal', 'apelido_conta', 'ativo',
            'tipo_aplicacao', 'app_key_or_id', 'app_secret', 'webhook_secret'
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

    # Construtor do formulário que recebe o usuário autor para aplicar restrições contextuais de RBAC e tenant
    def __init__(self, *args, autor=None, **kwargs):
        self.autor = autor
        super().__init__(*args, **kwargs)

        # Se o autor for desenvolvedor (DEV), permite escolher qualquer loja ativa do sistema
        if usuario_is_dev(self.autor):
            self.fields['loja'].queryset = Loja.objects.filter(ativo=True).order_by('nome')
            self.fields['loja'].required = True
            if self.instance.pk:
                self.fields['loja'].initial = self.instance.loja
        # Para operadores e lojistas comuns, restringe exclusivamente à própria loja e trava o campo
        else:
            loja_autor = getattr(self.autor.perfil, 'loja', None) if self.autor else None
            self.fields['loja'].queryset = Loja.objects.filter(id=loja_autor.id) if loja_autor else Loja.objects.none()
            self.fields['loja'].initial = loja_autor
            self.fields['loja'].disabled = True

        # Imutabilidade estrita na edição: Canal e Loja não podem ser alterados
        # Trava os campos 'canal' e 'loja' em modo de edição para garantir integridade referencial dos registros
        if self.instance and self.instance.pk:
            self.fields['canal'].disabled = True
            self.fields['canal'].help_text = "O canal de marketplace é imutável após a criação da conta."
            self.fields['loja'].disabled = True
            self.fields['loja'].help_text = "A loja (tenant) vinculada é imutável após a criação da conta."

            # Preenche valores iniciais dos campos sensíveis se existirem
            # Carrega as credenciais salvas nos campos correspondentes da interface
            if self.instance.tipo_aplicacao:
                self.fields['tipo_aplicacao'].initial = self.instance.tipo_aplicacao
            if self.instance.app_key_or_id:
                self.fields['app_key_or_id'].initial = self.instance.app_key_or_id
            if self.instance.app_secret:
                self.fields['app_secret'].initial = self.instance.app_secret
            if self.instance.webhook_secret:
                self.fields['webhook_secret'].initial = self.instance.webhook_secret

    # Método de limpeza específica para o modo de integração (tipo de aplicação)
    def clean_tipo_aplicacao(self):
        val = self.cleaned_data.get('tipo_aplicacao')
        # Se vier em branco, preserva o valor previamente persistido ou assume 'GLOBAL' como padrão
        if not val:
            if self.instance and getattr(self.instance, 'tipo_aplicacao', None):
                return self.instance.tipo_aplicacao
            return 'GLOBAL'
        return val

    # Método de validação cruzada geral do formulário contendo as regras de integridade e travas de negócio
    def clean(self):
        cleaned_data = super().clean()

        # Em edição, canal e loja são estritamente imutáveis e assumem os valores da instância original
        # Assegura que em updates as chaves de loja e canal venham da instância original do banco
        if self.instance and self.instance.pk:
            loja = self.instance.loja
            canal = self.instance.canal
            cleaned_data['loja'] = loja
            cleaned_data['canal'] = canal
        # Em criação de nova conta, extrai os valores validados conforme o nível de privilégio do autor
        else:
            if not usuario_is_dev(self.autor):
                loja = getattr(self.autor.perfil, 'loja', None) if self.autor else None
                cleaned_data['loja'] = loja
            else:
                loja = cleaned_data.get('loja')
            canal = cleaned_data.get('canal')

        # Validação obrigatória da loja
        if not loja:
            self.add_error('loja', "A seleção de uma Loja é obrigatória.")

        # Validação obrigatória do canal de marketplace
        if not canal:
            self.add_error('canal', "A seleção de um Canal é obrigatória.")

        apelido_conta = cleaned_data.get('apelido_conta')
        seller_id = cleaned_data.get('seller_id_externo')

        # 1. Trava Loja + Canal (apenas 1 conexão ativa por canal por loja)
        # Bloqueia a criação de mais de uma conexão para o mesmo marketplace na mesma loja
        if loja and canal:
            qs_canal = ContaMarketplace.objects.filter(loja=loja, canal=canal)
            if self.instance and self.instance.pk:
                qs_canal = qs_canal.exclude(pk=self.instance.pk)
            if qs_canal.exists():
                canal_display = dict(CanalMarketplaceEnum.choices).get(canal, canal)
                self.add_error('canal', f"A loja '{loja.nome}' já possui uma conexão para o canal {canal_display}.")

        # 2. Trava Canal + Seller ID Externo (não pode ser reaproveitado por outra loja)
        # Impede que duas contas distintas compartilhem a mesma identificação de vendedor externo
        if canal and seller_id:
            qs_seller = ContaMarketplace.objects.filter(canal=canal, seller_id_externo=seller_id)
            if self.instance and self.instance.pk:
                qs_seller = qs_seller.exclude(pk=self.instance.pk)
            if qs_seller.exists():
                canal_display = dict(CanalMarketplaceEnum.choices).get(canal, canal)
                self.add_error('seller_id_externo', f"O Seller ID Externo '{seller_id}' já está em uso por outra conta no canal {canal_display}.")

        # 3. Trava Loja + Apelido da Conta (único dentro da loja)
        # Garante unicidade do apelido da conta no escopo do tenant
        if loja and apelido_conta:
            qs_apelido = ContaMarketplace.objects.filter(loja=loja, apelido_conta=apelido_conta)
            if self.instance and self.instance.pk:
                qs_apelido = qs_apelido.exclude(pk=self.instance.pk)
            if qs_apelido.exists():
                self.add_error('apelido_conta', f"Já existe uma conta com o apelido '{apelido_conta}' cadastrada para esta loja.")

        # 4. Validação de credenciais para Modo Individual
        # Exige chaves e segredos específicos caso a loja opte pelo modo de aplicativo próprio
        tipo_app = cleaned_data.get('tipo_aplicacao')
        if tipo_app == 'INDIVIDUAL':
            app_key = cleaned_data.get('app_key_or_id')
            app_sec = cleaned_data.get('app_secret')
            if not app_key:
                self.add_error('app_key_or_id', "O App ID (Client ID) é obrigatório para o modo Aplicativo Próprio / Individual.")

            # Preserva segredo já salvo se o campo for submetido em branco durante edição
            if not app_sec:
                if self.instance and self.instance.pk and self.instance.app_secret:
                    cleaned_data['app_secret'] = self.instance.app_secret
                else:
                    self.add_error('app_secret', "O Client Secret é obrigatório para o modo Aplicativo Próprio / Individual.")

            # Preserva webhook_secret já salvo se deixado em branco
            if not cleaned_data.get('webhook_secret') and self.instance and self.instance.pk and self.instance.webhook_secret:
                cleaned_data['webhook_secret'] = self.instance.webhook_secret

        # Retorna o dicionário de dados completamente higienizado e validado
        return cleaned_data
