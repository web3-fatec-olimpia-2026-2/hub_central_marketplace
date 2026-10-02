# Módulo de Contas, Autenticação e RBAC (`apps/accounts`)

## 1. Responsabilidade e Objetivo
O módulo `accounts` gerencia a autenticação, segurança de login, conformidade de fluxo de redefinição de senha e o catálogo centralizado das funcionalidades do RBAC (Role-Based Access Control) do ecossistema Django.

## 2. Modelos e Escopo de Tenancy
- Atua diretamente com a entidade nativa `User` do Django e o perfil hierárquico `PerfilUsuario` (definido em `apps/tenancy`).
- As atribuições operacionais possuem escopo de tenant (`Loja`), com exceção do papel mestre Desenvolvedor (Grupo 4), que possui escopo global.

## 3. Funcionalidades Reservadas do Ecossistema (Doc ① §17.5)
O módulo registra e protege formalmente as 4 chaves normativas:
1. `accounts.matriz`: Visualização e edição da matriz de permissões RBAC (Grupos 3 e 4; Não delegável).
2. `accounts.atribuir_perfis`: Atribuição de perfis hierárquicos a operadores (Grupos 3 e 4; Não delegável).
3. `site.tema_editar`: Customização e alternância do tema visual do produto (Grupos 3 e 4; Delegável).
4. `site.visibilidade_publica`: Alternância do status de visibilidade pública de páginas (Grupos 3 e 4; Delegável).

## 4. Diretrizes de Interface e Login (Doc ① §16.2)
- O formulário de login (`templates/registration/login.html`) atende rigorosamente à ordem do DOM:
  1. Campo de Usuário (`autocomplete="username"`)
  2. Campo de Senha (`autocomplete="current-password"`)
  3. Botão de Ação Principal **Entrar**
  4. Link **"Esqueci minha senha"** localizado **obrigatoriamente abaixo do botão Entrar** no DOM, prevenindo a quebra de navegação por teclado (`Tab` -> `Enter`).

## 5. Dependências
- `apps.core`
- `django.contrib.auth`
