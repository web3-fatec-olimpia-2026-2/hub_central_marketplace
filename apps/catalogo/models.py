# Os códigos foram gerados com auxilio de I.A.

# Importa a classe Decimal para manipulação financeira sem erros de arredondamento de ponto flutuante
from decimal import Decimal

# Importa o módulo central de modelos ORM do framework Django
from django.db import models

# Importa a entidade padrão User do Django para atrelar a autoria de mutações de cadastro e auditoria
from django.contrib.auth.models import User

# Importa o utilitário slugify para geração automatizada de slugs ASCII a partir de nomes de categorias
from django.utils.text import slugify

# Importa a exceção nativa para lançamento de erros de integridade e validações de modelo
from django.core.exceptions import ValidationError

# Importa o modelo Loja que representa a segregação multi-inquilino (tenant)
from apps.tenancy.models import Loja

# Importa o modelo que gerencia credenciais de conexão com canais de venda externos
from apps.marketplaces.models import ContaMarketplace

# Importa a enumeração que padroniza os estados de sincronização entre o hub e canais parceiros
from apps.marketplaces.enums import StatusSincronizacaoEnum

# Importa os enums locais para o status do produto físico e motivos de ajuste de inventário
from .enums import StatusProdutoEnum, TipoAjusteEstoqueEnum


# Modelo representativo da classificação taxonômica dos produtos por organização
class Categoria(models.Model):
    # Bloco descritivo documentando o escopo funcional, isolamento multi-tenant (RN-01) e permissões de perfil
    """
    O QUE FAZ: Categorização de produtos organizada por Loja (Tenant).
    POR QUE FAZ: Organização taxonômica do catálogo mantendo rigoroso isolamento multi-tenant (RN-01).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (CRUD completo); USUARIO (criação e edição descritiva; exclusão bloqueada por RN-09).
    MULTI-TENANCY: FK obrigatória para Loja com unicidade composta ('loja', 'slug').
    """

    # Chave estrangeira que vincula a categoria estritamente à sua Loja com exclusão em cascata
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='categorias', verbose_name="Loja (Tenant)"
    )

    # Nome textual legível da categoria
    nome = models.CharField(max_length=100, verbose_name="Nome da Categoria")

    # Identificador textual normalizado utilizado em rotas e filtros amigáveis
    slug = models.SlugField(max_length=120, verbose_name="Identificador (Slug)")

    # Descrição opcional para contexto interno de catálogo
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição da Categoria")

    # Flag lógica para ativação ou desativação de categorias em menus e selects
    ativo = models.BooleanField(default=True, verbose_name="Categoria Ativa")

    # Data e hora do registro inicial da categoria
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    # Data e hora da última modificação dos metadados da categoria
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Configurações de metadados, ordenação e integridade relacional
    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        # Impede a existência de duas categorias com o mesmo identificador (slug) dentro de um mesmo tenant
        unique_together = [['loja', 'slug']]
        # Ordenação alfabética padrão por nome
        ordering = ['nome']

    # Representação em string exibindo o nome da categoria seguido do nome da loja dona
    def __str__(self):
        return f"{self.nome} ({self.loja.nome})"

    # Sobrescreve o método save para garantir geração defensiva de slug com sufixação incremental em caso de colisão
    def save(self, *args, **kwargs):
        # Se o slug não estiver preenchido manualmente
        if not self.slug:
            # Gera o slug base a partir do nome
            base_slug = slugify(self.nome)
            slug = base_slug
            counter = 1
            # Executa loop de verificação enquanto houver colisão de slug para a mesma loja
            while Categoria.objects.filter(loja=self.loja, slug=slug).exclude(pk=self.pk).exists():
                # Concatena sufixo numérico progressivo (-1, -2...)
                slug = f"{base_slug}-{counter}"
                counter += 1
            # Atribui o identificador único resultante
            self.slug = slug
        # Executa a persistência normal no banco de dados
        super().save(*args, **kwargs)


