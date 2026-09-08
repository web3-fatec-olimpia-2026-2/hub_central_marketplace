# Os códigos foram gerados com auxilio de I.A.
import math
from decimal import Decimal
from typing import Optional
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from apps.marketplaces.models import ContaMarketplace
from apps.catalogo.models import Produto


class Anuncio(models.Model):
    """
    O QUE FAZ: Representa o Anúncio/Listing publicado em um marketplace (ex.: Mercado Livre MLB123456).
    POR QUE FAZ: Segrega o domínio comercial (cota lógica de venda do anúncio) do inventário físico (Produto),
                 permitindo anúncios unitários e kits com multiplicadores subordinados ao estoque real.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (gestão completa); USUARIO (leitura).
    MULTI-TENANCY: Vinculado à ContaMarketplace da Loja do lojista.
    """
    STATUS_CHOICES = [
        ('active', 'Ativo'),
        ('paused', 'Pausado'),
        ('closed', 'Finalizado'),
        ('under_review', 'Em Revisão'),
        ('inactive', 'Inativo'),
    ]

    STATUS_SINCRONIZACAO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ENVIADO', 'Enviado'),
        ('CANCELADO', 'Cancelado'),
    ]

    conta = models.ForeignKey(
        ContaMarketplace,
        on_delete=models.CASCADE,
        related_name='anuncios_publicados',
        verbose_name="Conta do Marketplace"
    )
    item_id_externo = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="ID Externo do Anúncio (ex: MLB123456789)"
    )
    titulo = models.CharField(
        max_length=255,
        verbose_name="Título do Anúncio"
    )
    preco_venda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Preço de Venda (R$)"
    )
    estoque_publicado = models.IntegerField(
        default=0,
        verbose_name="Estoque Publicado no Canal (Snapshot Lógico)"
    )
    status_sincronizacao = models.CharField(
        max_length=20,
        choices=STATUS_SINCRONIZACAO_CHOICES,
        default='PENDENTE',
        db_index=True,
        verbose_name="Estado da Sincronização"
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="Status do Anúncio"
    )
    sku_vendedor = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="SKU Informado pelo Vendedor (seller_custom_field)"
    )
    thumbnail = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Imagem / Thumbnail"
    )
    permalink = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Link Público do Anúncio"
    )
    data_sincronizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Sincronização"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Anúncio"
        verbose_name_plural = "Anúncios"
        unique_together = ('conta', 'item_id_externo')
        ordering = ['-atualizado_em']

    def __str__(self):
        canal = self.conta.get_canal_display() if self.conta else "Marketplace"
        return f"[{canal}] {self.item_id_externo} — {self.titulo[:40]}"

    @property
    def ultima_sincronizacao(self):
        """Retorna o timestamp da última sincronização do anúncio."""
        return self.data_sincronizacao

    @property
    def eh_kit(self) -> bool:
        """Indica se o anúncio é composto por kit (mais de 1 produto ou multiplicador > 1)."""
        itens = self.itens_composicao.all()
        if itens.count() > 1:
            return True
        primeiro = itens.first()
        return bool(primeiro and primeiro.quantidade > 1)

    def calcular_cota_disponivel(self) -> int:
        """
        O QUE FAZ: Calcula a cota máxima vendável elegível com base no estoque real físico dos produtos vinculados.
        REGRA: cota = min(floor(saldo_disponivel_produto_i / quantidade_item_i)) para todos os produtos da composição.
        Se não possuir itens de composição vinculados, retorna o próprio estoque_publicado atual.
        """
        itens = self.itens_composicao.select_related('produto').all()
        if not itens.exists():
            return max(0, self.estoque_publicado)

        limites = []
        for item in itens:
            produto = item.produto
            saldo_real = getattr(produto, 'saldo_disponivel', produto.estoque)
            if item.quantidade <= 0:
                continue
            limites.append(math.floor(saldo_real / item.quantidade))

        if not limites:
            return 0
        return max(0, min(limites))

    @property
    def cota_calculada(self) -> int:
        """Retorna a cota física máxima calculada para o anúncio."""
        return self.calcular_cota_disponivel()

    def esta_pendente(self, preco_catalogo: Optional[Decimal] = None) -> bool:
        """
        O QUE FAZ: Verifica se o anúncio possui divergência física de cota ou preço em relação ao catálogo.
        """
        if self.status_sincronizacao == 'PENDENTE':
            return True
        cota = self.calcular_cota_disponivel()
        if self.estoque_publicado != cota:
            return True
        if preco_catalogo is not None and not self.eh_kit and self.preco_venda != preco_catalogo:
            return True
        return False


