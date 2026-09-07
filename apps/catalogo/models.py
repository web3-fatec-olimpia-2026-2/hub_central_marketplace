# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from apps.tenancy.models import Loja
from apps.marketplaces.models import ContaMarketplace
from apps.marketplaces.enums import StatusSincronizacaoEnum
from .enums import StatusProdutoEnum, TipoAjusteEstoqueEnum


class Categoria(models.Model):
    """
    O QUE FAZ: Categorização de produtos organizada por Loja (Tenant).
    POR QUE FAZ: Organização taxonômica do catálogo mantendo rigoroso isolamento multi-tenant (RN-01).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (CRUD completo); USUARIO (criação e edição descritiva; exclusão bloqueada por RN-09).
    MULTI-TENANCY: FK obrigatória para Loja com unicidade composta ('loja', 'slug').
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='categorias', verbose_name="Loja (Tenant)"
    )
    nome = models.CharField(max_length=100, verbose_name="Nome da Categoria")
    slug = models.SlugField(max_length=120, verbose_name="Identificador (Slug)")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição da Categoria")
    ativo = models.BooleanField(default=True, verbose_name="Categoria Ativa")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        unique_together = [['loja', 'slug']]
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.loja.nome})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nome)
            slug = base_slug
            counter = 1
            while Categoria.objects.filter(loja=self.loja, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Produto(models.Model):
    """
    O QUE FAZ: Entidade central do catálogo e Fonte Única da Verdade (Single Source of Truth) para inventário e preços no Hub.
    POR QUE FAZ: Mantém dados mestres de produtos, custos, estoque e precificação de forma desacoplada de canais externos (RF-03).
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR (acesso total); USUARIO (descritivos e baixa de avaria apenas; alteração de preço e estoque geral bloqueadas por RN-09).
    MULTI-TENANCY: FK para Loja e unicidade composta ('loja', 'sku') (RN-01 / RN-02).
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='produtos', verbose_name="Loja (Tenant)"
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='produtos', verbose_name="Categoria"
    )
    sku = models.CharField(
        max_length=60, verbose_name="Código SKU (Identificador Único na Loja)"
    )
    nome = models.CharField(max_length=200, verbose_name="Nome do Produto")
    descricao = models.TextField(
        blank=True, null=True, verbose_name="Descrição Detalhada do Produto"
    )
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Preço de Venda (R$)"
    )
    estoque = models.IntegerField(
        default=0, verbose_name="Saldo de Estoque Físico"
    )
    status = models.CharField(
        max_length=20, choices=StatusProdutoEnum.choices, default=StatusProdutoEnum.ATIVO,
        verbose_name="Status do Produto"
    )

    # Custos e Inteligência Financeira
    custo_aquisicao = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True,
        verbose_name="Custo de Aquisição / CMV (R$)",
        help_text="Custo de compra ou fabricação unitária do produto."
    )
    custo_embalagem = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True,
        verbose_name="Custo Específico de Embalagem (R$)",
        help_text="Custo de embalagem deste produto. Se 0, herda o padrão da loja."
    )
    modalidade_full = models.BooleanField(
        default=False,
        verbose_name="Modalidade Full / Fulfillment",
        help_text="Se marcado, o custo próprio de embalagem é zerado pois o marketplace assume o envio."
    )

    status_sincronizacao = models.CharField(
        max_length=20, choices=StatusSincronizacaoEnum.choices,
        default=StatusSincronizacaoEnum.NAO_SINCRONIZADO, verbose_name="Status de Sincronização Geral"
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        unique_together = [['loja', 'sku']]
        ordering = ['nome']

    def __str__(self):
        return f"[{self.sku}] {self.nome} — R$ {self.preco} (Estoque: {self.estoque})"

    def clean(self):
        super().clean()
        if self.preco is not None and self.preco < Decimal('0.00'):
            raise ValidationError({'preco': 'O preço de venda não pode ser negativo (RN-06).'})
        if self.categoria_id and self.loja_id:
            if self.categoria.loja_id != self.loja_id:
                raise ValidationError({'categoria': 'A categoria selecionada deve pertencer à mesma loja do produto.'})

    def save(self, *args, **kwargs):
        if self.sku:
            self.sku = self.sku.strip().upper()
        super().save(*args, **kwargs)

    @property
    def status_sincronizacao_consolidado(self) -> str:
        """
        O QUE FAZ: Calcula dinamicamente o estado de sincronização com base em todos os anúncios vinculados ao produto.
        POR QUE FAZ: Elimina divergências entre o card de informações principais e a tabela de anúncios.
        """
        from apps.anuncios.models import Anuncio
        anuncios = list(Anuncio.objects.filter(composicoes__produto=self).distinct())
        if not anuncios:
            return "Sem Anúncios"

        todos_cancelados = all(a.status_sincronizacao == 'CANCELADO' for a in anuncios)
        if todos_cancelados:
            return "Sincronização Descartada"

        tem_pendente = any(
            a.status_sincronizacao == 'PENDENTE' or a.esta_pendente(self.preco)
            for a in anuncios
            if a.status_sincronizacao != 'CANCELADO'
        )
        if tem_pendente:
            return "Pendente de Sincronização"

        todos_enviados = all(
            a.status_sincronizacao == 'ENVIADO' and not a.esta_pendente(self.preco)
            for a in anuncios
            if a.status_sincronizacao != 'CANCELADO'
        )
        if todos_enviados:
            return "Sincronizado com Sucesso"

        return "Pendente de Sincronização"

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



class AnuncioMarketplace(models.Model):
    """
    O QUE FAZ: Mapeia o vínculo de um Produto local a um anúncio publicado em uma ContaMarketplace externa.
    POR QUE FAZ: Desacopla o campo fixo meli_item_id, permitindo que um mesmo SKU seja anunciado simultaneamente no Mercado Livre, Shopee, Magalu e Amazon, com rastreabilidade de preços e IDs externos por canal.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Vinculado ao Produto e à ContaMarketplace da mesma Loja.
    """
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('pausado', 'Pausado'),
        ('finalizado', 'Finalizado'),
        ('pendente', 'Pendente'),
    ]

    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='anuncios', verbose_name="Produto"
    )
    conta_marketplace = models.ForeignKey(
        ContaMarketplace, on_delete=models.CASCADE, related_name='anuncios', verbose_name="Conta do Canal"
    )
    item_id_externo = models.CharField(
        max_length=100, db_index=True, verbose_name="ID Externo no Marketplace (MLB... / Shopee ID / Magalu SKU)"
    )
    status_anuncio = models.CharField(
        max_length=30, default='ativo', choices=STATUS_CHOICES, verbose_name="Status do Anúncio no Canal"
    )
    preco_sincronizado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Último Preço Sincronizado (R$)"
    )
    link_anuncio = models.URLField(
        max_length=500, blank=True, null=True, verbose_name="URL Pública do Anúncio"
    )
    ultima_sincronizacao = models.DateTimeField(
        auto_now=True, verbose_name="Última Sincronização"
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Anúncio no Marketplace"
        verbose_name_plural = "Anúncios nos Marketplaces"
        unique_together = ('produto', 'conta_marketplace')
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.produto.sku} -> [{self.conta_marketplace.get_canal_display()}] {self.item_id_externo}"

    def clean(self):
        super().clean()
        if self.produto_id and self.conta_marketplace_id:
            if self.produto.loja_id != self.conta_marketplace.loja_id:
                raise ValidationError("O produto e a conta de marketplace devem pertencer à mesma loja.")


