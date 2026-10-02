# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Módulo utilitário para cálculo de luminância, contraste WCAG 2.1, presets de temas e geração determinística de CSS (Doc ① §11.6 a §11.12).
POR QUE FAZ: Garante acessibilidade visual estrita, previne injeção de CSS arbitrário e encapsula regras de design tokens.
PERMISSÕES RBAC: Utilizado por rotinas de configuração de tema e geração de CSS.
MULTI-TENANCY: Agnóstico a tenancy; opera sobre tuplas de valores.
"""

import re
import hashlib
from typing import Tuple, Dict, Any
from django.core.exceptions import ValidationError

HEX_COLOR_REGEX = re.compile(r'^#[0-9A-Fa-f]{6}$')

# Modelos canônicos de design (Doc ① §11.6)
PRESETS_MODELOS: Dict[str, Dict[str, Any]] = {
    'T01': {
        'nome': 'Alegre',
        'slug': 'alegre',
        'fundos': '#FFFBF0',
        'destaques': '#E4572E',
        'escritas': '#2B2118',
        'raio': 'arredondado',
        'sombra': 'suave',
        'densidade': 'confortavel',
        'movimento': 'discreto',
        'tipografia': 'arredondada',
        'icones': 'preenchido',
        'shell_variante': 'topo',
    },
    'T02': {
        'nome': 'Sofisticado',
        'slug': 'sofisticado',
        'fundos': '#F5F1EA',
        'destaques': '#7B2D3B',
        'escritas': '#1F1B16',
        'raio': 'suave',
        'sombra': 'nenhuma',
        'densidade': 'confortavel',
        'movimento': 'discreto',
        'tipografia': 'serifa-titulos',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
    'T03': {
        'nome': 'Sóbrio',
        'slug': 'sobrio',
        'fundos': '#F1F5F9',
        'destaques': '#334155',
        'escritas': '#0F172A',
        'raio': 'reto',
        'sombra': 'nenhuma',
        'densidade': 'compacta',
        'movimento': 'nenhum',
        'tipografia': 'sans',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
    'T04': {
        'nome': 'Animado',
        'slug': 'animado',
        'fundos': '#FAF5FF',
        'destaques': '#7E22CE',
        'escritas': '#1E1B4B',
        'raio': 'arredondado',
        'sombra': 'marcada',
        'densidade': 'confortavel',
        'movimento': 'expressivo',
        'tipografia': 'arredondada',
        'icones': 'preenchido',
        'shell_variante': 'topo',
    },
    'T05': {
        'nome': 'Profissional',
        'slug': 'profissional',
        'fundos': '#F8FAFC',
        'destaques': '#1E3A8A',
        'escritas': '#0F172A',
        'raio': 'suave',
        'sombra': 'suave',
        'densidade': 'confortavel',
        'movimento': 'discreto',
        'tipografia': 'sans',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
    'T06': {
        'nome': 'Luxuoso',
        'slug': 'luxuoso',
        'fundos': '#16120F',
        'destaques': '#D4AF37',
        'escritas': '#F6EEDC',
        'raio': 'reto',
        'sombra': 'nenhuma',
        'densidade': 'ampla',
        'movimento': 'discreto',
        'tipografia': 'serifa-titulos',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
    'T07': {
        'nome': 'SoftClean',
        'slug': 'softclean',
        'fundos': '#FBFBFD',
        'destaques': '#4A76A8',
        'escritas': '#334155',
        'raio': 'arredondado',
        'sombra': 'difusa',
        'densidade': 'ampla',
        'movimento': 'discreto',
        'tipografia': 'sans',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
    'T08': {
        'nome': 'Noturno',
        'slug': 'noturno',
        'fundos': '#12141A',
        'destaques': '#4FA3FF',
        'escritas': '#E6E8EE',
        'raio': 'suave',
        'sombra': 'suave',
        'densidade': 'confortavel',
        'movimento': 'discreto',
        'tipografia': 'sans',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
    'T09': {
        'nome': 'Acessível',
        'slug': 'acessivel',
        'fundos': '#FFFFFF',
        'destaques': '#0B3D91',
        'escritas': '#000000',
        'raio': 'suave',
        'sombra': 'nenhuma',
        'densidade': 'ampla',
        'movimento': 'nenhum',
        'tipografia': 'sans',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
    'T10': {
        'nome': 'Outro',
        'slug': 'outro',
        'fundos': '#F8FAFC',
        'destaques': '#1E3A8A',
        'escritas': '#0F172A',
        'raio': 'suave',
        'sombra': 'suave',
        'densidade': 'confortavel',
        'movimento': 'discreto',
        'tipografia': 'sans',
        'icones': 'contorno',
        'shell_variante': 'topo',
    },
}


def validar_cor_hex(cor: str, nome_campo: str = "Cor") -> str:
    """Valida se uma string é um hexadecimal estrito no formato #RRGGBB."""
    if not cor or not isinstance(cor, str):
        raise ValidationError({nome_campo: f"{nome_campo} deve ser uma string no formato hexadecimal #RRGGBB."})
    cor = cor.strip()
    if not HEX_COLOR_REGEX.match(cor):
        raise ValidationError({nome_campo: f"{nome_campo} '{cor}' é inválido. Utilize o formato estrito #RRGGBB."})
    return cor.upper()


