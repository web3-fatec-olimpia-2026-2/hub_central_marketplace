# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo 'sys' para leitura de argumentos de linha de comando e retorno do código de saída do processo
import sys

# Importa o módulo nativo 'os' para interações e operações com o sistema operativo
import os

# Importa a classe 'Path' do módulo 'pathlib' para manipulação orientada a objetos de ficheiros e pastas
from pathlib import Path

# Resolve o caminho absoluto da pasta-mãe do diretório atual, apontando para a raiz do repositório
BASE_DIR = Path(__file__).resolve().parent.parent

# Define o formato do comentário de cabeçalho padrão para linguagens com suporte a cardinal (#)
HEADER_PYTHON = "# Os códigos foram gerados com auxilio de I.A."

# Define o formato do comentário de cabeçalho padrão compatível com sintaxe de marcação HTML
HEADER_HTML = "<!-- Os códigos foram gerados com auxilio de I.A. -->"

# Define o formato do comentário de cabeçalho padrão em bloco para ficheiros de estilo CSS e JavaScript
HEADER_CSS_JS = "/* Os códigos foram gerados com auxilio de I.A. */"

# Dicionário que mapeia a extensão do ficheiro ao respetivo formato textual de cabeçalho obrigatório
HEADER_MAP = {
    # Mapeia ficheiros Python para a versão com cardinal (#)
    ".py": HEADER_PYTHON,
    # Mapeia ficheiros de script shell (Bash/Sh) para a versão com cardinal (#)
    ".sh": HEADER_PYTHON,
    # Mapeia ficheiros de exemplo de variáveis de ambiente para a versão com cardinal (#)
    ".env.example": HEADER_PYTHON,
    # Mapeia ficheiros de configuração YAML padrão para a versão com cardinal (#)
    ".yaml": HEADER_PYTHON,
    # Mapeia ficheiros YAML com extensão abreviada para a versão com cardinal (#)
    ".yml": HEADER_PYTHON,
    # Mapeia páginas e templates HTML para a sintaxe de comentário HTML
    ".html": HEADER_HTML,
    # Mapeia folhas de estilo CSS para a sintaxe de comentário de bloco (/* */)
    ".css": HEADER_CSS_JS,
    # Mapeia scripts de front-end JavaScript para a sintaxe de comentário de bloco (/* */)
    ".js": HEADER_CSS_JS,
}

# Conjunto imutável de diretórios que devem ser totalmente ignorados pela rotina de auditoria
IGNORE_DIRS = {
    # Ignora ambientes virtuais isolados do Python e pastas de metadados do Git
    ".venv", "venv", ".git", "__pycache__", "migrations", ".system_generated",
    # Ignora pastas de configuração das IDEs (PyCharm/VSCode), estáticos recolhidos e dependências Node
    ".idea", ".vscode", "static_collected", "node_modules"
}

# Conjunto de nomes de ficheiros que não devem receber o comentário de conformidade
IGNORE_FILES = {
    # Ignora ficheiros de configuração do Git, a base SQLite compilada e a lista de pacotes pip
    ".gitignore", "db.sqlite3", "requirements.txt"
}


# Assinatura da função que valida se um caminho específico deve ou não ser analisado pelo script
def should_process(file_path: Path) -> bool:
    # Itera por cada segmento/diretório que compõe o caminho completo do ficheiro
    for part in file_path.parts:
        # Se qualquer parte do caminho pertencer à lista de pastas ignoradas, descarta a validação
        if part in IGNORE_DIRS:
            # Retorna falso para sinalizar a exclusão imediata do diretório
            return False
    # Avalia se o nome exato do ficheiro consta na lista de ficheiros dispensados
    if file_path.name in IGNORE_FILES:
        # Retorna falso para não processar ficheiros específicos como a base de dados SQLite
        return False
    # Valida se a extensão do ficheiro está contemplada no mapa de extensões monitorizadas
    if file_path.suffix in HEADER_MAP:
        # Retorna verdadeiro autorizando a análise do ficheiro
        return True
    # Tratamento especial para o ficheiro '.env.example', cuja extensão sufixal pode vir vazia
    if file_path.name == ".env.example":
        # Retorna verdadeiro para garantir a auditoria deste ficheiro de modelo de variáveis
        return True
    # Retorna falso caso a extensão não esteja prevista em nenhuma regra anterior
    return False


