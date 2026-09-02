# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional

from apps.tenancy.models import Loja
from apps.catalogo.models import Produto
from .models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace


class SimuladorPromocionalService:
    """
    O QUE FAZ: Motor de Inteligência Financeira e Simulador de Viabilidade Promocional para e-commerce multicanal.
    POR QUE FAZ:
      1. Resolve a circularidade matemática do frete e comissões através de cálculo por partes (Piecewise Linear).
      2. Calcula formação de preço ótimo com Markup Divisor.
      3. Analisa o impacto de campanhas promocionais de desconto sobre a margem líquida unitária.
      4. Determina o volume de vendas de compensação (Q_meta) e a elasticidade necessária (Delta Q %) para manter a rentabilidade bruta.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR (FinancialAccessMixin).
    MULTI-TENANCY: Consulta exclusivamente as taxas fiscais e parâmetros de canal configurados para a Loja do usuário.
    """

    @classmethod
    def obter_configuracoes_loja(cls, loja: Loja) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        """
        Retorna: (aliquota_imposto, custo_embalagem_padrao, margem_minima_seguranca, custos_fixos)
        """
        config, _ = ConfiguracaoTaxasLoja.objects.get_or_create(
            loja=loja,
            defaults={
                'aliquota_imposto': Decimal('0.0400'),
                'custo_embalagem_padrao': Decimal('2.50'),
                'margem_minima_seguranca': Decimal('0.1500'),
                'custos_fixos_mensais': Decimal('0.00'),
            }
        )
        return (
            config.aliquota_imposto,
            config.custo_embalagem_padrao,
            config.margem_minima_seguranca,
            config.custos_fixos_mensais,
        )

    @classmethod
    def obter_parametros_canal(cls, loja: Loja, canal_nome: str) -> ParametroCanalMarketplace:
        """
        Obtém ou provisiona parâmetros de taxas do marketplace para a loja.
        """
        defaults_map = {
            'mercadolivre_classico': {'comissao_padrao': Decimal('0.1200'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('18.00'), 'taxa_fixa_abaixo_limite': Decimal('6.00')},
            'mercadolivre_premium': {'comissao_padrao': Decimal('0.1700'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('18.00'), 'taxa_fixa_abaixo_limite': Decimal('6.00')},
            'shopee': {'comissao_padrao': Decimal('0.1400'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('16.00'), 'taxa_fixa_abaixo_limite': Decimal('4.00')},
            'magalu': {'comissao_padrao': Decimal('0.1600'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('17.00'), 'taxa_fixa_abaixo_limite': Decimal('5.00')},
            'amazon': {'comissao_padrao': Decimal('0.1500'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('18.00'), 'taxa_fixa_abaixo_limite': Decimal('5.00')},
        }
        padrao = defaults_map.get(canal_nome, defaults_map['mercadolivre_classico'])

        param, _ = ParametroCanalMarketplace.objects.get_or_create(
            loja=loja,
            marketplace=canal_nome,
            defaults=padrao
        )
        return param

    @classmethod
    def calcular_custo_direto_unitario(cls, produto: Produto, custo_embalagem_padrao: Decimal) -> Decimal:
        """
        O QUE FAZ: Calcula o Custo Variável Unitário (CVu) direto do produto.
        Fórmula: CVu = Custo_Aquisicao + (0 se Modalidade_Full senão (Custo_Embalagem ou Embalagem_Padrao))
        """
        cmv = produto.custo_aquisicao or Decimal('0.00')
        if produto.modalidade_full:
            embalagem = Decimal('0.00')
        else:
            embalagem = produto.custo_embalagem if (produto.custo_embalagem and produto.custo_embalagem > 0) else custo_embalagem_padrao
        return (cmv + embalagem).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def calcular_frete_para_preco(
        cls, preco: Decimal, param_canal: ParametroCanalMarketplace
    ) -> Tuple[Decimal, str]:
        """
        O QUE FAZ: Determina o custo de frete/taxa fixa aplicado com base no preço de venda.
        Regra Piecewise:
          - Se Preco < Piso_Frete_Gratis: Taxa Fixa Abaixo do Limite
          - Se Preco >= Piso_Frete_Gratis: Custo de Frete Acima do Limite
        """
        if preco < param_canal.frete_gratis_piso:
            return param_canal.taxa_fixa_abaixo_limite, "Abaixo do Piso (Taxa Fixa)"
        else:
            return param_canal.taxa_frete_acima_limite, "Acima do Piso (Frete Grátis Obrigatório)"

    @classmethod
    def calcular_formacao_preco(
        cls,
        cvu: Decimal,
        aliquota_imposto: Decimal,
        param_canal: ParametroCanalMarketplace,
        margem_lucro_desejada: Decimal
    ) -> Decimal:
        """
        O QUE FAZ: Resolve a formação de preço ótimo via Markup Divisor sobre regimes por partes.
        Fórmula Geral: Preço = (CVu + Frete) / (1 - Comissao - Imposto - Margem_Desejada)
        """
        comissao = param_canal.comissao_padrao
        markup_divisor = Decimal('1.0') - comissao - aliquota_imposto - margem_lucro_desejada

        if markup_divisor <= Decimal('0.05'):
            markup_divisor = Decimal('0.05')

        limiar = param_canal.frete_gratis_piso

        # Teste Regime A: Preço Abaixo do Limiar
        taxa_a = param_canal.taxa_fixa_abaixo_limite
        preco_a = (cvu + taxa_a) / markup_divisor

        if preco_a < limiar:
            return preco_a.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Teste Regime B: Preço Acima do Limiar
        taxa_b = param_canal.taxa_frete_acima_limite
        preco_b = (cvu + taxa_b) / markup_divisor

        if preco_b >= limiar:
            return preco_b.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Zona de descontinuidade: fixa no limiar
        return limiar.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def simular_impacto_promocional(
        cls,
        produto: Produto,
        canal_nome: str,
        percentual_desconto: Decimal,
        volume_estimado_mensal: int = 100
    ) -> Dict[str, Any]:
        """
        O QUE FAZ: Executa a simulação financeira completa de uma campanha promocional de desconto.
        RETORNA:
          - Preço Original (P0) e Preço Promocional (P_promo)
          - Margens de Contribuição Unitárias (MCU0 e MCU_promo)
          - Margens Líquidas % (ML0 e ML_promo)
          - Volume de Compensação Necessário (Q_meta)
          - Elasticidade de Volume Necessária (Delta Q %)
          - Status de Viabilidade: 'VIAVEL', 'ALERTA_ELASTICIDADE', 'PREJUIZO'
        """
        loja = produto.loja
        imposto, emb_padrao, margem_minima, custos_fixos = cls.obter_configuracoes_loja(loja)
        param_canal = cls.obter_parametros_canal(loja, canal_nome)

        cvu = cls.calcular_custo_direto_unitario(produto, emb_padrao)
        p0 = produto.preco or Decimal('0.00')

        # Percentual de desconto normalizado (0 a 1)
        fator_desc = (percentual_desconto / Decimal('100.0')) if percentual_desconto > Decimal('1.0') else percentual_desconto
        p_promo = (p0 * (Decimal('1.0') - fator_desc)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Cálculo Cenário Original
        frete_p0, _ = cls.calcular_frete_para_preco(p0, param_canal)
        comissao_p0 = (p0 * param_canal.comissao_padrao).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        imposto_p0 = (p0 * imposto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        mcu_0 = p0 - comissao_p0 - imposto_p0 - frete_p0 - cvu
        ml_0 = (mcu_0 / p0) if p0 > 0 else Decimal('0.00')

        # Cálculo Cenário Promocional
        frete_promo, _ = cls.calcular_frete_para_preco(p_promo, param_canal)
        comissao_promo = (p_promo * param_canal.comissao_padrao).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        imposto_promo = (p_promo * imposto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        mcu_promo = p_promo - comissao_promo - imposto_promo - frete_promo - cvu
        ml_promo = (mcu_promo / p_promo) if p_promo > 0 else Decimal('0.00')

        # Elasticidade e Volume de Compensação
        q0 = max(1, volume_estimado_mensal)

        if mcu_promo <= Decimal('0.00'):
            status = 'PREJUIZO'
            q_meta = None
            delta_q_pct = None
            msg_diagnostico = "A promoção gera margem de contribuição negativa. Cada unidade vendida gera prejuízo direto."
        else:
            # Q_meta * MCU_promo = Q0 * MCU0  =>  Q_meta = Q0 * (MCU0 / MCU_promo)
            razao = mcu_0 / mcu_promo
            q_meta = int((Decimal(q0) * razao).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            delta_q_pct = ((razao - Decimal('1.0')) * Decimal('100.0')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

            if ml_promo < margem_minima or delta_q_pct > Decimal('50.0'):
                status = 'ALERTA_ELASTICIDADE'
                msg_diagnostico = f"Margem abaixo do piso de segurança ({margem_minima * 100:.1f}%) ou aumento de volume exigido muito alto (+{delta_q_pct}%)."
            else:
                status = 'VIAVEL'
                msg_diagnostico = f"Promoção saudável! Exige aumento de vendas de +{delta_q_pct}% para manter o lucro total."

        # Preço Mínimo Recomendado e Desconto Máximo Suportável
        preco_minimo_piso = cls.calcular_formacao_preco(cvu, imposto, param_canal, margem_minima)
        if p0 > 0:
            desconto_maximo_suportavel = max(
                Decimal('0.0'),
                ((Decimal('1.0') - (preco_minimo_piso / p0)) * Decimal('100.0')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
            )
        else:
            desconto_maximo_suportavel = Decimal('0.0')

        return {
            'produto_sku': produto.sku,
            'produto_nome': produto.nome,
            'canal_selecionado': param_canal.get_marketplace_display(),
            'cvu': float(cvu),
            'preco_original': float(p0),
            'desconto_aplicado_pct': float(fator_desc * Decimal('100.0')),
            'preco_promocional': float(p_promo),
            # Cenário Original
            'cenario_original': {
                'preco': float(p0),
                'frete': float(frete_p0),
                'comissao': float(comissao_p0),
                'imposto': float(imposto_p0),
                'mcu': float(mcu_0),
                'margem_liquida_pct': float(ml_0 * Decimal('100.0')),
                'volume_base': q0,
                'lucro_bruto_total': float(mcu_0 * Decimal(q0)),
            },
            # Cenário Promocional
            'cenario_promocional': {
                'preco': float(p_promo),
                'frete': float(frete_promo),
                'comissao': float(comissao_promo),
                'imposto': float(imposto_promo),
                'mcu': float(mcu_promo),
                'margem_liquida_pct': float(ml_promo * Decimal('100.0')),
                'volume_meta': q_meta,
                'delta_volume_pct': float(delta_q_pct) if delta_q_pct is not None else None,
                'lucro_bruto_esperado': float(mcu_promo * Decimal(q_meta)) if q_meta else 0.0,
            },
            'status_viabilidade': status,
            'mensagem_diagnostico': msg_diagnostico,
            'preco_minimo_seguranca': float(preco_minimo_piso),
            'desconto_maximo_suportavel_pct': float(desconto_maximo_suportavel),
        }
