# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o objetivo dos formulários, conformidade com ADRs e suporte a kits/combos
"""
Formulários e Formsets para o Módulo de Anúncios e Composições Comerciais (ADR-003 e ADR-009).
Suporta criação manual direta de anúncios e gestão de composições heterogêneas multiproduto (kits/combos).
"""
# Fim do bloco de docstring informativa do módulo de formulários

# Importa a classe Decimal para manipulação precisa de valores monetários sem inconsistências de ponto flutuante
from decimal import Decimal

# Importa o módulo forms padrão do Django para construção de formulários HTML e validação de dados de entrada
from django import forms

# Importa o validador nativo que rejeita entradas numéricas inferiores ao patamar mínimo estipulado
from django.core.validators import MinValueValidator

# Importa a função utilitária do app tenancy que verifica se o usuário possui papel/perfil de desenvolvedor (DEV)
from apps.tenancy.permissions import usuario_is_dev

# Importa o modelo de Contas de Integração vinculadas aos canais de marketplace
from apps.marketplaces.models import ContaMarketplace

# Importa o modelo que representa a entidade mestre de Produtos físicos no catálogo
from apps.catalogo.models import Produto

# Importa a enumeração de status do ciclo de vida dos produtos (Ativo, Inativo, Arquivado)
from apps.catalogo.enums import StatusProdutoEnum

# Importa os modelos de Anúncio e a tabela associativa de Composição (produtos físicos que formam o anúncio/kit)
from apps.anuncios.models import Anuncio, AnuncioComposicao


# Declaração do formulário baseado em modelo para cadastro e alteração de instâncias de Anuncio
class AnuncioForm(forms.ModelForm):
    # Início do bloco de docstring detalhando o propósito do form e o isolamento de tenant
    """
    Formulário para cadastro e edição manual direta de Anúncios nos Marketplaces.
    Isola a seleção de ContaMarketplace estritamente ao tenant do usuário logado (ADR-003).
    """
    # Fim do bloco de docstring explicativa

    # Subclasse interna de metadados obrigatória para vincular o formulário ao modelo do banco de dados
    class Meta:
        # Aponta explicitamente para o modelo Anuncio como base estrutural deste formulário
        model = Anuncio
        # Lista ordenada de atributos do modelo que serão expostos nos campos do formulário
        fields = [
            # Campo para associação com a conta e credencial do marketplace
            'conta',
            # Identificador do anúncio gerado no canal externo (ex: MLB...)
            'item_id_externo',
            # Título principal da publicação no marketplace
            'titulo',
            # Identificador SKU comercial utilizado pelo lojista
            'sku_vendedor',
            # Preço final de venda anunciado
            'preco_venda',
            # Estado atual do anúncio (Ativo, Pausado, etc.)
            'status'
        ]
        # Dicionário customizado de renderização visual e comportamental dos inputs HTML
        widgets = {
            # Renderiza o campo conta como menu suspenso (<select>) estilizado com Bootstrap e obrigatório
            'conta': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            # Renderiza o identificador externo com fonte monoespaçada e texto auxiliar de orientação
            'item_id_externo': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Ex: MLB123456789 ou SKU-EXTERNO',
                'required': True
            }),
            # Renderiza o campo de texto para o título da oferta na interface do marketplace
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título comercial exibido no marketplace',
                'required': True
            }),
            # Renderiza o campo de SKU do lojista com formatação monoespaçada para fácil leitura de códigos
            'sku_vendedor': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Código SKU comercial do anúncio'
            }),
            # Renderiza o input numérico do preço com duas casas decimais e valor mínimo de 1 centavo
            'preco_venda': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00',
                'required': True
            }),
            # Renderiza o campo seletor de status com classe de layout Bootstrap
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    # Construtor customizado para recepcionar a injeção do usuário logado e isolar dados multi-tenant
    def __init__(self, *args, user=None, **kwargs):
        # Chama a inicialização da classe-mãe ModelForm passando os argumentos posicionais e nomeados
        super().__init__(*args, **kwargs)
        # Armazena a referência do usuário autenticado na instância do formulário
        self.user = user

        # Escopo Multi-Tenant de Contas (ADR-003):
        # Em edição de anúncio existente, a conta pertence estritamente à loja do anúncio (mesmo para DEV).
        # Verifica se o formulário está tratando um anúncio já existente no banco de dados com conta vinculada
        if self.instance and getattr(self.instance, 'conta_id', None):
            # Obtém a loja dona do anúncio recuperada através da conta associada
            loja_anuncio = self.instance.conta.loja
            # Restringe o queryset do campo conta às integrações ativas daquela mesma loja, ordenadas por apelido
            self.fields['conta'].queryset = ContaMarketplace.objects.filter(
                loja=loja_anuncio, ativo=True
            ).order_by('apelido_conta')
        # Bloco executado para novas criações de anúncios quando o usuário foi informado
        elif user:
            # Caso o usuário possua privilégios de desenvolvedor global do sistema
            if usuario_is_dev(user):
                # Permite acesso a todas as contas ativas de qualquer loja, otimizando a consulta via select_related
                self.fields['conta'].queryset = ContaMarketplace.objects.filter(
                    ativo=True
                ).select_related('loja').order_by('apelido_conta')
            # Fluxo para usuários regulares e operadores de loja específica
            else:
                # Recupera o perfil estendido atrelado ao usuário Django
                perfil = getattr(user, 'perfil', None)
                # Extrai a loja vinculada ao perfil caso o objeto exista
                loja = getattr(perfil, 'loja', None) if perfil else None
                # Se o operador possuir uma loja configurada
                if loja:
                    # Filtra estritamente as contas integradas da respectiva loja do operador
                    self.fields['conta'].queryset = ContaMarketplace.objects.filter(
                        loja=loja, ativo=True
                    ).order_by('apelido_conta')
                # Caso o usuário não tenha loja atrelada no perfil
                else:
                    # Zera as opções do campo conta para evitar vazamento transversal de dados de outros lojistas
                    self.fields['conta'].queryset = ContaMarketplace.objects.none()

        # Define a mensagem padrão de placeholder da primeira opção do menu seletor de contas
        self.fields['conta'].empty_label = "Selecione a conta de integração..."


