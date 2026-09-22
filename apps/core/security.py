# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o propósito criptográfico, algoritmo e estratégia de chave do módulo
"""
O QUE FAZ: Camada criptográfica em repouso utilizando o padrão Fernet (AES-128-CBC + HMAC-SHA256).
POR QUE FAZ: Protege chaves de API, segredos de aplicação, tokens de sessão OAuth e chaves de validação de webhooks no banco de dados.
SEGURANÇA: Obtém a chave mestra de FIELD_ENCRYPTION_KEY ou deriva deterministicamente a partir de settings.SECRET_KEY via SHA-256.
"""
# Fim do bloco de documentação arquitetural do módulo

# Importa o módulo nativo base64 para manipulação e codificação URL-safe de sequências de bytes
import base64

# Importa o módulo nativo hashlib para geração de resumos criptográficos via algoritmos de hash (SHA-256)
import hashlib

# Importa a cifra simétrica Fernet e a exceção InvalidToken da biblioteca cryptography
from cryptography.fernet import Fernet, InvalidToken

# Importa as configurações globais do projeto Django (settings.py)
from django.conf import settings

# Importa o módulo de modelos ORM do Django para construção de campos customizados de banco de dados
from django.db import models


# Declara a função responsável por instanciar ou derivar a chave simétrica do mecanismo Fernet
def get_fernet_instance() -> Fernet:
    # Início do bloco de docstring que detalha o ciclo de vida da chave e o algoritmo de fallback
    """
    O QUE FAZ: Obtém ou inicializa a cifra simétrica Fernet.
    POR QUE FAZ: Centraliza a derivação e validação da chave de criptografia de campos.
    FALLBACK: Caso FIELD_ENCRYPTION_KEY não esteja configurada ou seja inválida,
              deriva deterministicamente uma chave válida base64 URL-safe de 32 bytes aplicando SHA-256 sobre settings.SECRET_KEY.
    """
    # Fim do bloco de documentação da função

    # Tenta recuperar a variável específica de criptografia de campos a partir das configurações do Django
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)

    # Caso a chave exista e seja uma string, remove possíveis espaços em branco nas extremidades
    if key and isinstance(key, str):
        key = key.strip()

    # Se a chave informada não for vazia
    if key:
        # Inicia bloco protegido para validar se a chave atende aos requisitos estruturais do Fernet
        try:
            # Instancia o objeto Fernet convertendo a string para bytes caso necessário
            return Fernet(key.encode('utf-8') if isinstance(key, str) else key)
        # Captura eventuais erros de padding ou formato inválido na chave fornecida
        except Exception:
            # Ignora a chave inválida e prossegue para a derivação determinística de fallback
            pass

    # Derivação determinística: SHA-256 sobre SECRET_KEY codificada em URL-safe Base64 (32 bytes)
    # Recupera a chave mestra da aplicação (settings.SECRET_KEY) ou utiliza uma constante estática de emergência
    secret = getattr(settings, 'SECRET_KEY', 'hub-marketplaces-default-secret')

    # Garante que o segredo esteja tipado em formato binário de bytes codificado em UTF-8
    if isinstance(secret, str):
        secret = secret.encode('utf-8')

    # Calcula o hash SHA-256 sobre o segredo, obtendo um bloco exato de 32 bytes de entropia
    key_bytes = hashlib.sha256(secret).digest()

    # Converte os 32 bytes resultantes em uma representação Base64 URL-safe compatível com a especificação do Fernet
    derived_key = base64.urlsafe_b64encode(key_bytes)

    # Instancia e retorna o cifrador Fernet com a chave derivada
    return Fernet(derived_key)


# Alias para retrocompatibilidade
# Cria um alias de nome alternativo para manter interoperabilidade com rotinas que utilizam a nomenclatura anterior
get_fernet_cipher = get_fernet_instance


