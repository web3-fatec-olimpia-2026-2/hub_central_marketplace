# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo matemático padrão para operações numéricas como arredondamento para baixo (floor)
import math

# Importa a classe Decimal para manipulação monetária exata sem erros de ponto flutuante
from decimal import Decimal

# Importa a tipagem Optional para indicar parâmetros que podem receber um tipo específico ou None
from typing import Optional

# Importa o módulo de modelos ORM do Django para definição de entidades e campos de banco de dados
from django.db import models

# Importa a exceção padrão do Django utilizada para disparar erros de validação de modelo
from django.core.exceptions import ValidationError

# Importa a entidade User padrão do Django para referenciar operadores nos registros de auditoria
from django.contrib.auth.models import User

# Importa o módulo timezone para manipulação correta de datas cientes de fuso horário
from django.utils import timezone

# Importa a entidade de credencial e conta de integração nos marketplaces
from apps.marketplaces.models import ContaMarketplace

# Importa o modelo mestre de produtos físicos gerenciados no catálogo interno
from apps.catalogo.models import Produto


# Modelo representativo da publicação comercial exposta em uma conta de marketplace
class Anuncio(models.Model):
    # Docstring descrevendo a responsabilidade arquitetural, segregação do estoque físico e multi-tenancy
    """
    O QUE FAZ: Representa o Anúncio/Listing publicado em um marketplace (ex.: Mercado Livre MLB123456).
    POR QUE FAZ: Segrega o domínio comercial (cota lógica de venda do anúncio) do inventário físico (Produto),
                 permitindo anúncios unitários e kits com multiplicadores subordinados ao estoque real.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (gestão completa); USUARIO (leitura).
    MULTI-TENANCY: Vinculado à ContaMarketplace da Loja do lojista.
    """

    # Opções válidas para o status de publicação comercial do anúncio no canal parceiro
    STATUS_CHOICES = [
        ('active', 'Ativo'),
        ('paused', 'Pausado'),
        ('closed', 'Finalizado'),
        ('under_review', 'Em Revisão'),
        ('inactive', 'Inativo'),
    ]

    # Opções para a máquina de estados do ciclo de sincronização entre o hub e o canal
    STATUS_SINCRONIZACAO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ENVIADO', 'Enviado'),
        ('CANCELADO', 'Cancelado'),
    ]

    # Relacionamento que ancora o anúncio à conta de integração e ao tenant dono da operação
    conta = models.ForeignKey(
        ContaMarketplace,
        on_delete=models.CASCADE,
        related_name='anuncios_publicados',
        verbose_name="Conta do Marketplace"
    )

    # Identificador alfanumérico atribuído pelo marketplace (ex: MLB...) com índice para buscas rápidas
    item_id_externo = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="ID Externo do Anúncio (ex: MLB123456789)"
    )

    # Título do anúncio exibido comercialmente aos compradores na plataforma externa
    titulo = models.CharField(
        max_length=255,
        verbose_name="Título do Anúncio"
    )

    # Preço de venda configurado para o anúncio com precisão de duas casas decimais
    preco_venda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Preço de Venda (R$)"
    )

    # Cota lógica enviada e visível no canal externo no momento da última sincronização
    estoque_publicado = models.IntegerField(
        default=0,
        verbose_name="Estoque Publicado no Canal (Snapshot Lógico)"
    )

    # Estado da fila de envio para orientar o disparo de rotinas de sincronização
    status_sincronizacao = models.CharField(
        max_length=20,
        choices=STATUS_SINCRONIZACAO_CHOICES,
        default='PENDENTE',
        db_index=True,
        verbose_name="Estado da Sincronização"
    )

    # Status atual do anúncio perante a API do canal remoto
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="Status do Anúncio"
    )

    # Código SKU próprio atribuído pelo vendedor para conciliação no canal externo
    sku_vendedor = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="SKU Informado pelo Vendedor (seller_custom_field)"
    )

    # URL pública da imagem de miniatura da publicação
    thumbnail = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Imagem / Thumbnail"
    )

    # URL pública direta da página do produto no site do canal de venda
    permalink = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Link Público do Anúncio"
    )

    # Timestamp atualizado automaticamente sempre que os dados locais do anúncio sofrem mutação
    data_sincronizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Sincronização"
    )

    # Data e hora do registro inicial deste anúncio na base do hub
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    # Data e hora da última modificação do registro no banco local
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    # Configurações de metadados e restrições de integridade do modelo
    class Meta:
        # Nome singular da entidade para visualizações administrativas
        verbose_name = "Anúncio"
        # Nome plural da entidade
        verbose_name_plural = "Anúncios"
        # Impede a duplicação do mesmo ID externo de anúncio dentro da mesma conta de marketplace
        unique_together = ('conta', 'item_id_externo')
        # Ordenação padrão decrescente pela data de última atualização
        ordering = ['-atualizado_em']

    # Representação amigável em string exibindo o canal, ID externo e início do título
    def __str__(self):
        # Obtém o nome legível do marketplace vinculado à conta
        canal = self.conta.get_canal_display() if self.conta else "Marketplace"
        # Retorna o identificador formatado
        return f"[{canal}] {self.item_id_externo} — {self.titulo[:40]}"

    # Propriedade para compatibilidade e leitura do timestamp da última sincronização
    @property
    def ultima_sincronizacao(self):
        """Retorna o timestamp da última sincronização do anúncio."""
        # Retorna o valor do campo data_sincronizacao
        return self.data_sincronizacao

    # Avalia dinamicamente se o anúncio possui características de kit ou agrupamento
    @property
    def eh_kit(self) -> bool:
        """Indica se o anúncio é composto por kit (mais de 1 produto ou multiplicador > 1)."""
        # Consulta todos os componentes físicos cadastrados na composição deste anúncio
        itens = self.itens_composicao.all()
        # Se contiver mais de um produto físico diferente vinculado, classifica como kit
        if itens.count() > 1:
            return True
        # Recupera o primeiro e único item da composição
        primeiro = itens.first()
        # Classifica como kit caso a quantidade exigida daquele produto único seja maior que 1
        return bool(primeiro and primeiro.quantidade > 1)

    # Determina a tipologia comercial da oferta com base na composição de itens vinculados
    @property
    def tipo_composicao(self) -> str:
        """
        Retorna a classificação arquitetural da composição comercial do anúncio:
        - "Sem Vínculo": nenhum produto físico associado;
        - "Item Simples": 1 produto com multiplicador = 1;
        - "Kit Homogêneo": 1 produto com multiplicador > 1;
        - "Combo Multi-Produto": 2 ou mais produtos físicos heterogêneos vinculados.
        """
        # Avalia a lista completa de componentes em memória para evitar múltiplas queries
        itens = list(self.itens_composicao.all())
        # Caso o anúncio não possua nenhum item associado na ficha técnica
        if not itens:
            return "Sem Vínculo"
        # Caso possua exatamente um produto físico associado
        if len(itens) == 1:
            # Retorna 'Kit Homogêneo' se quantidade > 1 ou 'Item Simples' se for unitário
            return "Kit Homogêneo" if itens[0].quantidade > 1 else "Item Simples"
        # Retorna 'Combo Multi-Produto' quando houver 2 ou mais produtos distintos
        return "Combo Multi-Produto"

    # Retorna o dicionário de renderização com classe de CSS, rótulo e ícone Bootstrap
    @property
    def tipo_composicao_badge(self) -> dict:
        """
        Retorna metadados de estilo, label e ícone para renderização uniforme nos templates (ADR-013).
        """
        # Obtém a string de classificação da composição do anúncio
        tipo = self.tipo_composicao
        # Metadados de badge visual para item simples unitário
        if tipo == "Item Simples":
            return {
                'label': 'Item Simples',
                'badge_class': 'badge bg-light text-dark border',
                'icon': 'bi-box'
            }
        # Metadados de badge visual para pacote homogêneo com multiplicador
        elif tipo == "Kit Homogêneo":
            return {
                'label': 'Kit Homogêneo',
                'badge_class': 'badge bg-info text-dark',
                'icon': 'bi-collection'
            }
        # Metadados de badge visual para combo multiproduto com múltiplos SKUs
        elif tipo == "Combo Multi-Produto":
            return {
                'label': 'Combo Multi-Produto',
                'badge_class': 'badge bg-primary text-white',
                'icon': 'bi-boxes'
            }
        # Metadados de badge visual de alerta para anúncios que ainda não foram vinculados a produtos físicos
        return {
            'label': 'Sem Vínculo',
            'badge_class': 'badge bg-secondary',
            'icon': 'bi-exclamation-triangle'
        }

    # Calcula a cota comercial máxima que pode ser anunciada sem gerar ruptura de estoque
    def calcular_cota_disponivel(self) -> int:
        """
        O QUE FAZ: Calcula a cota máxima vendável elegível com base no estoque real físico dos produtos vinculados.
        REGRA: cota = min(floor(saldo_disponivel_produto_i / quantidade_item_i)) para todos os produtos da composição.
        Se não possuir itens de composição vinculados, retorna o próprio estoque_publicado atual.
        """
        # Carrega os itens da composição resolvendo antecipadamente o relacionamento de produto
        itens = self.itens_composicao.select_related('produto').all()
        # Se não houver produtos físicos amarrados, preserva o estoque publicado atual como fallback seguro
        if not itens.exists():
            return max(0, self.estoque_publicado)

        # Lista para armazenar o limite individual de kits suportado por cada componente
        limites = []
        # Percorre cada produto que compõe a estrutura do anúncio
        for item in itens:
            # Obtém a entidade do produto físico
            produto = item.produto
            # Extrai o saldo disponível líquido ou assume o estoque total como fallback
            saldo_real = getattr(produto, 'saldo_disponivel', produto.estoque)
            # Ignora configurações inconsistentes com multiplicador zero ou negativo
            if item.quantidade <= 0:
                continue
            # Calcula quantas unidades inteiras deste kit o saldo físico individual é capaz de atender
            limites.append(math.floor(saldo_real / item.quantidade))

        # Se nenhum componente válido foi avaliado, a cota vendável é nula
        if not limites:
            return 0
        # A cota global do anúncio é o gargalo (menor valor entre todos os componentes) limitado a no mínimo zero
        return max(0, min(limites))

    # Propriedade utilitária para obter a cota disponível calculada sem necessidade de invocar o método
    @property
    def cota_calculada(self) -> int:
        """Retorna a cota física máxima calculada para o anúncio."""
        # Redireciona para o método de cálculo de cota disponível
        return self.calcular_cota_disponivel()

    # Avalia se os dados locais do anúncio divergiram do catálogo físico ou das regras comerciais
    def esta_pendente(self, preco_catalogo: Optional[Decimal] = None) -> bool:
        """
        O QUE FAZ: Verifica se o anúncio possui divergência física de cota ou preço em relação ao catálogo.
        """
        # Se a sincronização já estiver explicitamente marcada como PENDENTE na base
        if self.status_sincronizacao == 'PENDENTE':
            return True
        # Obtém a cota vendável calculada com base no inventário atual
        cota = self.calcular_cota_disponivel()
        # Se o estoque divulgado no canal divergir da cota calculada real, acusa pendência
        if self.estoque_publicado != cota:
            return True
        # Se for item simples e o preço do anúncio divergir do preço base do catálogo informado
        if preco_catalogo is not None and not self.eh_kit and self.preco_venda != preco_catalogo:
            return True
        # Se não houver desvios de saldo nem de preço, o anúncio está alinhado
        return False