# Assinatura da função que averigua a presença da declaração textual nas primeiras linhas do ficheiro
def has_ai_header(content: str, ext: str) -> bool:
    # Obtém o cabeçalho esperado a partir da extensão mapeada no dicionário
    expected = HEADER_MAP.get(ext, "")
    # Caso a extensão não exija cabeçalho configurado, considera a validação satisfeita
    if not expected:
        # Retorna verdadeiro por ausência de regra restritiva
        return True
    # Isola as primeiras 5 linhas do ficheiro sem espaços residuais para conferência do topo
    first_lines = "\n".join(content.strip().splitlines()[:5])
    # Avalia se a string chave declarativa de auxílio de IA consta entre essas 5 primeiras linhas
    if "Os códigos foram gerados com auxilio de I.A." in first_lines:
        # Retorna verdadeiro confirmando que o ficheiro já está em conformidade
        return True
    # Retorna falso caso a mensagem declarativa não seja encontrada no topo do ficheiro
    return False


# Assinatura da função encarregue de injetar fisicamente o cabeçalho no topo do ficheiro ausente
def apply_ai_header(file_path: Path) -> bool:
    # Inicia bloco protegido para tratamento de erros de leitura no sistema de ficheiros
    try:
        # Executa a leitura integral do conteúdo do ficheiro com codificação UTF-8
        content = file_path.read_text(encoding="utf-8")
    # Captura eventuais exceções de permissão ou formato inválido na tentativa de leitura
    except Exception as exc:
        # Notifica no ecrã o erro detalhado que impediu a abertura do ficheiro
        print(f"Erro ao ler {file_path}: {exc}")
        # Aborta a alteração retornando falso
        return False

    # Extrai o sufixo (extensão) associado ao ficheiro
    ext = file_path.suffix
    # Normaliza a extensão para '.env.example' se o nome do ficheiro for idêntico e não possuir extensão sufixada
    if ext == "" and file_path.name == ".env.example":
        # Atribui o identificador específico para busca no mapa de cabeçalhos
        ext = ".env.example"

    # Se o conteúdo já possuir o cabeçalho de IA, não realiza nenhuma gravação redundante
    if has_ai_header(content, ext):
        # Encerra sem modificações retornando falso
        return False

    # Recupera a string de cabeçalho correta associada à extensão identificada
    header = HEADER_MAP.get(ext, "")
    # Se não houver formato de comentário compatível registado, aborta a operação
    if not header:
        # Retorna falso indicando que a mutação não é aplicável
        return False

    # Monta a nova estrutura do documento intercalando o cabeçalho com uma quebra de linha antes do código original
    new_content = f"{header}\n{content}"
    # Escreve o conteúdo atualizado no disco sobrescrevendo o ficheiro com codificação UTF-8
    file_path.write_text(new_content, encoding="utf-8")
    # Retorna verdadeiro indicando que a injeção do cabeçalho foi efetuada com sucesso
    return True