def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Converte hexadecimal #RRGGBB para tupla (r, g, b) em inteiros 0..255."""
    clean_hex = hex_code.lstrip('#')
    return int(clean_hex[0:2], 16), int(clean_hex[2:4], 16), int(clean_hex[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Converte tupla (r, g, b) para string hexadecimal #RRGGBB em maiúsculas."""
    r_c = max(0, min(255, int(round(r))))
    g_c = max(0, min(255, int(round(g))))
    b_c = max(0, min(255, int(round(b))))
    return f"#{r_c:02X}{g_c:02X}{b_c:02X}"


def calcular_luminancia_relativa(hex_code: str) -> float:
    """
    Calcula a luminância relativa conforme a fórmula WCAG 2.1:
    L = 0.2126 * R + 0.7152 * G + 0.0722 * B
    """
    r, g, b = hex_to_rgb(hex_code)
    def canal_linear(val: int) -> float:
        s = val / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r_lin = canal_linear(r)
    g_lin = canal_linear(g)
    b_lin = canal_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calcular_razao_contraste(hex1: str, hex2: str) -> float:
    """
    Calcula a razão de contraste WCAG 2.1 entre duas cores hexadecimais:
    Ratio = (L1 + 0.05) / (L2 + 0.05), onde L1 é a mais clara.
    """
    lum1 = calcular_luminancia_relativa(hex1)
    lum2 = calcular_luminancia_relativa(hex2)
    l_max = max(lum1, lum2)
    l_min = min(lum1, lum2)
    return round((l_max + 0.05) / (l_min + 0.05), 2)


def calcular_texto_sobre_destaque(hex_destaque: str) -> Tuple[str, str, float]:
    """
    Calcula se o texto sobre a cor de destaque deve ser Branco (#FFFFFF) ou Preto (#000000).
    Retorna tupla: (cor_texto, navbar_bs_theme, ratio)
    onde navbar_bs_theme é 'dark' se o texto for branco (navbar de fundo escuro com letras claras)
    e 'light' se o texto for preto.
    """
    ratio_branco = calcular_razao_contraste('#FFFFFF', hex_destaque)
    ratio_preto = calcular_razao_contraste('#000000', hex_destaque)

    if ratio_branco >= ratio_preto:
        return '#FFFFFF', 'dark', ratio_branco
    return '#000000', 'light', ratio_preto


def calcular_derivados_tema(cor_fundos: str, cor_destaques: str, cor_escritas: str) -> Dict[str, Any]:
    """
    Calcula derivados semânticos no servidor de forma determinística (Doc ① §11.7):
    - Superfície
    - Borda
    - Texto atenuado / suave
    - Destaque hover
    - Texto sobre destaque
    - bs_theme ('light' ou 'dark')
    - navbar_bs ('light' ou 'dark')
    """
    lum_fundo = calcular_luminancia_relativa(cor_fundos)
    bs_theme = 'dark' if lum_fundo < 0.2 else 'light'

    r_f, g_f, b_f = hex_to_rgb(cor_fundos)
    r_d, g_d, b_d = hex_to_rgb(cor_destaques)
    r_e, g_e, b_e = hex_to_rgb(cor_escritas)

    # Destaque hover: escurece ou clareia levemente o destaque
    if bs_theme == 'dark':
        # Clareia 15%
        d_hover = rgb_to_hex(r_d * 1.15, g_d * 1.15, b_d * 1.15)
    else:
        # Escurece 15%
        d_hover = rgb_to_hex(r_d * 0.85, g_d * 0.85, b_d * 0.85)

    # Superfície
    if bs_theme == 'dark':
        superficie = rgb_to_hex(r_f + 16, g_f + 16, b_f + 16)
        borda = rgb_to_hex(r_f + 36, g_f + 36, b_f + 36)
        escrita_suave = rgb_to_hex(r_e * 0.75, g_e * 0.75, b_e * 0.75)
    else:
        superficie = '#FFFFFF'
        borda = rgb_to_hex(r_f * 0.9, g_f * 0.9, b_f * 0.9)
        escrita_suave = rgb_to_hex((r_e + r_f) / 2, (g_e + g_f) / 2, (b_e + b_f) / 2)

    texto_sobre_destaque, navbar_bs, _ = calcular_texto_sobre_destaque(cor_destaques)

    return {
        'bs_theme': bs_theme,
        'navbar_bs': navbar_bs,
        'superficie': superficie,
        'borda': borda,
        'escrita_suave': escrita_suave,
        'destaque_hover': d_hover,
        'sobre_destaque': texto_sobre_destaque,
        'destaque_rgb': f"{r_d}, {g_d}, {b_d}",
    }


def validar_contraste_wcag(cor_fundos: str, cor_destaques: str, cor_escritas: str, modelo: str = 'T05') -> Dict[str, Any]:
    """
    Avalia a razão de contraste WCAG 2.1 de forma consultiva e pragmática (sem bloqueio de ValidationError).
    Permite total liberdade na identidade visual do produto.
    """
    ratio_escritas = calcular_razao_contraste(cor_escritas, cor_fundos)
    ratio_destaques = calcular_razao_contraste(cor_destaques, cor_fundos)

    min_escritas = 7.0 if modelo == 'T09' else 4.5
    min_destaques = 4.5 if modelo == 'T09' else 3.0

    return {
        'valido': (ratio_escritas >= min_escritas) and (ratio_destaques >= min_destaques),
        'ratio_escritas': ratio_escritas,
        'ratio_destaques': ratio_destaques,
        'min_escritas': min_escritas,
        'min_destaques': min_destaques,
    }


def gerar_css_tema(
    cor_fundos: str,
    cor_destaques: str,
    cor_escritas: str,
) -> str:
    """
    Gera o CSS público determinístico para a rota /tema.css (Doc ① §11.12 item 6).
    Apenas interpola valores validados e sanitizados.
    Garante inversão de cores para Modo Claro e Modo Escuro (data-bs-theme).
    """
    f = validar_cor_hex(cor_fundos, "cor_fundos")
    d = validar_cor_hex(cor_destaques, "cor_destaques")
    e = validar_cor_hex(cor_escritas, "cor_escritas")

    derivados = calcular_derivados_tema(f, d, e)
    lum_f = calcular_luminancia_relativa(f)

    # Modo Claro
    if lum_f < 0.2:
        claro_fundo = '#F8FAFC'
        claro_superficie = '#FFFFFF'
        claro_borda = '#E2E8F0'
        claro_escrita = '#0F172A'
        claro_escrita_suave = '#475569'
    else:
        claro_fundo = f
        claro_superficie = derivados['superficie']
        claro_borda = derivados['borda']
        claro_escrita = e
        claro_escrita_suave = derivados['escrita_suave']

    # Modo Escuro: Inversão estrutural
    if lum_f < 0.2:
        escuro_fundo = f
        escuro_superficie = derivados['superficie']
        escuro_borda = derivados['borda']
        escuro_escrita = e
        escuro_escrita_suave = derivados['escrita_suave']
    else:
        escuro_fundo = '#12141A'
        escuro_superficie = '#1E222B'
        escuro_borda = '#2D323F'
        escuro_escrita = '#FFFFFF'
        escuro_escrita_suave = '#94A3B8'

    r_d, g_d, b_d = hex_to_rgb(d)
    destaque_rgb = f"{r_d}, {g_d}, {b_d}"
    texto_sobre_destaque, _, _ = calcular_texto_sobre_destaque(d)

    css = f"""/* Tema Dinâmico do Hub Central de Marketplaces (Doc ① §11.5) */
:root,
[data-bs-theme="light"] {{
  --tema-fundo: {claro_fundo};
  --tema-destaque: {d};
  --tema-escrita: {claro_escrita};
  --tema-destaque-rgb: {destaque_rgb};
  --tema-superficie: {claro_superficie};
  --tema-borda: {claro_borda};
  --tema-escrita-suave: {claro_escrita_suave};
  --tema-destaque-hover: {derivados['destaque_hover']};
  --tema-sobre-destaque: {texto_sobre_destaque};

  /* Mapeamento Bootstrap 5.3 (Claro) */
  --bs-primary: {d};
  --bs-primary-rgb: {destaque_rgb};
  --bs-body-bg: {claro_fundo};
  --bs-body-color: {claro_escrita};
  --bs-border-color: {claro_borda};
  --bs-card-bg: {claro_superficie};
  --bs-card-color: {claro_escrita};
  --bs-card-border-color: {claro_borda};
  --bs-link-color: {d};
  --bs-link-color-rgb: {destaque_rgb};
}}

/* Modo Escuro Estrutural Invertido */
[data-bs-theme="dark"] {{
  --tema-fundo: {escuro_fundo};
  --tema-destaque: {d};
  --tema-escrita: {escuro_escrita};
  --tema-destaque-rgb: {destaque_rgb};
  --tema-superficie: {escuro_superficie};
  --tema-borda: {escuro_borda};
  --tema-escrita-suave: {escuro_escrita_suave};
  --tema-destaque-hover: {derivados['destaque_hover']};
  --tema-sobre-destaque: {texto_sobre_destaque};

  /* Mapeamento Bootstrap 5.3 (Escuro) */
  --bs-primary: {d};
  --bs-primary-rgb: {destaque_rgb};
  --bs-body-bg: {escuro_fundo};
  --bs-body-color: {escuro_escrita};
  --bs-border-color: {escuro_borda};
  --bs-card-bg: {escuro_superficie};
  --bs-card-color: {escuro_escrita};
  --bs-card-border-color: {escuro_borda};
  --bs-link-color: {d};
  --bs-link-color-rgb: {destaque_rgb};
  --bs-tertiary-bg: #161922;
  --bs-secondary-bg: #1A1D24;
}}

@media (prefers-color-scheme: dark) {{
  :root:not([data-bs-theme="light"]) {{
    --tema-fundo: {escuro_fundo};
    --tema-destaque: {d};
    --tema-escrita: {escuro_escrita};
    --tema-superficie: {escuro_superficie};
    --tema-borda: {escuro_borda};
    --tema-escrita-suave: {escuro_escrita_suave};
    --bs-body-bg: {escuro_fundo};
    --bs-body-color: {escuro_escrita};
    --bs-border-color: {escuro_borda};
    --bs-card-bg: {escuro_superficie};
    --bs-card-color: {escuro_escrita};
    --bs-card-border-color: {escuro_borda};
  }}
}}

.btn-primary {{
  --bs-btn-color: {texto_sobre_destaque};
  --bs-btn-hover-color: {texto_sobre_destaque};
  --bs-btn-bg: {d};
  --bs-btn-border-color: {d};
  --bs-btn-hover-bg: {derivados['destaque_hover']};
  --bs-btn-hover-border-color: {derivados['destaque_hover']};
  --bs-btn-active-bg: {derivados['destaque_hover']};
  --bs-btn-active-border-color: {derivados['destaque_hover']};
  --bs-btn-disabled-bg: {d};
  --bs-btn-disabled-border-color: {d};
}}

.app-navbar,
.navbar-app {{
  background-color: {d} !important;
  opacity: 1 !important;
}}

.app-navbar .navbar-brand,
.navbar-app .navbar-brand,
.app-navbar .nav-link,
.navbar-app .nav-link {{
  color: {texto_sobre_destaque} !important;
}}

.app-navbar .nav-link:hover,
.navbar-app .nav-link:hover,
.app-navbar .nav-link:focus,
.navbar-app .nav-link:focus,
.app-navbar .nav-link.active,
.navbar-app .nav-link.active {{
  color: #ffffff !important;
  background-color: rgba(255, 255, 255, 0.18) !important;
}}

.btn-login {{
  background-color: {texto_sobre_destaque} !important;
  color: {d} !important;
  border-color: {texto_sobre_destaque} !important;
}}
"""
    return css
