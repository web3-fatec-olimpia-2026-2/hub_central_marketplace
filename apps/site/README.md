# Módulo de Site, Temas e Visibilidade Pública (`apps/site`)

## 1. Responsabilidade e Objetivo
O módulo `site` implementa o motor de temas desacoplados, geração dinâmica e sanitizada de CSS, chaveamento de visibilidade pública na rota raiz `/` e páginas institucionais com rigorosa conformidade às diretrizes WCAG 2.1 e anti-enumeração de rotas (Doc ① §11 e §17.2).

## 2. Modelos e Escopo
- **`ConfigTema`:** Persiste os tokens visuais (Fundos, Destaques, Escritas), eixos de estilo (`data-raio`, `data-sombra`, `data-densidade`, `data-movimento`, `data-tipografia`, `data-icones`) e hash de versionamento.
  - Escopo: possui `loja` opcional (nulo representa a configuração global padrão).
  - Validação: bloqueio estrito em caso de reprovação WCAG 2.1 (Escritas × Fundos < 4,5:1; Destaques × Fundos < 3:1) e validação regex `^#[0-9A-Fa-f]{6}$` contra CSS Injection.
- **`ConfigSite`:** Controla a flag `visibilidade_publica`.
  - Escopo: possui `loja` opcional (nulo representa escopo global).

## 3. Visibilidade Pública e Chaveamento da Rota Raiz (Doc ① §11.1)
- **Rota `/`:**
  - Usuário autenticado: navega diretamente para o Dashboard principal da aplicação.
  - Usuário anônimo + Visibilidade Ativa: renderiza Landing Page com botão destacado para Login.
  - Usuário anônimo + Visibilidade Desativada: renderiza a tela de Login diretamente.
- **Política Anti-Enumeração (§17.2):** Páginas públicas controláveis (`/apresentacao/`) respondem obrigatoriamente **`HTTP 404`** para anônimos quando a visibilidade estiver desativada.

## 4. Context Processor Resiliente
- `apps.site.context_processors.tema`: injeta `tema`, `tema_versao`, `shell_template` e `menu_grupos`.
- **Garantia de tolerância a falhas:** jamais levanta exceção; caso ocorra indisponibilidade ou ausência de dados, retorna transparentemente os valores do preset padrão **T05 Profissional**.

## 5. Dependências
- `apps.core`
- `apps.accounts`
- `apps.tenancy`
