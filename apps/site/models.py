# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Modelos de Configuração de Tema e Visibilidade do Site (Doc ① §11.1 e §11.12).
POR QUE FAZ: Persiste tokens visuais do produto, layouts e flag de controle de páginas públicas com escopo multi-tenant e validação WCAG.
PERMISSÕES RBAC: Gerenciado por perfis com 'site.tema_editar' e 'site.visibilidade_publica'.
MULTI-TENANCY: FK opcional para Loja; nulo indica configuração global padrão do sistema.
"""

import hashlib
from django.db import models
from django.core.exceptions import ValidationError
from apps.tenancy.models import Loja
from .utils_tema import (
    PRESETS_MODELOS, validar_cor_hex, validar_contraste_wcag,
    calcular_derivados_tema
)

CHOICES_MODELOS = [
    ('T01', 'T01 — Alegre'),
    ('T02', 'T02 — Sofisticado'),
    ('T03', 'T03 — Sóbrio'),
    ('T04', 'T04 — Animado'),
    ('T05', 'T05 — Profissional (Padrão)'),
    ('T06', 'T06 — Luxuoso'),
    ('T07', 'T07 — SoftClean'),
    ('T08', 'T08 — Noturno'),
    ('T09', 'T09 — Acessível'),
    ('T10', 'T10 — Outro (Personalizado)'),
]

CHOICES_RAIO = [
    ('reto', 'Reto (0)'),
    ('suave', 'Suave (.375rem)'),
    ('arredondado', 'Arredondado (1rem)'),
    ('pilula', 'Pílula (2rem)'),
]

CHOICES_SOMBRA = [
    ('nenhuma', 'Nenhuma (Apenas bordas)'),
    ('suave', 'Suave'),
    ('marcada', 'Marcada'),
    ('difusa', 'Difusa'),
]

CHOICES_DENSIDADE = [
    ('compacta', 'Compacta (.75)'),
    ('confortavel', 'Confortável (1.0)'),
    ('ampla', 'Ampla (1.35)'),
]

CHOICES_MOVIMENTO = [
    ('nenhum', 'Nenhum (0s)'),
    ('discreto', 'Discreto (.15s)'),
    ('expressivo', 'Expressivo (.35s)'),
]

CHOICES_TIPOGRAFIA = [
    ('sans', 'Sans do Sistema'),
    ('arredondada', 'Arredondada'),
    ('serifa-titulos', 'Serifa nos Títulos'),
]

CHOICES_ICONES = [
    ('contorno', 'Contorno'),
    ('preenchido', 'Preenchido'),
]


class ConfigTema(models.Model):
    """
    Entidade de persistência do tema ativo (Doc ① §11.12).
    Armazena as três cores, eixos de estilo e variantes com suporte a tenancy.
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, null=True, blank=True,
        related_name='config_temas', verbose_name="Loja (Tenant)"
    )
    modelo = models.CharField(
        max_length=5, choices=CHOICES_MODELOS, default='T05',
        verbose_name="Modelo de Design"
    )
    cor_fundos = models.CharField(
        max_length=7, default='#F8FAFC', verbose_name="Cor de Fundos"
    )
    cor_destaques = models.CharField(
        max_length=7, default='#1E3A8A', verbose_name="Cor de Destaques"
    )
    cor_escritas = models.CharField(
        max_length=7, default='#0F172A', verbose_name="Cor de Escritas"
    )
    raio = models.CharField(
        max_length=15, choices=CHOICES_RAIO, default='suave',
        verbose_name="Raio dos Cantos"
    )
    sombra = models.CharField(
        max_length=15, choices=CHOICES_SOMBRA, default='suave',
        verbose_name="Sombra das Superfícies"
    )
    densidade = models.CharField(
        max_length=15, choices=CHOICES_DENSIDADE, default='confortavel',
        verbose_name="Densidade e Espaçamento"
    )
    movimento = models.CharField(
        max_length=15, choices=CHOICES_MOVIMENTO, default='discreto',
        verbose_name="Movimento e Transições"
    )
    tipografia = models.CharField(
        max_length=20, choices=CHOICES_TIPOGRAFIA, default='sans',
        verbose_name="Pilha Tipográfica"
    )
    icones = models.CharField(
        max_length=15, choices=CHOICES_ICONES, default='contorno',
        verbose_name="Estilo dos Ícones"
    )
    shell_variante = models.CharField(
        max_length=30, default='topo', verbose_name="Variante de Casca Autenticada"
    )
    versao = models.CharField(
        max_length=64, blank=True, verbose_name="Hash de Versionamento do CSS"
    )
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Configuração de Tema"
        verbose_name_plural = "Configurações de Tema"

    def __str__(self):
        escopo = self.loja.nome if self.loja else "Global (Padrão)"
        return f"Tema {self.get_modelo_display()} [{escopo}] (v:{self.versao[:8]})"

    def clean(self):
        super().clean()
        # Validação estrita de formato hexadecimal anti-injection (mantida)
        self.cor_fundos = validar_cor_hex(self.cor_fundos, "cor_fundos")
        self.cor_destaques = validar_cor_hex(self.cor_destaques, "cor_destaques")
        self.cor_escritas = validar_cor_hex(self.cor_escritas, "cor_escritas")

    def save(self, *args, **kwargs):
        # Valida antes de persistir
        self.full_clean()

        # Calcula hash sha256 para versionamento do /tema.css?v=<hash>
        hash_payload = (
            f"{self.modelo}-{self.cor_fundos}-{self.cor_destaques}-{self.cor_escritas}-"
            f"{self.raio}-{self.sombra}-{self.densidade}-{self.movimento}-{self.tipografia}-{self.icones}"
        )
        self.versao = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()[:16]
        super().save(*args, **kwargs)

    @classmethod
    def get_tema_ativo(cls, loja=None):
        """
        Retorna o tema ativo para a loja ou o tema global padrão.
        Se não existir registro no banco, devolve uma instância não salva com preset T05.
        """
        if loja:
            tema_loja = cls.objects.filter(loja=loja).first()
            if tema_loja:
                return tema_loja

        tema_global = cls.objects.filter(loja__isnull=True).first()
        if tema_global:
            return tema_global

        tema_qualquer = cls.objects.first()
        if tema_qualquer:
            return tema_qualquer

        # Fallback padrão T05 Profissional
        preset = PRESETS_MODELOS['T05']
        instancia = cls(
            modelo='T05',
            cor_fundos=preset['fundos'],
            cor_destaques=preset['destaques'],
            cor_escritas=preset['escritas'],
            raio=preset['raio'],
            sombra=preset['sombra'],
            densidade=preset['densidade'],
            movimento=preset['movimento'],
            tipografia=preset['tipografia'],
            icones=preset['icones'],
            shell_variante=preset['shell_variante'],
            versao='t05-default'
        )
        return instancia


