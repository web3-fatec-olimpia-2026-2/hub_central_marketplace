# ADR 007 — Padrão de Resiliência Circuit Breaker na Sincronização de Preços e Prevenção de Zeramento em Lote

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

A automação de sincronização entre o catálogo mestre e as APIs externas de marketplaces (Mercado Livre, Shopee, Amazon) traz riscos operacionais e financeiros severos caso ocorram falhas humanas ou de integração:
1. **Erro de Precificação (*Fat-Finger Error*)**: Um operador digita acidentalmente R$ 10,00 em vez de R$ 100,00 (queda de 90%) ou aplica uma regra de margem com separador decimal trocado. Se esse preço for despachado imediatamente para o Mercado Livre, robôs de compras podem liquidar todo o inventário da loja em minutos antes que o erro seja percebido, causando prejuízos financeiros catastróficos.
2. **Zeramento Acidental em Lote (*Mass Out-of-Stock Storm*)**: Uma falha de conciliação de planilha ou instabilidade de rede pode zerar o estoque de dezenas de produtos simultaneamente. Pausar dezenas de anúncios no marketplace de forma indevida derruba o algoritmo de ranqueamento da conta do lojista e paralisa o faturamento.

A equipe precisava de uma barreira de proteção arquitetural que interceptasse anomalias antes que as requisições de rede fossem submetidas aos canais externos.

## 2. Decisão

A equipe decidiu implementar o padrão de resiliência e estabilidade **Circuit Breaker** encapsulado na camada de orquestração de sincronização (`apps/anuncios/services.py: AnuncioSincronizacaoService`):
1. **Circuit Breaker de Variação de Preço (`validar_variacao_preco`)**:
   - Limite Máximo de Queda: 50% (`MAX_QUEDA_PRECO_PERCENTUAL = Decimal('0.50')`).
   - Limite Máximo de Aumento: 100% (`MAX_ALTA_PRECO_PERCENTUAL = Decimal('1.00')`).
   - Se o preço proposto divergir dos limiares de segurança em relação ao preço atualmente publicado, o disjuntor desarma (*Trip*), aborta a chamada de API e retorna uma mensagem semântica clara com o percentual de divergência detectado.
2. **Circuit Breaker de Zeramento em Lote (`validar_zeramento_em_lote`)**:
   - Bloqueia operações quando mais de 5 itens ativos ou mais de 50% do lote de anúncios forem submetidos com estoque zero simultaneamente (`LIMITE_ZERAMENTO_LOTE_ITENS = 5` / `LIMITE_ZERAMENTO_LOTE_PERCENTUAL = 0.50`).
3. **Mecanismo de Sobrescrita Controlada (*Override*)**:
   - O disjuntor permite bypass somente quando o operador (perfil `ADMIN` ou `DEV`) confirma expressamente a alteração através de um parâmetro de autorização explícito (`forcar=True`), acompanhado de log de auditoria compulsório.

## 3. Alternativa Descartada

A equipe avaliou e **rejeitou duas abordagens alternativas**:

### Alternativa 1: Despacho direto e irrestrito de qualquer valor submetido (Sem Circuit Breaker)
- **Por que foi descartada (Justificativa Técnica)**: Tratar a sincronização como um simples "passa-prato" cego das mutações de banco para a API externa ignora a vulnerabilidade do fator humano e inconsistências de integração. No comércio eletrônico de alta escala, comandos acidentais de zeramento ou preços irrisórios geram cancelamentos forçados de pedidos, penalidades jurídicas (CDC) e até bloqueio permanente da conta do seller no Mercado Livre.

### Alternativa 2: Bloqueio rígido definitivo sem possibilidade de override
- **Por que foi descartada (Justificativa Técnica)**: Se o sistema rejeitasse alterações superiores a 50% de forma estática sem exceção, ele inviabilizaria promoções reais e agressivas de vendas (ex.: campanhas legítimas de Black Friday com descontos de 60% ou liquidação de ponta de estoque). O Circuit Breaker com confirmação explícita em modal equilibra segurança máxima contra erros operacionais sem retirar a autonomia de negócio do lojista.

## 4. Consequência

### Ganhos Reais:
- **Blindagem Financeira do Negócio**: Erros de digitação e oscilações anômalas de preços são contidos na camada interna do Hub antes de atingirem a internet.
- **Proteção do Ranqueamento nos Marketplaces**: Evita pausas acidentais em massa de anúncios de alta conversão por falhas de integração.
- **Auditoria de Operações Críticas**: Toda tentativa de bypass do disjuntor registra a identidade do usuário e os valores divergentes em `LogAuditoria`.

### Custos e Limitações Assumidas:
- **Necessidade de Confirmação em Modais**: Alterações legítimas de grande magnitude exigem uma etapa adicional de confirmação por parte dos operadores na interface gráfica.

## 5. Commit

- **Hash Principal**: `8284bc8` — `feat(anuncios): implementa Fase 2 de sincronizacao segura de estoque e preco com circuit breaker e signals` (Implementação dos limites, métodos de validação e desarmamento de disjuntor).
- **Hash de Consumo na UI**: `e792dbb` — `fix(catalogo): refina sincronizacao com confirmacao modal, controle de pendencias e historico unificado`.