# Modelo que mapeia os produtos físicos que integram a composição/kit do anúncio (BOM)
class AnuncioComposicao(models.Model):
    # Docstring descrevendo o propósito de desdobramento de kits e a restrição de tenant
    """
    O QUE FAZ: Mapeia os Produtos físicos que compõem o Anúncio (Ficha Técnica / Bill of Materials).
    POR QUE FAZ: Suporta tanto anúncios unitários (1:1 com quantidade=1) quanto Kits (1:N ou quantidade > 1),
                 garantindo que baixas de pedidos debitem as quantidades exatas dos produtos reais.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Produto físico e Anúncio devem pertencer à mesma Loja.
    """

    # Chave estrangeira ligando o componente ao anúncio pai
    anuncio = models.ForeignKey(
        Anuncio,
        on_delete=models.CASCADE,
        related_name='itens_composicao',
        related_query_name='composicoes',
        verbose_name="Anúncio"
    )

    # Chave estrangeira apontando para o produto físico real mantido no catálogo
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='anuncios_vinculados',
        related_query_name='composicoes',
        verbose_name="Produto Físico no Catálogo (Fonte da Verdade)"
    )

    # Multiplicador que define quantas unidades físicas deste produto são consumidas por venda do anúncio
    quantidade = models.PositiveIntegerField(
        default=1,
        verbose_name="Quantidade por Embalagem / Multiplicador do Kit"
    )

    # Data de vinculação do componente físico ao anúncio
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    # Data da última edição cadastrada na quantidade ou produto da composição
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    # Metadados de integridade relacional da tabela de composição
    class Meta:
        # Nome singular da entidade
        verbose_name = "Composição do Anúncio"
        # Nome plural da entidade
        verbose_name_plural = "Composições do Anúncio"
        # Garante que o mesmo produto físico não seja cadastrado duas vezes para o mesmo anúncio
        unique_together = ('anuncio', 'produto')
        # Ordenação padrão pelas chaves de anúncio e produto
        ordering = ['anuncio', 'produto']

    # Representação em string exibindo o fator multiplicador, SKU e ID externo do anúncio
    def __str__(self):
        return f"{self.quantidade}x [{self.produto.sku}] {self.produto.nome} no anúncio {self.anuncio.item_id_externo}"

    # Validação estrutural de isolamento entre tenants executada antes da gravação
    def clean(self):
        # Executa as validações originais de Model
        super().clean()
        # Se os relacionamentos de anúncio e produto já estiverem definidos na instância
        if self.anuncio_id and self.produto_id:
            # Obtém o identificador da loja proprietária da conta do anúncio
            loja_anuncio = self.anuncio.conta.loja_id
            # Obtém o identificador da loja proprietária do produto físico
            loja_produto = self.produto.loja_id
            # Bloqueia a gravação caso o produto e a conta pertençam a lojistas diferentes
            if loja_anuncio != loja_produto:
                raise ValidationError("O Produto físico e o Anúncio devem pertencer à mesma Loja (Tenant).")


