# ADR 002 — Localização e Estratégia de Validação de Invariantes de Domínio no Model (Preço e Estoque Físico)

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

No ecossistema do **Hub Inteligente de Marketplaces**, o catálogo mestre atua como a **Fonte Única da Verdade (*Single Source of Truth*)** para precificação e controle de saldo físico de inventário (`Produto.preco` e `Produto.estoque`). 

Grandezas comerciais e financeiras não podem, sob hipótese alguma, violar invariantes fundamentais de negócio:
- O preço de venda de um produto nunca pode ser negativo ou nulo (`preco >= Decimal('0.00')`), pois propagar um preço negativo ou zerado para Mercado Livre, Shopee ou Amazon acarretaria prejuízos financeiros imediatos por vendas com preço incorreto (*dumping* acidental).
- O saldo físico de inventário não pode ser persistido como negativo em cadastros e ajustes manuais (`estoque >= 0`).
- Entidades relacionadas, como `Categoria`, devem obrigatoriamente pertencer à mesma loja (`loja_id`) do produto para evitar corrupção de catálogo multi-tenant.

O dilema arquitetural enfrentado pela equipe de engenharia era: **onde deve residir a autoridade soberana para a validação dessas regras invariantes de negócio no framework Django?** Na interface visual (HTML/JavaScript), nos formulários da camada de apresentação (`forms.py`), em propriedades Python computadas com setters (`@property`) ou diretamente encapsuladas no modelo de domínio (`models.py`)?

## 2. Decisão

A equipe de engenharia decidiu centralizar a integridade e validação de invariantes **diretamente no Model (`apps/catalogo/models.py`)**, combinando três mecanismos complementares de defesa em profundidade:
1. **Validadores nativos no Schema do Model**: declaração explícita de `validators=[MinValueValidator(Decimal('0.00'))]` na definição dos campos `preco` e `custo_aquisicao`.
2. **Método de validação semântica `clean()` no Model**: implementação da lógica de validação composta no método `clean()` da classe `Produto`:
   ```python
   def clean(self):
       super().clean()
       if self.preco is not None and self.preco < Decimal('0.00'):
           raise ValidationError({'preco': 'O preço de venda não pode ser negativo (RN-06).'})
       if self.categoria_id and self.loja_id:
           if self.categoria.loja_id != self.loja_id:
               raise ValidationError({'categoria': 'A categoria selecionada deve pertencer à mesma loja do produto.'})
   ```
3. **Restrições de integridade no banco de dados (`CheckConstraint`)**: garantia de que mesmo mutações diretas via SQL rejeitem dados inconsistentes.

## 3. Alternativa Descartada

A equipe avaliou e **rejeitou formalmente duas alternativas comuns**:

### Alternativa A: Validação exclusiva na camada de apresentação / formulários (`forms.py` ou validação em tela via JavaScript/HTML5)
- **Por que foi descartada (Justificativa Técnica Profunda)**: A validação em formulários do Django (`forms.Form` ou `ModelForm`) intercepta apenas as requisições submetidas através de navegadores web pela interface de usuário. Em um Hub de Marketplaces, grande parte das mutações de dados ocorre fora da interface web:
  - Ingestão contínua de vendas assíncronas via Webhooks do Mercado Livre (`apps/pedidos/services.py`).
  - Scripts de conciliação e carga de catálogo em lote (`management commands` ou tarefas Celery).
  - Comandos operacionais executados via terminal administrativo do Django (`python manage.py shell`).
  - Sincronização reversa originada de importação de anúncios.
  Se a regra de validação morasse apenas nos formulários, qualquer pedido de webhook com dados anômalos ou comando em lote gravaria dados corrompidos diretamente no banco de dados, destruindo a confiabilidade do Hub como fonte única da verdade.

### Alternativa B: Encapsulamento com propriedades Python (`@property` com `@<campo>.setter`) em Models Django
- **Por que foi descartada (Justificativa Técnica Profunda)**: Embora o uso de `@property` com setters privados seja o padrão tradicional de encapsulamento em Python orientado a objetos puro, sua aplicação para mascarar campos persistidos no Django ORM representa um grave erro arquitetural:
  - O Django ORM depende fundamentalmente de instâncias da classe `models.Field` para inspecionar tipos de dados, gerar migrações de schema (`makemigrations`), mapear chaves relacionais e inferir automaticamente campos em `ModelForm` e no Django Admin.
  - Ao substituir um campo de banco por uma `@property`, o Django Admin quebra ao tentar renderizar o formulário e a listagem de produtos.
  - Consultas essenciais no banco de dados através do ORM (`Produto.objects.filter(preco__gt=100)`) tornam-se impossíveis, pois o Django ORM traduz os campos da classe para colunas SQL na cláusula `WHERE`; propriedades Python computadas em memória não são traduzíveis para SQL relacional.

## 4. Consequência

### Ganhos Reais:
- **Integridade Universal Garantida**: A regra de negócio é respeitada em qualquer canal de entrada do Hub (Admin, Formulários web, Comandos Shell, Webhooks e APIs).
- **Compatibilidade Nativa com o Framework**: Formulários `ModelForm` e o painel administrativo integram-se perfeitamente, exibindo erros de campo semânticos automáticos via `ValidationError`.
- **Prevenção de Falhas de Integração Externa**: Garante que o Hub nunca despache requisições com preços negativos ou inconsistentes para as APIs dos marketplaces parceiros.

### Custos e Limitações Assumidas:
- **Invocação Explícita de `full_clean()`**: Como o método `save()` padrão do Django ORM não invoca `clean()` automaticamente por razões de otimização de performance, serviços e tarefas assíncronas devem invocar explicitamente `instance.full_clean()` antes de persistir alterações vindas de fontes externas.

## 5. Commit

- **Hash Principal**: `4a4bbda` — `:books: ADR-002` (Registro inicial da regra no Caderno de Design).
- **Hash de Implementação no Catálogo de Produtos**: `c2ae6bf` — `feat: implementacao do modulo de cadastro de produtos e categorias (RF-03) com isolamento multi-tenant e RBAC granular` (Implementação de `clean()`, constraints e validações em `Produto` e `Categoria`).
