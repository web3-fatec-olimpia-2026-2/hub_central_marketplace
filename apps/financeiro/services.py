# Os códigos foram gerados com auxilio de I.A.

# Importa a classe Decimal para precisão matemática monetária e o modo de arredondamento ROUND_HALF_UP (arredonda 0.5 para cima)
from decimal import Decimal, ROUND_HALF_UP

# Importa tipagens estáticas para estruturas de dicionários, tipos genéricos, tuplas e opcionais
from typing import Dict, Any, Optional, Tuple

# Importa a entidade Loja para garantir a contextualização multi-tenant das taxas
from apps.tenancy.models import Loja

# Importa o modelo Produto que fornece o custo de aquisição, preço atual e embalagem
from apps.catalogo.models import Produto

# Importa os modelos de configurações tributárias da loja e parâmetros tarifários dos canais
from .models import ConfiguracaoTaxasLoja, ParametroCanalMarketplace


# Declara a classe de serviço responsável pelo motor de inteligência financeira e simulações promocionais
class SimuladorPromocionalService:
    # Início do bloco de docstring que detalha as responsabilidades matemáticas, RBAC e isolamento multi-tenant
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
    # Fim do bloco de documentação do serviço

    # Método de classe para recuperar ou provisionar as diretrizes fiscais e custos fixos da loja informada
    @classmethod
    def obter_configuracoes_loja(cls, loja: Loja) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        """
        Retorna: (aliquota_imposto, custo_embalagem_padrao, margem_minima_seguranca, custos_fixos)
        """
        # Busca a configuração fiscal da loja ou cria um registro com valores conservadores padrão caso inexista
        config, _ = ConfiguracaoTaxasLoja.objects.get_or_create(
            loja=loja,
            defaults={
                'aliquota_imposto': Decimal('0.0400'),
                'custo_embalagem_padrao': Decimal('2.50'),
                'margem_minima_seguranca': Decimal('0.1500'),
                'custos_fixos_mensais': Decimal('0.00'),
            }
        )
        # Retorna uma tupla contendo alíquota tributária, embalagem padrão, margem mínima e custos fixos
        return (
            config.aliquota_imposto,
            config.custo_embalagem_padrao,
            config.margem_minima_seguranca,
            config.custos_fixos_mensais,
        )

    # Método de classe para recuperar ou provisionar as regras tarifárias específicas de um canal para a loja
    @classmethod
    def obter_parametros_canal(cls, loja: Loja, canal_nome: str) -> ParametroCanalMarketplace:
        """
        Obtém ou provisiona parâmetros de taxas do marketplace para a loja.
        """
        # Dicionário com as tarifas de mercado padrão por canal para inicialização automática de novos tenants
        defaults_map = {
            'mercadolivre_classico': {'comissao_padrao': Decimal('0.1200'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('18.00'), 'taxa_fixa_abaixo_limite': Decimal('6.00')},
            'mercadolivre_premium': {'comissao_padrao': Decimal('0.1700'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('18.00'), 'taxa_fixa_abaixo_limite': Decimal('6.00')},
            'shopee': {'comissao_padrao': Decimal('0.1400'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('16.00'), 'taxa_fixa_abaixo_limite': Decimal('4.00')},
            'magalu': {'comissao_padrao': Decimal('0.1600'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('17.00'), 'taxa_fixa_abaixo_limite': Decimal('5.00')},
            'amazon': {'comissao_padrao': Decimal('0.1500'), 'frete_gratis_piso': Decimal('79.00'), 'taxa_frete_acima_limite': Decimal('18.00'), 'taxa_fixa_abaixo_limite': Decimal('5.00')},
        }
        # Seleciona o dicionário de defaults do canal solicitado ou utiliza mercadolivre_classico como fallback
        padrao = defaults_map.get(canal_nome, defaults_map['mercadolivre_classico'])

        # Busca ou cria a regra no banco de dados respeitando o tenant
        param, _ = ParametroCanalMarketplace.objects.get_or_create(
            loja=loja,
            marketplace=canal_nome,
            defaults=padrao
        )
        # Retorna a instância com as taxas do canal
        return param

    # Método que calcula o Custo Variável Unitário (CVu) direto do produto físico
    @classmethod
    def calcular_custo_direto_unitario(cls, produto: Produto, custo_embalagem_padrao: Decimal) -> Decimal:
        """
        O QUE FAZ: Calcula o Custo Variável Unitário (CVu) direto do produto.
        Fórmula: CVu = Custo_Aquisicao + (0 se Modalidade_Full senão (Custo_Embalagem ou Embalagem_Padrao))
        """
        # Obtém o CMV do produto ou assume zero caso nulo
        cmv = produto.custo_aquisicao or Decimal('0.00')
        # Se a mercadoria estiver na modalidade Full, o custo próprio de embalagem do lojista é zerado
        if produto.modalidade_full:
            embalagem = Decimal('0.00')
        # Para logística própria, utiliza o custo específico do produto ou herda o padrão da loja
        else:
            embalagem = produto.custo_embalagem if (produto.custo_embalagem and produto.custo_embalagem > 0) else custo_embalagem_padrao
        # Retorna a soma de aquisição e embalagem arredondada para duas casas decimais
        return (cmv + embalagem).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Método que determina a taxa de envio ou taxa fixa com base no valor de venda (função linear por partes)
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
        # Se o preço for inferior ao piso de frete grátis do canal (ex.: R$ 79,00)
        if preco < param_canal.frete_gratis_piso:
            # Retorna a taxa fixa por item e a descrição do regime
            return param_canal.taxa_fixa_abaixo_limite, "Abaixo do Piso (Taxa Fixa)"
        # Se o preço atingir ou ultrapassar o piso de frete grátis
        else:
            # Retorna o custo de frete subsidiado obrigatório e a descrição do regime
            return param_canal.taxa_frete_acima_limite, "Acima do Piso (Frete Grátis Obrigatório)"

    # Método que soluciona o preço de venda ideal usando a técnica do Markup Divisor sobre funções por partes
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
        # Lê o percentual de comissão do canal
        comissao = param_canal.comissao_padrao
        # Calcula o denominador do markup: 1 - (soma das taxas variáveis percentuais)
        markup_divisor = Decimal('1.0') - comissao - aliquota_imposto - margem_lucro_desejada

        # Proteção matemática para impedir divisão por zero ou markups negativos em cenários de margens inviáveis
        if markup_divisor <= Decimal('0.05'):
            markup_divisor = Decimal('0.05')

        # Limiar de corte monetário que separa os regimes tarifários
        limiar = param_canal.frete_gratis_piso

        # Teste Regime A: Preço Abaixo do Limiar
        # Recupera a tarifa administrativa fixa aplicada em itens de baixo ticket
        taxa_a = param_canal.taxa_fixa_abaixo_limite
        # Calcula o preço hipotético admitindo que ele ficará abaixo do piso
        preco_a = (cvu + taxa_a) / markup_divisor

        # Valida se a hipótese do Regime A é matematicamente consistente com o preço calculado
        if preco_a < limiar:
            # Hipótese confirmada: retorna o preço do Regime A
            return preco_a.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Teste Regime B: Preço Acima do Limiar
        # Recupera o custo de frete subsidiado aplicável acima do piso
        taxa_b = param_canal.taxa_frete_acima_limite
        # Calcula o preço hipotético admitindo que ele superará o piso
        preco_b = (cvu + taxa_b) / markup_divisor

        # Valida se a hipótese do Regime B é consistente com o preço obtido
        if preco_b >= limiar:
            # Hipótese confirmada: retorna o preço do Regime B
            return preco_b.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Zona de descontinuidade: fixa no limiar
        # Trata a descontinuidade do degrau tarifário travando o preço exatamente na fronteira do limiar
        return limiar.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Método que realiza o diagnóstico financeiro completo de campanhas promocionais de desconto
    @classmethod
    def simular_impacto_promocional(
        cls,
        produto: Produto,
        canal_nome: str,
        percentual_desconto: Decimal,
        volume_estimado_mensal: int = 100
    ) -> Dict[str, Any]:
        # Início da docstring que documenta o payload completo de telemetria e retorno da simulação
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
        # Fim do bloco descritivo do método

        # Recupera o tenant ao qual o produto pertence
        loja = produto.loja
        # Obtém os parâmetros fiscais e custos da loja
        imposto, emb_padrao, margem_minima, custos_fixos = cls.obter_configuracoes_loja(loja)
        # Obtém os parâmetros tarifários do canal selecionado
        param_canal = cls.obter_parametros_canal(loja, canal_nome)

        # Calcula o custo variável unitário (CVu)
        cvu = cls.calcular_custo_direto_unitario(produto, emb_padrao)
        # Preço de venda original praticado
        p0 = produto.preco or Decimal('0.00')

        # Percentual de desconto normalizado (0 a 1)
        # Converte valores percentuais em fração (ex.: 10.0 vira 0.10)
        fator_desc = (percentual_desconto / Decimal('100.0')) if percentual_desconto > Decimal('1.0') else percentual_desconto
        # Calcula o novo preço com desconto aplicado
        p_promo = (p0 * (Decimal('1.0') - fator_desc)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Cálculo Cenário Original
        # Obtém o frete ou taxa fixa aplicável ao preço original
        frete_p0, _ = cls.calcular_frete_para_preco(p0, param_canal)
        # Calcula a comissão do canal em reais sobre o preço original
        comissao_p0 = (p0 * param_canal.comissao_padrao).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Calcula o imposto faturado em reais sobre o preço original
        imposto_p0 = (p0 * imposto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Calcula a Margem de Contribuição Unitária original: MCU0 = P0 - Comissao - Imposto - Frete - CVu
        mcu_0 = p0 - comissao_p0 - imposto_p0 - frete_p0 - cvu
        # Calcula a margem líquida percentual original: ML0 = MCU0 / P0
        ml_0 = (mcu_0 / p0) if p0 > 0 else Decimal('0.00')

        # Cálculo Cenário Promocional
        # Recalcula o frete ou taxa fixa com base no novo preço com desconto (pode migrar de degrau tarifário)
        frete_promo, _ = cls.calcular_frete_para_preco(p_promo, param_canal)
        # Recalcula a comissão em reais sobre o preço promocional
        comissao_promo = (p_promo * param_canal.comissao_padrao).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Recalcula o imposto em reais sobre o faturamento promocional
        imposto_promo = (p_promo * imposto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Calcula a Margem de Contribuição Unitária promocional: MCU_promo = P_promo - Comissao - Imposto - Frete - CVu
        mcu_promo = p_promo - comissao_promo - imposto_promo - frete_promo - cvu
        # Calcula a margem líquida percentual promocional
        ml_promo = (mcu_promo / p_promo) if p_promo > 0 else Decimal('0.00')

        # Elasticidade e Volume de Compensação
        # Volume base de vendas mensal informado (mínimo de 1 unidade para evitar divisões por zero)
        q0 = max(1, volume_estimado_mensal)

        # Se a margem de contribuição no preço com desconto for nula ou negativa
        if mcu_promo <= Decimal('0.00'):
            # Classifica a promoção como operação com prejuízo direto
            status = 'PREJUIZO'
            q_meta = None
            delta_q_pct = None
            msg_diagnostico = "A promoção gera margem de contribuição negativa. Cada unidade vendida gera prejuízo direto."
        # Se a margem de contribuição promocional for positiva
        else:
            # Q_meta * MCU_promo = Q0 * MCU0  =>  Q_meta = Q0 * (MCU0 / MCU_promo)
            # Calcula a razão de compensação entre a margem original e a margem promocional
            razao = mcu_0 / mcu_promo
            # Calcula o volume total de unidades necessárias para atingir o mesmo lucro bruto original
            q_meta = int((Decimal(q0) * razao).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            # Calcula a elasticidade necessária em percentual adicional de vendas: ((razao - 1) * 100)
            delta_q_pct = ((razao - Decimal('1.0')) * Decimal('100.0')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

            # Se a nova margem cair abaixo do piso de segurança da loja ou exigir aumento irreal de volume (> 50%)
            if ml_promo < margem_minima or delta_q_pct > Decimal('50.0'):
                status = 'ALERTA_ELASTICIDADE'
                msg_diagnostico = f"Margem abaixo do piso de segurança ({margem_minima * 100:.1f}%) ou aumento de volume exigido muito alto (+{delta_q_pct}%)."
            # Se a campanha mantiver a saúde financeira da operação
            else:
                status = 'VIAVEL'
                msg_diagnostico = f"Promoção saudável! Exige aumento de vendas de +{delta_q_pct}% para manter o lucro total."

        # Preço Mínimo Recomendado e Desconto Máximo Suportável
        # Calcula o piso mínimo de preço que preserva a margem de segurança exigida pela loja
        preco_minimo_piso = cls.calcular_formacao_preco(cvu, imposto, param_canal, margem_minima)
        # Calcula a porcentagem máxima de desconto que o produto tolera antes de romper a margem mínima
        if p0 > 0:
            desconto_maximo_suportavel = max(
                Decimal('0.0'),
                ((Decimal('1.0') - (preco_minimo_piso / p0)) * Decimal('100.0')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
            )
        else:
            desconto_maximo_suportavel = Decimal('0.0')

        # Retorna o diagnóstico financeiro detalhado com cenários original e simulado
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
