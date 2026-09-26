# Plano de Implementação — Motor de Inteligência Financeira e Simulador de Viabilidade Promocional

## 1. Objetivo

Traduzir, dentro do Hub, o mecanismo de alavancagem operacional demonstrado no exemplo de
referência — um desconto nominal de 5% no preço reduz a margem de contribuição unitária em
16,67% e o lucro líquido em 50%, exigindo +20% de volume só para empatar — em um serviço que
o lojista possa consultar *antes* de aceitar uma promoção de marketplace.

## 2. Reconciliação das Duas Especificações Coladas

O texto de origem contém duas versões da modelagem (a seção "Requisitos" e o "Prompt pronto
para o Antigravity"), com divergências pontuais de nome. Este plano adota a versão do prompt
final como canônica, por trazer tipos e defaults explícitos. Divergências resolvidas:

| Ponto | Versão "Requisitos" | Versão canônica (adotada) |
|---|---|---|
| Campo de embalagem em `Produto` | `custo_embalagem_customizado` | `custo_embalagem` |
| Local do serviço | `core/services/financial.py` (pacote) | `core/services.py` (módulo único) |
| Taxa acima do piso de frete grátis | `taxa_frete_lojista` | `taxa_frete_acima_limite` |
| Tarifa abaixo do piso | `tarifa_fixa_item_barato` | `taxa_fixa_abaixo_limite` |

Todo o restante do plano usa a nomenclatura canônica.

## 3. Preparação do Ambiente

```bash
git checkout main
git pull origin main
git checkout -b feat/motor-inteligencia-financeira-promocoes
```

## 4. Roteiro de Execução (ordem recomendada)

| # | Etapa | Arquivos | Critério de aceite |
|---|---|---|---|
| 1 | Modelos + migração | `core/models.py`, nova migração | `makemigrations` sem warnings; `migrate` aplica limpo em base com dados existentes (defaults não quebram nada) |
| 2 | Admin (recomendado, não obrigatório) | `core/admin.py` | `ConfiguracaoTaxasLoja` e `ParametroCanalMarketplace` editáveis via `/admin`, para permitir carga inicial dos parâmetros sem depender de UI própria |
| 3 | Camada de serviço | `core/services.py` | Funções puras (sem `request`, sem I/O além do necessário), 100% cobertas por teste |
| 4 | Testes do serviço | `core/tests.py` | Casos batem com os números do exemplo de referência (seção 5.8) |
| 5 | View + URL | `core/views.py`, `core/urls.py` | Acesso restrito a `SUPERVISOR`/`ADMIN`/`DEV`; 403/404 fora do tenant |
| 6 | Templates | `simulador_promocional.html`, `produto_list.html` | Sliders recalculam KPIs sem reload de página |
| 7 | Cabeçalho de IA | todos os arquivos novos/alterados | `python scripts/check_ai_header.py` sem erros |
| 8 | Suíte completa | — | `python manage.py test core` sem falhas |
| 9 | Commit + push | — | mensagem conforme convenção definida |

A ordem importa: a camada de serviço (3–4) deve estar validada por teste **antes** de conectar
views e templates, porque as fórmulas têm um ponto de circularidade (seção 5.3) que é mais
barato de depurar isoladamente do que através da UI.

## 5. Especificação Técnica

### 5.1 Modelagem de dados

**`Produto`** — campos novos:
- `custo_aquisicao` — `DecimalField`, default `0.00`
- `custo_embalagem` — `DecimalField`, default `0.00`
- `modalidade_full` — `BooleanField`, default `False` (se `True`, o custo próprio de embalagem é zerado no cálculo, pois o marketplace assume esse custo)

**`ConfiguracaoTaxasLoja`** (`OneToOneField` → `Loja`):
- `aliquota_imposto` — default `6.00` (%)
- `custo_embalagem_padrao` — default `2.00` (herdado quando `Produto.custo_embalagem` for nulo/zero e não houver override)
- `margem_minima_seguranca` — default `5.00` (%)
- `custos_fixos_mensais` — default `0.00`

**`ParametroCanalMarketplace`** (`ForeignKey` → `Loja`):
- `marketplace` — choices: `mercadolivre_classico`, `mercadolivre_premium`, `shopee`, `magalu`
- `comissao_padrao` — default `16.00` (%)
- `frete_gratis_piso` — default `79.00`
- `taxa_frete_acima_limite` — default `18.00`
- `taxa_fixa_abaixo_limite` — default `6.00`

Constraint recomendada: `unique_together = ("loja", "marketplace")`, para impedir duplicidade de
parâmetros por canal.

### 5.2 Camada de serviço — contratos das funções

```python
# core/services.py
# Os códigos foram gerados com auxilio de I.A.

class SimuladorPromocionalService:

    @staticmethod
    def calcular_formacao_preco(produto, canal, margem_alvo):
        """
        Retorna o preço de venda (Decimal) que garante margem_alvo (%)
        após comissão, imposto e frete do canal.
        Resolve a circularidade de frete via regime piecewise (ver 5.3).
        """

    @staticmethod
    def simular_impacto_promocional(produto, canal, desconto_total,
                                     subsidio_mkt, volume_base=1000):
        """
        Retorna um dict/dataclass com:
          - preco_promocional, receita_liquida_seller
          - nova_margem_contribuicao_rs, nova_margem_contribuicao_pct
          - elasticidade_minima_pct        (ΔQ%)
          - volume_meta_compensacao        (Qmeta)
          - desconto_maximo_suportavel_pct (D_seller_max)
          - status: "VIAVEL" | "ALERTA_ELASTICIDADE" | "PREJUIZO"
        """
```

### 5.3 O problema da circularidade do frete

`frete_gratis_piso` define qual tarifa de frete se aplica — mas essa tarifa depende do preço
final, e o preço final (em `calcular_formacao_preco`) ou a margem resultante (no cálculo do
desconto máximo) dependem da tarifa. É circular. Algoritmo recomendado para ambos os casos:
resolver assumindo um regime, validar a hipótese, e recair no outro regime se ela falhar.

### 5.4 Algoritmo do Desconto Máximo Suportável (`D_seller_max`)

Definições:
- `P0` = preço cheio do produto (sem desconto)
- `CFdir` = `custo_aquisicao` + `custo_embalagem` efetivo (`0` se `modalidade_full=True`)
- `pv` = (`comissao_padrao` + `aliquota_imposto`) / 100
- `MC(P) = P × (1 − pv) − CFdir − Frete(P)`

O preço `P*` que zera a margem (`MC(P*) = 0`) é resolvido por regime:

```
Regime A (assume P* >= piso, Frete = taxa_frete_acima_limite):
    P*_A = (CFdir + taxa_frete_acima_limite) / (1 − pv)
    válido somente se P*_A >= frete_gratis_piso

Regime B (assume P* < piso, Frete = taxa_fixa_abaixo_limite):
    P*_B = (CFdir + taxa_fixa_abaixo_limite) / (1 − pv)
    válido somente se P*_B < frete_gratis_piso
```

`D_seller_max = 1 − (P* / P0)`, usando o `P*` do regime que se validar. Se nenhum dos dois se
validar (piso mal configurado em relação aos custos), o serviço deve retornar um erro de
configuração explícito em vez de um número — é sinal de que os parâmetros do canal estão
inconsistentes, não um resultado financeiro válido.

O mesmo algoritmo piecewise se aplica a `calcular_formacao_preco`, substituindo `pv` por
`comissao + imposto + margem_alvo` e mantendo o frete como termo no numerador, conforme a
fórmula original:

```
PV = (CustoProd + CustoEmb + Frete) / (1 − (comissao + imposto + margem_alvo) / 100)
```

### 5.5 Regras de status de viabilidade — decisão em aberto

O texto de origem nomeia os três status (`VIÁVEL`, `ALERTA_ELASTICIDADE`, `PREJUÍZO`) mas não
fixa os limiares numéricos. Proponho como ponto de partida (parametrizável, não hardcoded):

- **PREJUÍZO** 🔴 — `nova_margem_contribuicao_rs <= 0`
- **ALERTA_ELASTICIDADE** 🟡 — margem positiva, mas `nova_margem_contribuicao_pct <
  margem_minima_seguranca` da loja, **ou** `elasticidade_minima_pct` acima de um teto
  configurável (sugestão inicial: 15%)
- **VIÁVEL** 🟢 — margem acima do mínimo de segurança **e** elasticidade exigida dentro do teto

Isso deveria ser validado com o time de produto antes do merge, já que afeta diretamente a
recomendação que o lojista vai seguir.

### 5.6 Views e permissões

- `SimuladorPromocionalView` — `LoginRequiredMixin` + mixin de papel (`SUPERVISOR`/`ADMIN`/`DEV`)
- GET → página dedicada (formulário Bootstrap 5)
- POST via `fetch`/AJAX → JSON com o resultado de `simular_impacto_promocional`, para alimentar
  os sliders em tempo real sem reload
- Toda query de `Produto`/`ParametroCanalMarketplace` filtrada por `request.user.loja` — nunca
  por `produto_id` cru vindo da URL sem checar o tenant

### 5.7 Templates e frontend

- `simulador_promocional.html`: sliders/inputs para `% Desconto Total`, `% Subsídio Marketplace`
  e `Volume Mensal Estimado`; cards de KPI (Lucro Unitário Antes/Depois, Desconto Máximo Seguro,
  Volume Mínimo Obrigatório)
- `produto_list.html`: botão "Simular Promoção" por linha, abrindo modal com os dados do SKU
  pré-carregados (evita o usuário redigitar custo/canal)

### 5.8 Testes obrigatórios (com valores de referência)

Usar o próprio exemplo numérico do vídeo como fixture de teste — já validado manualmente:

```python
# entrada: P=100, CVu=70, desconto_total=5%, subsidio_mkt=0%, volume_base=1000
# esperado:
#   preco_promocional            == 95.00
#   nova_margem_contribuicao_rs  == 25.00   (por unidade)
#   elasticidade_minima_pct      == 20.0    (30/25 - 1) * 100
#   volume_meta_compensacao      == 1200    (para manter lucro de 10.000)
```

Casos adicionais:
1. `test_markup_frete_gratis_vs_tarifa_fixa` — preço cruzando o piso nos dois sentidos
2. `test_elasticidade_desconto_subsidio_parcial` — fixture acima
3. `test_desconto_maximo_suportavel_regime_a_e_b` — força cada regime do algoritmo 5.4
4. `test_isolamento_multitenant` — lojista A recebe 403/404 ao tentar simular produto ou acessar
   parâmetros da loja B

## 6. Riscos e Edge Cases

- **Decimal vs float**: todos os cálculos monetários em `Decimal`, nunca `float` (evita erro de
  arredondamento acumulado nas fórmulas de markup)
- **Divisão por zero**: `elasticidade_minima_pct` usa `MC_original / MC_promocional` — proteger
  o caso `MC_promocional == 0` (retornar `PREJUÍZO` direto, sem calcular a razão)
- **Preço exatamente no piso**: definir explicitamente se `P == piso` conta como "acima" ou
  "abaixo" (recomendo tratar como frete grátis, ou seja, regime "acima")
- **`desconto_total < subsidio_mkt`**: já coberto por `D_seller = max(0, D_total − D_mkt)`
- **`volume_base = 0`**: guard clause explícita, retornar erro de validação em vez de resultado
  numérico sem sentido

## 7. Definition of Done

- [ ] Migração aplica sem quebrar dados existentes
- [ ] `SimuladorPromocionalService` com 100% de cobertura nas fórmulas críticas
- [ ] Fixture do exemplo de referência (seção 5.8) passando com os valores exatos
- [ ] Isolamento multi-tenant coberto por teste
- [ ] View reativa sem reload de página
- [ ] `check_ai_header.py` limpo
- [ ] `python manage.py test core` verde
- [ ] Branch pushada com a mensagem de commit convencionada

## 8. Prompt Final Revisado para o Antigravity

Mesmo conteúdo do prompt original, com a nomenclatura já reconciliada (seção 2) e a observação
sobre o algoritmo piecewise de frete (seção 5.3–5.4) incluída explicitamente, para que o agente
não implemente uma fórmula ingênua que ignore a circularidade:

```
Crie uma nova branch chamada feat/motor-inteligencia-financeira-promocoes a partir da main
e implemente o Motor de Inteligência Financeira e Simulador de Viabilidade Promocional:

1. Modelagem (core/models.py + migração): campos custo_aquisicao, custo_embalagem,
   modalidade_full em Produto; modelos ConfiguracaoTaxasLoja e ParametroCanalMarketplace
   conforme especificado no plano, seção 5.1.

2. core/services.py — classe SimuladorPromocionalService com calcular_formacao_preco()
   e simular_impacto_promocional(). IMPORTANTE: o frete alterna entre taxa_frete_acima_limite
   e taxa_fixa_abaixo_limite conforme o preço cruza frete_gratis_piso — isso cria uma
   circularidade (o regime depende do preço, o preço depende do regime). Resolva assumindo
   um regime, validando a hipótese contra o piso, e recaindo no outro regime se necessário
   (não assuma um regime fixo).

3. Views/templates: SimuladorPromocionalView (GET set página, POST AJAX retorna JSON),
   restrita a SUPERVISOR/ADMIN/DEV, com isolamento por loja em toda query. Template
   simulador_promocional.html com sliders Bootstrap 5 recalculando KPIs via fetch, sem
   reload. Botão "Simular Promoção" em produto_list.html abrindo modal pré-carregado.

4. Testes: usar como fixture obrigatória P=100, CVu=70, desconto=5% → NMC=25, ΔQ%=20,
   Qmeta=1200. Cobrir os dois regimes de frete e o isolamento multi-tenant.

5. Cabeçalho de IA em todo arquivo novo/alterado; rodar check_ai_header.py e
   manage.py test core antes do commit.

6. git commit -m 'feat(financial): implementa motor de inteligencia financeira e
   simulador de promocoes'
   git push -u origin feat/motor-inteligencia-financeira-promocoes
```