# Assinatura da função principal de varredura que percorre os diretórios alvo
def check_all_files(target_dirs=None, auto_apply=False):
    # Inicializa o conjunto padrão de pastas e ficheiros a rastrear caso nenhum seja passado explicitamente
    if target_dirs is None:
        # Define os componentes centrais do projeto a serem auditados
        target_dirs = ["apps", "hub", "templates", "scripts", "manage.py"]

    # Lista que acumulará os ficheiros identificados sem o cabeçalho obrigatório
    missing = []
    # Lista que acumulará os ficheiros alterados automaticamente quando a flag auto_apply estiver ativa
    applied = []
    # Contador de ficheiros avaliados pelo script
    checked_count = 0

    # Percorre sequencialmente cada entrada definida na lista de alvos
    for target in target_dirs:
        # Constrói o caminho completo resolvido a partir da raiz do projeto
        p = BASE_DIR / target
        # Ignora e salta a iteração se o ficheiro ou pasta não existir no ambiente
        if not p.exists():
            # Passa para a próxima entrada da lista
            continue
        # Verifica se a entrada atual representa diretamente um ficheiro isolado (ex.: manage.py)
        if p.is_file():
            # Encapsula o caminho unitário em uma lista para iteração padronizada
            files = [p]
        # Se for um diretório, procede à leitura recursiva
        else:
            # Varre recursivamente todas as subpastas recolhendo apenas os caminhos que forem ficheiros
            files = [f for f in p.rglob("*") if f.is_file()]

        # Itera por cada ficheiro identificado na pasta ou lista unitária
        for f in files:
            # Valida se o ficheiro atual não pertence aos diretórios ou extensões ignoradas
            if not should_process(f):
                # Salta o ficheiro se ele não for legível ou estiver desconsiderado
                continue

            # Incrementa o totalizador de ficheiros que passaram pelo crivo de validação
            checked_count += 1
            # Obtém a extensão sufixal do ficheiro avaliado
            ext = f.suffix
            # Aplica o ajuste de chave para o ficheiro '.env.example' caso venha sem sufixo padrão
            if ext == "" and f.name == ".env.example":
                # Define a chave explícita para obter o comentário correto
                ext = ".env.example"

            # Lê integralmente o conteúdo do ficheiro de texto em modo UTF-8
            content = f.read_text(encoding="utf-8")
            # Verifica se o ficheiro carece da marcação obrigatória de IA
            if not has_ai_header(content, ext):
                # Se o parâmetro de correção automática estiver ativo, injeta a alteração
                if auto_apply:
                    # Executa a escrita do cabeçalho no ficheiro
                    apply_ai_header(f)
                    # Adiciona o ficheiro à lista de itens corrigidos
                    applied.append(f)
                # Caso esteja em modo estrito de validação/checagem apenas
                else:
                    # Adiciona o caminho à listagem de falhas de conformidade
                    missing.append(f)

    # Verifica se houve aplicação automática e se algum ficheiro foi efetivamente alterado
    if auto_apply and applied:
        # Apresenta mensagem informativa listando a quantidade de ficheiros alterados
        print(f"[OK] Cabeçalho de I.A. adicionado em {len(applied)} arquivo(s):")
        # Itera por cada ficheiro modificado com sucesso
        for f in applied:
            # Exibe no terminal o caminho relativo a partir da raiz do repositório
            print(f"  + {f.relative_to(BASE_DIR)}")

    # Avalia se foram identificados ficheiros fora do padrão esperado
    if missing:
        # Exibe mensagem de erro alertando sobre a quantidade de ficheiros pendentes
        print(f"[ERRO] {len(missing)} arquivo(s) sem cabeçalho obrigatório de I.A.:")
        # Itera por cada ficheiro em inconformidade
        for f in missing:
            # Exibe o caminho do ficheiro pendente no ecrã
            print(f"  - {f.relative_to(BASE_DIR)}")
        # Orienta o desenvolvedor a utilizar o parâmetro de correção rápida
        print("\nExecute 'python scripts/check_ai_header.py --apply' para adicionar automaticamente.")
        # Retorna falso indicando que a auditoria identificou falhas
        return False

    # Imprime mensagem de sucesso informando que todo o repositório auditado está em conformidade
    print(f"[SUCESSO] Todos os {checked_count} arquivos verificados possuem o cabeçalho de I.A. em conformidade.")
    # Retorna verdadeiro atestando a integridade das validações
    return True


# Ponto de entrada padrão para execução do script via terminal
if __name__ == "__main__":
    # Inspeciona os argumentos passados para conferir se foi solicitada a aplicação automática (--apply ou -a)
    auto_apply = "--apply" in sys.argv or "-a" in sys.argv
    # Dispara a checagem geral passando a flag de aplicação automática
    success = check_all_files(auto_apply=auto_apply)
    # Encerra o processo do sistema operacional retornando 0 em caso de conformidade ou 1 em caso de falha
    sys.exit(0 if success else 1)