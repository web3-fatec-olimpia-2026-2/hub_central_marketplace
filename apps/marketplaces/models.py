# Os códigos foram gerados com auxilio de I.A.
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.tenancy.models import Loja
from .enums import CanalMarketplaceEnum, EventoAuditoriaEnum, StatusSincronizacaoEnum, WebhookStatusEnum
from apps.core.security import EncryptedTextField


class ContaMarketplace(models.Model):
    """
    O QUE FAZ: Representa a conexão e credenciais de uma conta de Marketplace vinculada a uma Loja (Tenant).
    POR QUE FAZ: Desacopla a integração de canais específicos, viabilizando arquitetura multicanal com persistência criptografada de tokens OAuth.
    PERMISSÕES RBAC: DEV (qualquer loja); ADMIN (sua própria loja); SUPERVISOR e USUARIO não gerenciam conexões.
    MULTI-TENANCY: FK obrigatória para Loja e restrição de unicidade ('loja', 'canal', 'seller_id_externo').
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='contas_marketplace', verbose_name="Loja (Tenant)"
    )
    canal = models.CharField(
        max_length=30, choices=CanalMarketplaceEnum.choices, verbose_name="Canal de Marketplace"
    )
    apelido_conta = models.CharField(
        max_length=100, verbose_name="Apelido da Conta",
        help_text="Identificador amigável (Ex: Loja Principal ML, Shopee Filial)"
    )
    ativo = models.BooleanField(
        default=True, verbose_name="Integração Ativa"
    )
    is_mock = models.BooleanField(
        default=False, verbose_name="Conta Simulada / Mock",
        help_text="Indica se a conta pertence ao conjunto de lojas e dados fictícios de teste."
    )

    TIPO_APLICACAO_CHOICES = [
        ('GLOBAL', 'Aplicação Global do Hub (Centralizada)'),
        ('INDIVIDUAL', 'Aplicação Própria do Tenant (Individual)'),
    ]

    # Estratégia de Aplicação (Híbrida: Global vs Individual)
    tipo_aplicacao = models.CharField(
        max_length=20,
        choices=TIPO_APLICACAO_CHOICES,
        default='GLOBAL',
        verbose_name="Tipo de Aplicação",
        help_text="Define se utiliza credenciais compartilhadas do Hub ou chaves próprias do lojista."
    )

    # Identificador Público de Roteamento para Webhook Individual (Segmentação na Origem)
    webhook_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name="UUID do Webhook"
    )

    # Credenciais do Desenvolvedor (Modo Individual)
    app_key_or_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="App ID / Partner ID / Client ID",
        help_text="Identificador público da aplicação: Client ID / Partner ID"
    )
    app_secret = EncryptedTextField(
        blank=True,
        null=True,
        verbose_name="App Secret / Client Secret / Partner Key",
        help_text="Chave secreta da aplicação (criptografada em repouso via Fernet)."
    )
    webhook_secret = EncryptedTextField(
        blank=True,
        null=True,
        verbose_name="Webhook Secret",
        help_text="Chave secreta para validação de assinatura HMAC dos webhooks."
    )

    # Credenciais de Integração OAuth / API (Criptografadas em Repouso via Fernet)
    access_token = EncryptedTextField(
        blank=True, null=True, verbose_name="Access Token"
    )
    refresh_token = EncryptedTextField(
        blank=True, null=True, verbose_name="Refresh Token"
    )
    token_expira_em = models.DateTimeField(
        blank=True, null=True, verbose_name="Token Expira Em"
    )
    ultima_sincronizacao = models.DateTimeField(
        blank=True, null=True, verbose_name="Última Sincronização"
    )
    seller_id_externo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Seller ID Externo / User ID"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Conectado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Conta de Marketplace"
        verbose_name_plural = "Contas de Marketplaces"
        constraints = [
            models.UniqueConstraint(
                fields=['loja', 'canal'],
                name='unique_conta_loja_canal'
            ),
            models.UniqueConstraint(
                fields=['loja', 'apelido_conta'],
                name='unique_conta_loja_apelido'
            ),
            models.UniqueConstraint(
                fields=['canal', 'seller_id_externo'],
                condition=models.Q(seller_id_externo__isnull=False) & ~models.Q(seller_id_externo=''),
                name='unique_conta_canal_seller_id'
            ),
        ]
        ordering = ['loja', 'canal', 'apelido_conta']

    def __str__(self):
        return f"[{self.get_canal_display()}] {self.apelido_conta} — {self.loja.nome}"

    def clean(self):
        super().clean()

        # 1. Imutabilidade na edição: canal e loja não podem ser alterados
        if self.pk:
            original = ContaMarketplace.objects.filter(pk=self.pk).only('loja_id', 'canal').first()
            if original:
                if original.loja_id != self.loja_id:
                    raise ValidationError({'loja': "A loja (tenant) vinculada é imutável após a conexão."})
                if original.canal != self.canal:
                    raise ValidationError({'canal': "O canal de marketplace é imutável após a conexão."})

        # 2. Trava Loja + Canal (apenas 1 conexão ativa por canal por loja)
        if self.loja_id and self.canal:
            qs = ContaMarketplace.objects.filter(loja_id=self.loja_id, canal=self.canal)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'canal': f"A loja selecionada já possui uma conexão para o canal {self.get_canal_display()}."
                })

        # 3. Trava Canal + Seller ID Externo (não pode ser reaproveitado por outra loja)
        if self.canal and self.seller_id_externo:
            qs = ContaMarketplace.objects.filter(canal=self.canal, seller_id_externo=self.seller_id_externo)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'seller_id_externo': f"O Seller ID Externo '{self.seller_id_externo}' já está em uso por outra conta no canal {self.get_canal_display()}."
                })

        # 4. Trava Loja + Apelido da Conta (único dentro da loja)
        if self.loja_id and self.apelido_conta:
            qs = ContaMarketplace.objects.filter(loja_id=self.loja_id, apelido_conta=self.apelido_conta)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'apelido_conta': f"Já existe uma conta com o apelido '{self.apelido_conta}' cadastrada para esta loja."
                })

    def save(self, *args, **kwargs):
        """Valida imutabilidade e identifica automaticamente contas pertencentes às lojas mockadas."""
        if self.pk:
            original = ContaMarketplace.objects.filter(pk=self.pk).only('loja_id', 'canal').first()
            if original:
                if original.loja_id != self.loja_id:
                    raise ValidationError({'loja': "A loja (tenant) vinculada é imutável após a conexão."})
                if original.canal != self.canal:
                    raise ValidationError({'canal': "O canal de marketplace é imutável após a conexão."})

        if self.loja and getattr(self.loja, 'slug', None) in ['techzone-mock', 'comfort-mock', 'passofirme-mock']:
            self.is_mock = True
        super().save(*args, **kwargs)

    @property
    def seller_id_remoto(self):
        return self.seller_id_externo

    @seller_id_remoto.setter
    def seller_id_remoto(self, value):
        self.seller_id_externo = value

    @property
    def has_credentials(self) -> bool:
        """Verifica se a conta possui Access Token configurado."""
        return bool(self.access_token)

    def get_connector(self):
        """
        O QUE FAZ: Instancia e retorna o conector adequado para a conta de marketplace (Strategy / Adapter Pattern).
        POR QUE FAZ: Ponto único de despacho desacoplado do conector específico de canal (Mercado Livre, Shopee, etc.).
        """
        from .connectors.factory import get_connector_for_conta
        return get_connector_for_conta(self)


# Alias de modelo conforme especificação
ConfiguracaoCanal = ContaMarketplace
MarketplaceConta = ContaMarketplace


class LogSincronizacao(models.Model):
    """
    O QUE FAZ: Registro detalhado de telemetria, chamadas de API e respostas de comunicação com marketplaces externos.
    POR QUE FAZ: Diagnóstico de integrações, auditoria técnica e rastreabilidade de falhas (RF-05 / RN-04).
    PERMISSÕES RBAC: DEV e ADMIN (leitura); gravação automática pelo sistema.
    MULTI-TENANCY: FK obrigatória para Loja com isolamento horizontal por tenant.
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='logs_sincronizacao', verbose_name="Loja (Tenant)"
    )
    conta_marketplace = models.ForeignKey(
        ContaMarketplace, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs', verbose_name="Conta de Origem"
    )
    canal = models.CharField(
        max_length=30, choices=CanalMarketplaceEnum.choices, default=CanalMarketplaceEnum.MERCADOLIVRE,
        verbose_name="Canal de Marketplace"
    )
    evento = models.CharField(
        max_length=50, choices=EventoAuditoriaEnum.choices, verbose_name="Tipo de Operação / Evento"
    )
    item_id_externo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="ID Externo no Marketplace"
    )
    payload_enviado = models.JSONField(
        default=dict, blank=True, verbose_name="Payload Enviado (JSON)"
    )
    resposta_recebida = models.JSONField(
        default=dict, blank=True, verbose_name="Resposta Recebida da API (JSON)"
    )
    status_http = models.IntegerField(
        null=True, blank=True, verbose_name="Status HTTP"
    )
    sucesso = models.BooleanField(
        default=False, verbose_name="Operação Bem-Sucedida"
    )
    mensagem_erro = models.TextField(
        blank=True, null=True, verbose_name="Mensagem de Erro / Diagnóstico"
    )
    tempo_resposta_ms = models.IntegerField(
        null=True, blank=True, verbose_name="Tempo de Resposta (ms)"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora do Disparo"
    )

    class Meta:
        verbose_name = "Log de Sincronização"
        verbose_name_plural = "Logs de Sincronização"
        ordering = ['-criado_em']

    def __str__(self):
        status_txt = "Sucesso" if self.sucesso else "Falha"
        return f"[{self.get_canal_display()}] {self.get_evento_display()} ({status_txt}, HTTP {self.status_http}) em {self.criado_em.strftime('%d/%m/%Y %H:%M:%S')}"


