# ADR 001 — Definição de Projeto [Hub Inteligente de Marketplaces]

## Contexto

O campo quarto aceitava valores nulos ou negativos o que não era condizente com a realidade.

## Decisão

Foi usado a função de validação MinValueValidator(1) para manter o valor minimo possível em 1.

## Alternativa descartada

manter sem validação, pois permitia a inclusão de valores irreais.

## Consequência

Agora ao tentar cadastrar quartos com valore negativos ou valor 0 é exibido uma mensagem de erro e o cadastro é iterrompido.

## Commit