# Entidade central que consolida os dados mestres do catálogo e fonte física de inventário
class Produto(models.Model):
    # Docstring detalhando o conceito de Single Source of Truth, desacoplamento de marketplaces e governança RBAC
    """
    O QUE FAZ: Entidade central do catálogo e Fonte Única da Verdade (Single Source of Truth) para inventário e preços no Hub.
    POR QUE FAZ: Mantém dados mestres de produtos, custos, estoque e precificação de forma desacoplada de canais externos (RF-03).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (acesso total); USUARIO (descritivos e baixa de avaria apenas; alteração de preço e estoque geral bloqueadas por RN-09).
    MULTI-TENANCY: FK para Loja e unicidade composta ('loja', 'sku') (RN-01 / RN-02).
    """

    # Vínculo mandatório com a Loja proprietária do item físico
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='produtos', verbose_name="Loja (Tenant)"
    )

    # Associação com a Categoria da loja, bloqueando exclusão da categoria enquanto houver produtos cadastrados (PROTECT)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='produtos', verbose_name="Categoria"
    )

    # Identificador SKU comercial mestre gerenciado pelo lojista
    sku = models.CharField(
        max_length=60, verbose_name="Código SKU (Identificador Único na Loja)"
    )

    # Nome comercial oficial do produto físico
    nome = models.CharField(max_length=200, verbose_name="Nome do Produto")

    # Descrição completa de ficha técnica e especificações
    descricao = models.TextField(
        blank=True, null=True, verbose_name="Descrição Detalhada do Produto"
    )

    # Preço base de venda do produto físico cadastrado no ERP/Hub
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Preço de Venda (R$)"
    )

    # Saldo físico real apurado em armazém
    estoque = models.IntegerField(
        default=0, verbose_name="Saldo de Estoque Físico"
    )

    # Status operacional de disponibilidade do item perante o hub
    status = models.CharField(
        max_length=20, choices=StatusProdutoEnum.choices, default=StatusProdutoEnum.ATIVO,
        verbose_name="Status do Produto"
    )

    # Custos e Inteligência Financeira
    # Custo unitário de compra/fabricação utilizado para cálculo de margem líquida e lucro operacional
    custo_aquisicao = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True,
        verbose_name="Custo de Aquisição / CMV (R$)",
        help_text="Custo de compra ou fabricação unitária do produto."
    )

    # Custo de insumos de envio (caixa, fita, plástico-bolha)
    custo_embalagem = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True,
        verbose_name="Custo Específico de Embalagem (R$)",
        help_text="Custo de embalagem deste produto. Se 0, herda o padrão da loja."
    )

    # Flag indicando se a mercadoria reside no armazém do marketplace (Full/Fulfillment)
    modalidade_full = models.BooleanField(
        default=False,
        verbose_name="Modalidade Full / Fulfillment",
        help_text="Se marcado, o custo próprio de embalagem é zerado pois o marketplace assume o envio."
    )

    # Estado estático global de sincronização
    status_sincronizacao = models.CharField(
        max_length=20, choices=StatusSincronizacaoEnum.choices,
        default=StatusSincronizacaoEnum.NAO_SINCRONIZADO, verbose_name="Status de Sincronização Geral"
    )

    # Timestamp de inclusão do registro no banco local
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    # Timestamp da última alteração de qualquer campo do produto
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Metadados e restrição de unicidade por loja e SKU
    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        # Garante que o mesmo SKU nunca seja duplicado na mesma Loja (RN-02)
        unique_together = [['loja', 'sku']]
        # Ordenação alfabética padrão por nome
        ordering = ['nome']

    # Representação em texto exibindo SKU, nome, preço e estoque físico
    def __str__(self):
        return f"[{self.sku}] {self.nome} — R$ {self.preco} (Estoque: {self.estoque})"

    # Validação de integridade de regras de negócio antes de persistir o modelo
    def clean(self):
        super().clean()
        # Regra RN-06: Impede que o preço mestre seja registrado com valor negativo
        if self.preco is not None and self.preco < Decimal('0.00'):
            raise ValidationError({'preco': 'O preço de venda não pode ser negativo (RN-06).'})
        # Garante o isolamento multi-tenant: o produto e sua categoria devem pertencer ao mesmo tenant
        if self.categoria_id and self.loja_id:
            if self.categoria.loja_id != self.loja_id:
                raise ValidationError({'categoria': 'A categoria selecionada deve pertencer à mesma loja do produto.'})

    # Sobrescreve save para sanitizar e forçar o SKU em caixa alta sem espaços laterais
    def save(self, *args, **kwargs):
        if self.sku:
            self.sku = self.sku.strip().upper()
        super().save(*args, **kwargs)

    # Propriedade que retorna todos os anúncios (unitários ou kits) que utilizam este produto na ficha técnica
    @property
    def anuncios_publicados(self):
        """
        Retorna QuerySet de Anúncios vinculados a este produto via composição.
        """
        # Importação tardia do modelo Anuncio para evitar referências circulares
        from apps.anuncios.models import Anuncio
        # Retorna a consulta filtrando pelas composições com eliminação de redundâncias
        return Anuncio.objects.filter(composicoes__produto=self).distinct()

    # Propriedade que consolida o status dinâmico de sincronização com base nas ofertas vinculadas
    @property
    def status_sincronizacao_consolidado(self) -> str:
        """
        O QUE FAZ: Calcula dinamicamente o estado de sincronização com base em todos os anúncios vinculados ao produto.
        POR QUE FAZ: Elimina divergências entre o card de informações principais e a tabela de anúncios.
        """
        # Carrega a coleção de anúncios vinculados para avaliação em memória
        anuncios = list(self.anuncios_publicados)
        # Se não houver nenhum anúncio vinculado ao produto
        if not anuncios:
            return "Sem Anúncios"

        # Se todos os anúncios atrelados estiverem marcados como cancelados pelo operador
        todos_cancelados = all(a.status_sincronizacao == 'CANCELADO' for a in anuncios)
        if todos_cancelados:
            return "Sincronização Descartada"

        # Avalia se há pelo menos um anúncio ativo que apresente pendência de envio ou divergência de cota/preço
        tem_pendente = any(
            a.status_sincronizacao == 'PENDENTE' or a.esta_pendente(self.preco)
            for a in anuncios
            if a.status_sincronizacao != 'CANCELADO'
        )
        if tem_pendente:
            return "Pendente de Sincronização"

        # Avalia se todos os anúncios ativos foram confirmados como enviados e sem divergências de preço/cota
        todos_enviados = all(
            a.status_sincronizacao == 'ENVIADO' and not a.esta_pendente(self.preco)
            for a in anuncios
            if a.status_sincronizacao != 'CANCELADO'
        )
        if todos_enviados:
            return "Sincronizado com Sucesso"

        # Fallback defensivo: assume estado de pendência caso haja qualquer inconsistência
        return "Pendente de Sincronização"

    # Mapeia o estado consolidado para a respectiva classe visual de cores do Bootstrap
    @property
    def status_sincronizacao_consolidado_badge(self) -> str:
        """Retorna a classe CSS Bootstrap correspondente ao estado consolidado."""
        st = self.status_sincronizacao_consolidado
        if st == "Sincronizado com Sucesso":
            return "bg-success text-white"
        elif st == "Pendente de Sincronização":
            return "bg-warning text-dark"
        elif st == "Sincronização Descartada":
            return "bg-secondary text-white"
        return "bg-light text-dark border"

    # Método para registrar mutações conjuntas de preço e estoque na trilha de auditoria
    def registrar_historico(
        self,
        estoque_anterior=None,
        novo_estoque=None,
        preco_anterior=None,
        novo_preco=None,
        usuario=None,
        motivo=None,
        **kwargs
    ):
        """
        O QUE FAZ: Registra mutação de preço e/ou estoque físico em HistoricoPreco.
        POR QUE FAZ: Garante rastreabilidade e auditoria unificada no catálogo (RN-04 / RF-05).
        """
        # Se os dados anteriores não foram passados, assume o valor atual persistido
        if preco_anterior is None:
            preco_anterior = self.preco
        # Se o novo preço não foi passado, tenta kwargs ou assume o preço atual
        if novo_preco is None:
            novo_preco = kwargs.get('preco_novo', self.preco)
        # Se o estoque anterior não foi informado, assume o saldo atual da instância
        if estoque_anterior is None:
            estoque_anterior = self.estoque
        # Se o novo estoque não foi informado, tenta kwargs ou assume o estoque atual
        if novo_estoque is None:
            novo_estoque = kwargs.get('estoque_novo', self.estoque)

        # Fallback de autoria: se o usuário executor for nulo, busca o primeiro administrador da loja
        if not usuario and self.loja:
            perfil = self.loja.usuarios.filter(papel__in=['ADMIN', 'DEV']).select_related('usuario').first()
            if not perfil:
                perfil = self.loja.usuarios.select_related('usuario').first()
            if perfil:
                usuario = perfil.usuario

        # Persiste o registro na entidade HistoricoPreco
        return HistoricoPreco.objects.create(
            produto=self,
            loja=self.loja,
            preco_anterior=preco_anterior,
            preco_novo=novo_preco,
            estoque_anterior=estoque_anterior,
            estoque_novo=novo_estoque,
            usuario=usuario,
            motivo=motivo
        )