# Modelo para auditoria e rastreabilidade histórica de alterações de preço e estoque nos anúncios
class HistoricoSincronizacaoAnuncio(models.Model):
    # Docstring descrevendo a finalidade de conformidade, auditoria e rastreabilidade operacional
    """
    O QUE FAZ: Registra a trilha de auditoria do ciclo de sincronização do anúncio.
    POR QUE FAZ: Rastreabilidade de transição de estados [PENDENTE, ENVIADO, CANCELADO],
                 preço/cota propostos vs anteriores e identificação do responsável.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (leitura); gravação automática.
    """

    # Vínculo com o anúncio que sofreu a modificação ou sincronização
    anuncio = models.ForeignKey(
        Anuncio,
        on_delete=models.CASCADE,
        related_name='historico_ciclo',
        verbose_name="Anúncio"
    )

    # Estado resultante assumido pelo anúncio após a operação auditada
    status_resultante = models.CharField(
        max_length=20,
        choices=Anuncio.STATUS_SINCRONIZACAO_CHOICES,
        verbose_name="Status Resultante"
    )

    # Preço do anúncio registrado antes da execução da rotina
    preco_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Anterior (R$)"
    )

    # Novo preço calculado ou informado para envio ao canal externo
    preco_proposto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Proposto / Atualizado (R$)"
    )

    # Saldo de cota anterior armazenado no snapshot
    estoque_anterior = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Estoque / Cota Anterior"
    )

    # Nova cota calculada proposta para publicação no marketplace
    estoque_proposto = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Estoque / Cota Proposta"
    )

    # Usuário autenticado que acionou a operação, ou nulo caso tenha sido acionado pelo sistema
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Responsável"
    )

    # Texto descritivo informando a origem ou a justificativa da atualização
    motivo = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Motivo / Operação"
    )

    # Registro de quando a pendência de sincronização foi originalmente detectada
    data_pendencia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data / Hora da Pendência"
    )

    # Data e hora exatas da criação deste registro de auditoria
    criado_em = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data / Hora da Decisão / Registro"
    )

    # Fotografia completa em formato JSON do anúncio antes do evento de modificação
    snapshot_antes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Snapshot Antes da Operação"
    )

    # Fotografia completa em formato JSON do anúncio logo após o evento de modificação
    snapshot_depois = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Snapshot Depois da Operação"
    )

    # Metadados de apresentação e ordenação do histórico
    class Meta:
        # Nome singular da entidade de auditoria
        verbose_name = "Histórico de Ciclo do Anúncio"
        # Nome plural da entidade
        verbose_name_plural = "Históricos de Ciclos dos Anúncios"
        # Ordenação cronológica decrescente para priorizar os eventos mais recentes
        ordering = ['-criado_em']

    # Representação em string exibindo o anúncio, o status gerado e o operador responsável
    def __str__(self):
        # Determina o nome de exibição do autor da ação (usuário ou sistema)
        user_str = self.usuario.username if self.usuario else "Sistema"
        # Retorna o sumário textual do log de histórico
        return f"[{self.anuncio.item_id_externo}] -> {self.get_status_resultante_display()} por {user_str}"