# Formulário que representa um item individual na lista de componentes físicos de uma oferta (kit ou produto único)
class AnuncioComposicaoItemForm(forms.ModelForm):
    # Início da docstring que documenta o papel da ficha técnica do anúncio e a política multi-tenant
    """
    Formulário individual para cada componente físico vinculado ao Anúncio na Composição (Ficha Técnica).
    Garante isolamento estrito por Loja mesmo quando acessado por operador com papel DEV.
    """
    # Fim da docstring explicativa da ficha técnica

    # Campo numérico explícito para definir a quantidade física que compõe o kit anunciado
    quantidade = forms.IntegerField(
        # Validação a nível de formulário que impede números menores que 1
        min_value=1,
        # Validador de modelo redundante garantindo que a quantidade nunca seja zero ou negativa
        validators=[MinValueValidator(1)],
        # Define 1 como valor pré-preenchido por padrão
        initial=1,
        # Renderização HTML com alinhamento centralizado, estilo enfatizado e restrição no atributo min
        widget=forms.NumberInput(attrs={
            'class': 'form-control text-center fw-bold input-item-qtd',
            'min': 1,
            'value': 1,
            'placeholder': '1'
        })
    )

    # Subclasse de configuração vinculando o sub-formulário ao modelo AnuncioComposicao
    class Meta:
        # Aponta o modelo relacional de itens de composição
        model = AnuncioComposicao
        # Expõe os campos de seleção do produto do catálogo e sua respectiva quantidade física
        fields = ['produto', 'quantidade']
        # Customização do widget para seleção de produto com classes de estilização
        widgets = {
            'produto': forms.Select(attrs={
                'class': 'form-select select-item-produto',
                'required': True
            }),
        }

    # Construtor do item da composição recebendo parâmetros explícitos de loja e usuário
    def __init__(self, *args, loja=None, user=None, **kwargs):
        # Executa a inicialização padrão de ModelForm
        super().__init__(*args, **kwargs)
        # Registra a loja alvo na instância do formulário
        self.loja = loja
        # Registra o usuário que submeteu o formulário
        self.user = user

        # Se não informada diretamente, infere a loja a partir da instância do anúncio
        # Checa se o formulário é de edição e recupera a loja através das relações do anúncio pai
        if not self.loja and self.instance and getattr(self.instance, 'anuncio_id', None):
            # Obtém a loja a partir do encadeamento anúncio -> conta -> loja
            self.loja = self.instance.anuncio.conta.loja

        # Escopo Multi-Tenant Estrito de Produtos (ADR-003):
        # Mesmo para usuário DEV, os produtos DEVEM ser restritos à loja do anúncio em questão.
        # Caso a loja de destino esteja bem definida
        if self.loja:
            # Lista apenas os produtos cadastrados sob o tenant daquela loja e com status estritamente ATIVO
            self.fields['produto'].queryset = Produto.objects.filter(
                loja=self.loja, status=StatusProdutoEnum.ATIVO
            ).order_by('nome')
        # Tratamento de salvaguarda quando a loja não veio explícita e o operador não é usuário DEV
        elif user and not usuario_is_dev(user):
            # Obtém o perfil vinculado ao usuário corrente
            perfil = getattr(user, 'perfil', None)
            # Extrai a loja do perfil
            loja_user = getattr(perfil, 'loja', None) if perfil else None
            # Se encontrou a loja no perfil do usuário
            if loja_user:
                # Limita a listagem aos produtos ativos daquela loja
                self.fields['produto'].queryset = Produto.objects.filter(
                    loja=loja_user, status=StatusProdutoEnum.ATIVO
                ).order_by('nome')
            # Se não houver loja válida mapeada no usuário
            else:
                # Esvazia as opções para impedir seleção acidental de dados órfãos
                self.fields['produto'].queryset = Produto.objects.none()
        # Tratamento defensivo caso seja um usuário DEV sem loja contextualizada no anúncio
        else:
            # DEV sem loja vinculada à conta ainda não pode vincular produtos aleatórios
            # Bloqueia a seleção até que uma conta/loja válida seja previamente selecionada
            self.fields['produto'].queryset = Produto.objects.none()

        # Texto padrão inicial para guiar a seleção de um produto físico do catálogo
        self.fields['produto'].empty_label = "Selecione um produto físico do catálogo..."


