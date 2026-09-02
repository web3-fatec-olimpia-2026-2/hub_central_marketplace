# Os códigos foram gerados com auxilio de I.A.
from django.db import models
from django.contrib.auth.models import User

from apps.tenancy.models import Loja
from .enums import CanalMarketplaceEnum, EventoAuditoriaEnum, StatusSincronizacaoEnum


class ContaMarketplace(models.Model):
    """
    O QUE FAZ: Representa a conexão e credenciais de uma conta de Marketplace vinculada a uma Loja (Tenant).
    POR QUE FAZ: Desacopla a integração de canais específicos (ex: campos fixos do Mercado Livre em Loja), viabilizando arquitetura multicanal e múltiplas contas por loja (ex: duas contas Mercado Livre ou contas em Mercado Livre, Shopee, Magalu e Amazon).
    PERMISSÕES RBAC: DEV (qualquer loja); ADMIN (sua própria loja); SUPERVISOR e USUARIO não gerenciam credenciais.
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

    # Credenciais de Integração OAuth / API
    client_id = models.CharField(
        max_length=150, blank=True, null=True, verbose_name="Client ID / App ID"
    )
    client_secret = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Client Secret / Chave Secreta"
    )
    access_token = models.TextField(
        blank=True, null=True, verbose_name="Access Token"
    )
    refresh_token = models.TextField(
        blank=True, null=True, verbose_name="Refresh Token"
    )
    token_expira_em = models.DateTimeField(
        blank=True, null=True, verbose_name="Token Expira Em"
    )
    seller_id_externo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Seller ID Externo / User ID"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Conectado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Conta de Marketplace"
        verbose_name_plural = "Contas de Marketplaces"
        unique_together = ('loja', 'canal', 'seller_id_externo')
        ordering = ['loja', 'canal', 'apelido_conta']

    def __str__(self):
        return f"[{self.get_canal_display()}] {self.apelido_conta} — {self.loja.nome}"

    @property
    def has_credentials(self) -> bool:
        """Verifica se possui credenciais mínimas configuradas."""
        return bool(self.access_token or (self.client_id and self.client_secret))


# Alias de modelo conforme especificação
ConfiguracaoCanal = ContaMarketplace


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