# Declaração do campo customizado herdando de TextField para proteção de dados sensíveis em repouso
class EncryptedTextField(models.TextField):
    # Início do bloco de docstring descrevendo a finalidade de segurança do campo no ORM
    """
    O QUE FAZ: Campo de modelo Django que criptografa strings em UTF-8 com Fernet antes de persistir no banco e decifra ao recuperar.
    POR QUE FAZ: Previne vazamento e exposição de tokens e segredos em repouso (banco de dados, dumps, logs SQL).
    """
    # Fim do bloco de docstring do campo customizado

    # Descrição legível do tipo de campo para exibição em interfaces administrativas ou inspeção de modelos
    description = "Campo de texto com criptografia simétrica Fernet em repouso"

    # Método interceptor do Django executado no momento de preparar o valor para escrita no banco de dados
    def get_prep_value(self, value):
        """Criptografa o texto antes de persistir no banco de dados."""
        # Executa a preparação padrão do TextField original
        value = super().get_prep_value(value)

        # Se o valor a gravar for nulo ou uma string vazia, retorna sem modificações
        if value is None or value == "":
            return value

        # Garante que o valor a ser cifrado seja tratado como string
        if not isinstance(value, str):
            value = str(value)

        # Obtém o cifrador Fernet configurado para o sistema
        cipher = get_fernet_instance()

        # Inicia bloco protegido para tratamento do ciclo de cifragem
        try:
            # Verifica se já está cifrado para evitar dupla encriptação
            # Tenta decifrar o valor atual para avaliar se ele já se encontra criptografado
            try:
                cipher.decrypt(value.encode('utf-8'))
                # Se a decifragem teve sucesso, o dado já é um ciphertext válido; retorna o próprio valor para não cifrar novamente
                return value
            # Caso a decifragem falhe, confirma que o conteúdo é texto plano e precisa ser cifrado
            except (InvalidToken, Exception):
                # Criptografa o texto em UTF-8 gerando o payload autenticado Fernet em bytes
                encrypted_bytes = cipher.encrypt(value.encode('utf-8'))
                # Converte os bytes criptografados de volta em string UTF-8 para persistência no banco
                return encrypted_bytes.decode('utf-8')
        # Em caso de qualquer falha inesperada na manipulação dos dados
        except Exception:
            # Retorna o valor original para evitar perda de dados por bloqueio fatal
            return value

    # Método interceptor chamado pelo ORM do Django ao ler o dado bruto retornado do banco de dados
    def from_db_value(self, value, expression, connection):
        """Descriptografa o texto ao carregar do banco de dados."""
        # Se o valor armazenado no banco for nulo ou vazio, propaga o próprio valor
        if value is None or value == "":
            return value

        # Obtém a instância ativa do cifrador
        cipher = get_fernet_instance()

        # Inicia bloco protegido para tentar a decifragem do ciphertext
        try:
            # Decifra a string obtida do banco de dados convertendo-a para bytes
            decrypted_bytes = cipher.decrypt(value.encode('utf-8'))
            # Converte os bytes decifrados em texto legível formatado em UTF-8
            return decrypted_bytes.decode('utf-8')
        # Captura tokens inválidos ou falhas de formatação (ex.: registros antigos sem criptografia)
        except (InvalidToken, Exception):
            # Fallback gracioso para o valor original caso já esteja em texto plano ou legado
            # Retorna o dado tal como lido do banco, preservando dados legados não cifrados
            return value

    # Método de conversão chamado pelo Django durante validações de formulários e atribuições manuais no modelo
    def to_python(self, value):
        """Garante consistência de decriptografia e compatibilidade no formulário/ORM."""
        # Se o valor for nulo ou vazio, retorna imediatamente
        if value is None or value == "":
            return value

        # Se o valor recebido for uma string
        if isinstance(value, str):
            # Recupera a cifra simétrica Fernet
            cipher = get_fernet_instance()
            # Tenta verificar se o dado recebido é um ciphertext Fernet que precisa ser decifrado
            try:
                decrypted_bytes = cipher.decrypt(value.encode('utf-8'))
                # Retorna a versão decifrada em texto plano
                return decrypted_bytes.decode('utf-8')
            # Se não for um token cifrado válido, deduz que já é o texto plano em memória
            except (InvalidToken, Exception):
                # Retorna o próprio valor textual
                return value

        # Para outros tipos de dados, converte e retorna em formato de string
        return str(value)
