# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Modelo de dados para persistência da Matriz RBAC (Funcionalidade x Papel/Perfil).
POR QUE FAZ: Conforme especificado em AGENT_INSTRUCTIONS_DJANGO.md (§17.4 e §17.5) e PROJECT_SPEC.md (§5 e §6),
             a Matriz de Permissões deve ser gerenciada como dado persistido e auditável.
PERMISSÕES RBAC: Exclusivo Grupos 3 (Administrador) e 4 (Desenvolvedor).
MULTI-TENANCY: Matriz com escopo global por padrão (§17.6).
"""

from django.db import models


class RegraRBAC(models.Model):
    """
    O QUE FAZ: Representa uma entrada na matriz de autorização RBAC, mapeando um código funcional a um papel.
    POR QUE FAZ: Transforma a matriz em dado dinâmico, permitindo alternância via switches (toggles) com persistência em banco.
    """
    funcionalidade = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="Código da Funcionalidade"
    )
    papel = models.CharField(
        max_length=20,
        db_index=True,
        verbose_name="Papel de Acesso"
    )
    concedido = models.BooleanField(
        default=False,
        verbose_name="Permissão Concedida"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Atualização"
    )

    class Meta:
        verbose_name = "Regra de Permissão RBAC"
        verbose_name_plural = "Regras de Permissão RBAC"
        unique_together = ('funcionalidade', 'papel')
        ordering = ['funcionalidade', 'papel']

    def __str__(self):
        status = "Concedido" if self.concedido else "Negado"
        return f"[{self.papel}] {self.funcionalidade}: {status}"