class AnuncioComposicao(models.Model):
    """
    O QUE FAZ: Mapeia os Produtos físicos que compõem o Anúncio (Ficha Técnica / Bill of Materials).
    POR QUE FAZ: Suporta tanto anúncios unitários (1:1 com quantidade=1) quanto Kits (1:N ou quantidade > 1),
                 garantindo que baixas de pedidos debitem as quantidades exatas dos produtos reais.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR.
    MULTI-TENANCY: Produto físico e Anúncio devem pertencer à mesma Loja.
    """
    anuncio = models.ForeignKey(
        Anuncio,
        on_delete=models.CASCADE,
        related_name='itens_composicao',
        related_query_name='composicoes',
        verbose_name="Anúncio"
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='anuncios_vinculados',
        related_query_name='composicoes',
        verbose_name="Produto Físico no Catálogo (Fonte da Verdade)"
    )
    quantidade = models.PositiveIntegerField(
        default=1,
        verbose_name="Quantidade por Embalagem / Multiplicador do Kit"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Composição do Anúncio"
        verbose_name_plural = "Composições do Anúncio"
        unique_together = ('anuncio', 'produto')
        ordering = ['anuncio', 'produto']

    def __str__(self):
        return f"{self.quantidade}x [{self.produto.sku}] {self.produto.nome} no anúncio {self.anuncio.item_id_externo}"

    def clean(self):
        super().clean()
        if self.anuncio_id and self.produto_id:
            loja_anuncio = self.anuncio.conta.loja_id
            loja_produto = self.produto.loja_id
            if loja_anuncio != loja_produto:
                raise ValidationError("O Produto físico e o Anúncio devem pertencer à mesma Loja (Tenant).")


class HistoricoSincronizacaoAnuncio(models.Model):
    """
    O QUE FAZ: Registra a trilha de auditoria do ciclo de sincronização do anúncio.
    POR QUE FAZ: Rastreabilidade de transição de estados [PENDENTE, ENVIADO, CANCELADO],
                 preço/cota propostos vs anteriores e identificação do responsável.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (leitura); gravação automática.
    """
    anuncio = models.ForeignKey(
        Anuncio,
        on_delete=models.CASCADE,
        related_name='historico_ciclo',
        verbose_name="Anúncio"
    )
    status_resultante = models.CharField(
        max_length=20,
        choices=Anuncio.STATUS_SINCRONIZACAO_CHOICES,
        verbose_name="Status Resultante"
    )
    preco_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Anterior (R$)"
    )
    preco_proposto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Proposto / Atualizado (R$)"
    )
    estoque_anterior = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Estoque / Cota Anterior"
    )
    estoque_proposto = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Estoque / Cota Proposta"
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Responsável"
    )
    motivo = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Motivo / Operação"
    )
    data_pendencia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data / Hora da Pendência"
    )
    criado_em = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data / Hora da Decisão / Registro"
    )

    class Meta:
        verbose_name = "Histórico de Ciclo do Anúncio"
        verbose_name_plural = "Históricos de Ciclos dos Anúncios"
        ordering = ['-criado_em']

    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sistema"
        return f"[{self.anuncio.item_id_externo}] -> {self.get_status_resultante_display()} por {user_str}"