class HistoricoPreco(models.Model):
    """
    O QUE FAZ: Registro histórico unificado de mutações de preços e estoque (RN-04 / RF-05).
    POR QUE FAZ: Rastreabilidade conjunta de precificação e inventário físico na mesma linha.
    PERMISSÕES RBAC: Consulta por DEV, ADMIN e SUPERVISOR; gravação automática em alterações de preço e estoque.
    MULTI-TENANCY: FK para Loja e Produto da loja.
    """
    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='historico_precos', verbose_name="Produto"
    )
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='historico_precos', verbose_name="Loja (Tenant)"
    )
    preco_anterior = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Preço Anterior (R$)"
    )
    preco_novo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Novo Preço (R$)"
    )
    estoque_anterior = models.IntegerField(
        null=True, blank=True, verbose_name="Estoque Anterior"
    )
    estoque_novo = models.IntegerField(
        null=True, blank=True, verbose_name="Novo Estoque"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='precos_alterados', verbose_name="Usuário Responsável"
    )
    motivo = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Motivo / Operação"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora da Alteração"
    )

    class Meta:
        verbose_name = "Histórico de Alteração de Preço e Estoque"
        verbose_name_plural = "Históricos de Alterações de Preço e Estoque"
        ordering = ['-criado_em']

    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sistema"
        return f"{self.produto.sku}: Preço ({self.preco_anterior} -> {self.preco_novo}) | Estoque ({self.estoque_anterior} -> {self.estoque_novo}) por {user_str}"


HistoricoAlteracao = HistoricoPreco