# Modelo associativo direto para mapeamento 1:1 entre produto físico e canal de venda (legado/suporte direto)
class AnuncioMarketplace(models.Model):
    # Docstring documentando o desacoplamento de identificadores externos por marketplace
    """
    O QUE FAZ: Mapeia o vínculo de um Produto local a um anúncio publicado em uma ContaMarketplace externa.
    POR QUE FAZ: Desacopla o campo fixo meli_item_id, permitindo que um mesmo SKU seja anunciado simultaneamente no Mercado Livre, Shopee, Magalu e Amazon, com rastreabilidade de preços e IDs externos por canal.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Vinculado ao Produto e à ContaMarketplace da mesma Loja.
    """

    # Opções válidas para o status do anúncio direto
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('pausado', 'Pausado'),
        ('finalizado', 'Finalizado'),
        ('pendente', 'Pendente'),
    ]

    # Vínculo com o produto pai
    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='anuncios', verbose_name="Produto"
    )

    # Vínculo com a conta de integração
    conta_marketplace = models.ForeignKey(
        ContaMarketplace, on_delete=models.CASCADE, related_name='anuncios', verbose_name="Conta do Canal"
    )

    # Identificador do anúncio gerado no canal externo com índice de busca
    item_id_externo = models.CharField(
        max_length=100, db_index=True, verbose_name="ID Externo no Marketplace (MLB... / Shopee ID / Magalu SKU)"
    )

    # Situação do anúncio perante a API parceira
    status_anuncio = models.CharField(
        max_length=30, default='ativo', choices=STATUS_CHOICES, verbose_name="Status do Anúncio no Canal"
    )

    # Preço efetivamente transmitido na última sincronização
    preco_sincronizado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Último Preço Sincronizado (R$)"
    )

    # Link web para acesso à oferta pública
    link_anuncio = models.URLField(
        max_length=500, blank=True, null=True, verbose_name="URL Pública do Anúncio"
    )

    # Data da última comunicação de sincronização bem-sucedida
    ultima_sincronizacao = models.DateTimeField(
        auto_now=True, verbose_name="Última Sincronização"
    )

    # Data de vinculação do anúncio direto
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    # Data da última atualização local dos atributos
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Metadados e restrição de unicidade por produto e conta
    class Meta:
        verbose_name = "Anúncio no Marketplace"
        verbose_name_plural = "Anúncios nos Marketplaces"
        # Garante que um mesmo produto só tenha um registro direto por conta de marketplace
        unique_together = ('produto', 'conta_marketplace')
        ordering = ['-criado_em']

    # Representação em string exibindo o SKU, o canal e o ID externo
    def __str__(self):
        return f"{self.produto.sku} -> [{self.conta_marketplace.get_canal_display()}] {self.item_id_externo}"

    # Validação de isolamento multi-tenant garantindo que a conta e o produto sejam da mesma loja
    def clean(self):
        super().clean()
        if self.produto_id and self.conta_marketplace_id:
            if self.produto.loja_id != self.conta_marketplace.loja_id:
                raise ValidationError("O produto e a conta de marketplace devem pertencer à mesma loja.")