class LogAuditoria(models.Model):
    """
    O QUE FAZ: Registro de auditoria de mutações críticas (RBAC, tenants, alterações manuais de catálogo e estoque).
    POR QUE FAZ: Rastreabilidade e conformidade com RN-04 (Fonte única da verdade e auditoria).
    PERMISSÕES RBAC: DEV (global); ADMIN e SUPERVISOR (leitura da loja); gravação automática pelo sistema.
    MULTI-TENANCY: FK para Loja com isolamento por inquilino.
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_auditoria', verbose_name="Loja (Tenant)"
    )
    autor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_realizados', verbose_name="Autor da Ação"
    )
    usuario_afetado = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_recebidos', verbose_name="Usuário Afetado"
    )
    evento = models.CharField(
        max_length=50, choices=EventoAuditoriaEnum.choices, verbose_name="Evento"
    )
    detalhes = models.TextField(
        verbose_name="Detalhes da Ação / Histórico de Alterações"
    )
    ip_origem = models.CharField(
        max_length=45, blank=True, null=True, verbose_name="IP de Origem"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora do Evento"
    )

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ['-criado_em']

    def __str__(self):
        autor_str = self.autor.username if self.autor else "Sistema"
        return f"[{self.get_evento_display()}] por {autor_str} em {self.criado_em.strftime('%d/%m/%Y %H:%M')}"


class WebhookEventLog(models.Model):
    """
    O QUE FAZ: Registro de eventos de Webhook com controle estrito de idempotência e auditoria de ciclo de vida.
    POR QUE FAZ: Impede deduplicações de baixa de estoque caso o marketplace reenvie a mesma notificação (retentativas de rede, atualizações intermediárias de pedidos).
    PERMISSÕES RBAC: DEV e ADMIN (consulta); gravação automatizada pelo webhook.
    """
    marketplace = models.CharField(
        max_length=50, default="mercadolivre", verbose_name="Marketplace de Origem"
    )
    topic = models.CharField(
        max_length=50, verbose_name="Tópico da Notificação (ex: orders_v2, items)"
    )
    resource = models.CharField(
        max_length=255, db_index=True, verbose_name="Recurso Notificado (ex: /orders/2000001234567890)"
    )
    user_id = models.CharField(
        max_length=50, verbose_name="ID do Usuário / Vendedor no Canal"
    )
    payload_raw = models.JSONField(
        default=dict, verbose_name="Payload Bruto da Notificação"
    )
    status = models.CharField(
        max_length=20,
        choices=WebhookStatusEnum.choices,
        default=WebhookStatusEnum.RECEBIDO,
        db_index=True,
        verbose_name="Status de Processamento"
    )
    error_log = models.TextField(
        null=True, blank=True, verbose_name="Log de Erro / Justificativa"
    )
    received_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Recebido em"
    )
    processed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Processado em"
    )

    class Meta:
        verbose_name = "Log de Evento de Webhook"
        verbose_name_plural = "Logs de Eventos de Webhooks"
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['marketplace', 'resource', 'status'], name='idx_wh_mkt_res_status'),
            models.Index(fields=['resource', 'status'], name='idx_wh_res_status'),
            models.Index(fields=['received_at'], name='idx_wh_received_at'),
        ]

    def __str__(self):
        return f"[{self.marketplace}] {self.topic} {self.resource} ({self.get_status_display()}) em {self.received_at.strftime('%d/%m/%Y %H:%M:%S')}"