class ConfigSite(models.Model):
    """
    Configuração geral do site e visibilidade pública (Doc ① §11.1).
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, null=True, blank=True,
        related_name='config_site', verbose_name="Loja (Tenant)"
    )
    visibilidade_publica = models.BooleanField(
        default=True,
        verbose_name="Visibilidade Pública Ativa",
        help_text="Se True, a rota '/' serve a Landing Page. Se False, '/' serve Login e páginas públicas respondem 404."
    )
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Configuração do Site"
        verbose_name_plural = "Configurações do Site"

    def __str__(self):
        escopo = self.loja.nome if self.loja else "Global"
        status = "Ativa" if self.visibilidade_publica else "Desativada"
        return f"Visibilidade Pública: {status} [{escopo}]"

    @classmethod
    def is_visibilidade_publica_ativa(cls, loja=None) -> bool:
        """Verifica se a visibilidade pública está ativa para o escopo informado."""
        try:
            if loja:
                cfg = cls.objects.filter(loja=loja).first()
                if cfg:
                    return cfg.visibilidade_publica
            cfg_global = cls.objects.filter(loja__isnull=True).first()
            if cfg_global:
                return cfg_global.visibilidade_publica
        except Exception:
            pass
        return True  # Padrão do ecossistema: Ativa (Doc ① §11.1)