# Classe base para conjunto de formulários inline (formset), contendo validações consolidadas do conjunto de linhas
class BaseAnuncioComposicaoFormSet(forms.BaseInlineFormSet):
    # Início do bloco de docstring descrevendo as duas principais validações de integridade comercial
    """
    Formset com validações de integridade e multi-tenancy para composições de anúncios:
    1. Impede a duplicação do mesmo produto físico em mais de uma linha de composição.
    2. Garante que todos os produtos pertençam estritamente à mesma Loja da conta do anúncio (ADR-003), inclusive para usuário DEV.
    """
    # Fim do bloco de documentação do formset

    # Construtor do formset inline recebendo a loja e o operador responsável
    def __init__(self, *args, loja=None, user=None, **kwargs):
        # Atribui a loja informada para validação de tenant
        self.loja = loja
        # Atribui o usuário para verificação de permissões
        self.user = user
        # Se a loja não foi passada mas a instância mestre do anúncio já possui conta, descobre a loja automaticamente
        if not self.loja and self.instance and getattr(self.instance, 'conta_id', None):
            # Infere a loja diretamente da conta do anúncio pai
            self.loja = self.instance.conta.loja
        # Invoca o construtor base de BaseInlineFormSet
        super().__init__(*args, **kwargs)

    # Método interceptor responsável por repassar argumentos customizados para cada linha (sub-formulário) gerada
    def get_form_kwargs(self, index):
        # Obtém o dicionário padrão de parâmetros do formulário filho na posição informada
        kwargs = super().get_form_kwargs(index)
        # Identifica a loja efetiva armazenada no formset
        loja_efetiva = self.loja
        # Em edições onde a conta já está gravada, garante que a loja venha da conta do anúncio
        if not loja_efetiva and self.instance and getattr(self.instance, 'conta_id', None):
            # Atualiza para a loja do anúncio
            loja_efetiva = self.instance.conta.loja
        # Injeta a loja no kwargs da linha filha para que seu __init__ filtre o dropdown corretamente
        kwargs['loja'] = loja_efetiva
        # Injeta a referência do usuário no formulário filho
        kwargs['user'] = self.user
        # Retorna o dicionário de parâmetros enriquecido
        return kwargs

    # Método de validação global do formset executado após as validações individuais de cada campo
    def clean(self):
        # Executa as validações padrão do Django para formsets
        super().clean()
        # Se algum dos formulários já apresentou erro de campo individual, aborta a validação global
        if any(self.errors):
            # Interrompe o processamento prematuro
            return

        # Conjunto em memória para rastrear e detectar produtos duplicados na mesma grade
        produtos_vistos = set()
        # Define a loja de referência contra a qual todos os produtos da composição serão validados
        loja_alvo = self.loja

        # Caso o anúncio pai possua a conta persistida, consolida a loja dela como autoridade primária
        if self.instance and getattr(self.instance, 'conta_id', None):
            # Define a loja oficial do anúncio
            loja_alvo = self.instance.conta.loja

        # Itera por cada linha de formulário de item submetida no formset
        for form in self.forms:
            # Se a linha estiver marcada para exclusão física ou lógica pelo usuário, ignora sua validação
            if self.can_delete and self._should_delete_form(form):
                # Passa para a próxima linha
                continue
            # Ignora formulários que não contenham dados preenchidos ou com flag de exclusão acionada
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                # Passa para a próxima linha
                continue

            # Obtém a entidade do produto físico validado no formulário da linha
            produto = form.cleaned_data.get('produto')
            # Se houver um produto selecionado nesta linha
            if produto:
                # 1. Validação de Unicidade no Anúncio: mesmo produto não pode aparecer mais de uma vez
                # Avalia se a chave primária deste produto já foi processada em uma linha anterior
                if produto.id in produtos_vistos:
                    # Lança exceção de validação rejeitando o formulário com mensagem amigável ao operador
                    raise forms.ValidationError(
                        f"O produto '{produto.nome}' (SKU: {produto.sku}) foi adicionado mais de uma vez na composição. "
                        f"Agrupe as unidades desejadas em uma única linha."
                    )
                # Adiciona o ID do produto ao conjunto para garantir a unicidade nas próximas iterações
                produtos_vistos.add(produto.id)

                # 2. Validação Multi-Tenant Estrita (ADR-003) mesmo para DEV: produto deve pertencer à mesma Loja
                # Checa se o tenant do produto físico coincide com o tenant da conta onde o anúncio será publicado
                if loja_alvo and produto.loja_id != loja_alvo.id:
                    # Lança erro impedindo vazamento de dados ou agrupamentos entre lojistas distintos
                    raise forms.ValidationError(
                        f"O produto '{produto.nome}' pertence à loja '{produto.loja.nome}', mas a conta do anúncio "
                        f"pertence à loja '{loja_alvo.nome}'. Todos os componentes devem pertencer ao mesmo Tenant."
                    )