# Entidade de persistência dedicada à auditoria e conformidade fiscal de alterações de preço e estoque (RN-04)
class HistoricoPreco(models.Model):
    # Docstring documentando a conformidade com as regras de auditoria conjunta
    """
    O QUE FAZ: Registro histórico unificado de mutações de preços e estoque (RN-04 / RF-05).
    POR QUE FAZ: Rastreabilidade conjunta de precificação e inventário físico na mesma linha.
    PERMISSÕES RBAC: Consulta por DEV, ADMIN e SUPERVISOR; gravação automática em alterações de preço e estoque.
    MULTI-TENANCY: FK para Loja e Produto da loja.
    """

    # Referência ao produto físico alvo da alteração
    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='historico_precos', verbose_name="Produto"
    )

    # Referência à loja para isolamento multi-tenant direto nos relatórios de auditoria
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='historico_precos', verbose_name="Loja (Tenant)"
    )

    # Preço de venda praticado imediatamente antes da alteração
    preco_anterior = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Preço Anterior (R$)"
    )

    # Novo preço definido após a edição
    preco_novo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Novo Preço (R$)"
    )

    # Saldo de estoque registrado antes da mutação física
    estoque_anterior = models.IntegerField(
        null=True, blank=True, verbose_name="Estoque Anterior"
    )

    # Novo saldo físico resultante da operação
    estoque_novo = models.IntegerField(
        null=True, blank=True, verbose_name="Novo Estoque"
    )

    # Usuário que confirmou o ajuste ou nulo caso tenha sido acionado pelo sistema
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='precos_alterados', verbose_name="Usuário Responsável"
    )

    # Justificativa ou descrição textual da motivação do ajuste
    motivo = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Motivo / Operação"
    )

    # Timestamp de gravação do registro histórico
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora da Alteração"
    )

    # Metadados e ordenação decrescente por data de criação
    class Meta:
        verbose_name = "Histórico de Alteração de Preço e Estoque"
        verbose_name_plural = "Históricos de Alterações de Preço e Estoque"
        ordering = ['-criado_em']

    # Representação em texto detalhando a evolução numérica de preço e saldo com o responsável
    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sistema"
        return f"{self.produto.sku}: Preço ({self.preco_anterior} -> {self.preco_novo}) | Estoque ({self.estoque_anterior} -> {self.estoque_novo}) por {user_str}"


# Aliases de compatibilidade histórica para referenciar o modelo de histórico unificado
HistoricoAlteracao = HistoricoPreco
HistoricoPrecoEstoque = HistoricoPreco
