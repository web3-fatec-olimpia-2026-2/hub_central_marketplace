# Módulo de Geração de Dados Sintéticos e Mock (`apps/mockar_dados`)

## 1. Responsabilidade e Objetivo
O módulo `mockar_dados` fornece rotinas de carga de dados para testes em desenvolvimento e homologação (seeding), além de simulações de retornos de APIs externas.

## 2. Isolamento de Segurança
- Disponível estritamente em ambiente de desenvolvimento quando `LOGIN_DEBUG=True` ou `DEBUG=True`.
- Não afeta ambientes produtivos.

## 3. Dependências
- `apps.core`
- `apps.tenancy`
- `apps.catalogo`
- `apps.marketplaces`