# Fábrica de formset que conecta o modelo pai Anuncio aos seus itens filhos AnuncioComposicao
AnuncioComposicaoInlineFormSet = forms.inlineformset_factory(
    # Modelo mestre
    Anuncio,
    # Modelo dependente (relação ForeignKey 1:N)
    AnuncioComposicao,
    # Formulário customizado para validação das linhas
    form=AnuncioComposicaoItemForm,
    # Classe base do formset com as regras de unicidade e isolamento multi-tenant
    formset=BaseAnuncioComposicaoFormSet,
    # Define a exibição de 1 formulário vazio extra na tela para nova inserção imediata
    extra=1,
    # Habilita o checkbox nativo para permitir remoção de linhas da composição
    can_delete=True
)


# Formulário isolado para operações modais ou rápidas de inclusão de componente na composição
class AnuncioComposicaoForm(forms.ModelForm):
    # Início da docstring explicativa da finalidade do formulário pontual
    """
    Formulário para vincular pontualmente um produto físico a um anúncio existente (via modal/detail).
    """
    # Fim da docstring informativa

    # Metadados vinculando a operação ao modelo AnuncioComposicao
    class Meta:
        # Modelo alvo
        model = AnuncioComposicao
        # Campos exibidos na janela modal
        fields = ['produto', 'quantidade']
        # Widgets com suporte a plugin select2 e campo de quantidade configurado
        widgets = {
            'produto': forms.Select(attrs={'class': 'form-select select2'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
        }

    # Construtor customizado que recebe explicitamente o anúncio pai para restringir o escopo dos produtos
    def __init__(self, *args, anuncio=None, **kwargs):
        # Executa a inicialização padrão do formulário
        super().__init__(*args, **kwargs)
        # Se a referência do anúncio for fornecida na chamada
        if anuncio:
            # Extrai a loja dona do anúncio através do relacionamento com a conta
            loja = anuncio.conta.loja
            # Filtra o menu de produtos permitindo somente itens ativos que pertençam àquela loja
            self.fields['produto'].queryset = Produto.objects.filter(
                loja=loja, status=StatusProdutoEnum.ATIVO
            ).order_by('nome')