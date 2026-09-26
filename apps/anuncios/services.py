# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo logging para registrar eventos, avisos e erros operacionais da aplicação
import logging

# Importa a classe Decimal para manipulação financeira e cálculos de precisão sem erros de ponto flutuante
from decimal import Decimal

# Importa tipagens estáticas da biblioteca typing para clareza de contratos em parâmetros e retornos
from typing import Dict, Any, Optional, Tuple, List

# Importa o gerenciador de transações do Django para garantir atomicidade no banco de dados (rollback/commit)
from django.db import transaction

# Importa o utilitário timezone para obter timestamps consistentes e com fuso horário correto
from django.utils import timezone

# Importa as entidades de persistência de credencial de marketplace e as tabelas de logs de sincronização e auditoria
from apps.marketplaces.models import ContaMarketplace, LogSincronizacao, LogAuditoria

# Importa os enums que padronizam os identificadores de canais de marketplace e os tipos de eventos de auditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum

# Importa a entidade central de inventário de produtos físicos do catálogo
from apps.catalogo.models import Produto

# Importa os modelos de Anúncio e da Composição/Ficha Técnica (kits e relações multiproduto)
from apps.anuncios.models import Anuncio, AnuncioComposicao

# Inicializa o registrador de log atribuindo a ele o namespace do módulo atual (__name__)
logger = logging.getLogger(__name__)


# Classe de serviço responsável por orquestrar a carga de anúncios originados nos canais integrados
class AnuncioImportacaoService:
    # Bloco descritivo documentando o papel arquitetural, idempotência, segurança e multi-tenancy da classe
    """
    O QUE FAZ: Orquestra o fluxo de importação e conciliação de anúncios externos no Hub.
    POR QUE FAZ: Conecta o conector de cada marketplace à base relacional, garantindo idempotência
                 (update_or_create) e auto-vinculação com produtos físicos por correspondência de SKU.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Vincula todos os anúncios exclusivamente à ContaMarketplace e Loja do tenant.
    """

    # Método de classe para executar a extração de anúncios da conta e a consolidação no banco local
    @classmethod
    def importar_anuncios_da_conta(
        cls,
        conta: ContaMarketplace,
        associar_produtos_por_sku: bool = True,
        usuario=None,
        search_type: Optional[str] = None
    ) -> Dict[str, Any]:
        # Documenta a finalidade da função e o tipo de retorno estruturado
        """
        Executa a importação completa dos anúncios da conta e persiste na tabela Anuncio.
        """
        # Validação defensiva: se o objeto de conta for inexistente ou não tiver chave primária persistida
        if not conta or not conta.pk:
            # Retorna imediatamente status de falha com contagem zerada de processamento
            return {"sucesso": False, "mensagem": "Conta de marketplace inválida.", "total": 0}

        # Instancia o conector específico do marketplace vinculado à conta (ex: MercadoLivreConnector)
        connector = conta.get_connector()
        # Verifica se o conector obtido implementa fisicamente o método 'importar_anuncios'
        if not hasattr(connector, 'importar_anuncios'):
            # Retorna estrutura de erro informando a ausência do recurso para o canal correspondente
            return {
                "sucesso": False,
                "mensagem": f"O conector para {conta.get_canal_display()} não implementa importação de anúncios.",
                "total": 0,
            }

        # Invoca a chamada externa ao conector do canal, repassando o tipo de filtro/busca desejado
        resultado_conector = connector.importar_anuncios(search_type=search_type)
        # Se o conector retornar erro na comunicação remota ou nas credenciais
        if not resultado_conector.get('sucesso'):
            # Propaga o dicionário de erro retornado pela chamada externa
            return resultado_conector

        # Extrai a lista de itens normalizados obtida a partir do payload retornado pelo canal
        itens_retornados = resultado_conector.get('itens', [])
        # Inicializa o contador de novos anúncios criados no banco de dados local
        criados = 0
        # Inicializa o contador de anúncios preexistentes que receberam atualização
        atualizados = 0
        # Inicializa o totalizador de anúncios automaticamente associados a produtos físicos por SKU
        vinculados = 0

        # Inicia um bloco de transação atômica para garantir que todas as inserções e logs ocorram com integridade
        with transaction.atomic():
            # Itera sequencialmente sobre cada anúncio tratado e retornado pela integração
            for item in itens_retornados:
                # Recupera o identificador único fornecido pelo marketplace (ex: MLB...)
                item_id = item.get('item_id_externo')
                # Ignora o registro caso o identificador externo venha nulo ou vazio
                if not item_id:
                    continue

                # Extrai o código SKU de identificação do lojista informado no anúncio
                sku_vendedor = item.get('sku_vendedor')
                # Se o SKU estiver presente, remove espaços em branco residuais no início e no final
                if sku_vendedor:
                    sku_vendedor = sku_vendedor.strip()

                # Monta o dicionário de valores padrão a serem gravados ou atualizados no modelo Anuncio
                defaults = {
                    # Título da oferta ou fallback genérico contendo o ID externo
                    'titulo': item.get('titulo', f"Anúncio {item_id}"),
                    # Preço de venda normalizado para Decimal
                    'preco_venda': item.get('preco', Decimal('0.00')),
                    # Converte a quantidade disponível para número inteiro positivo ou zero (clamping)
                    'estoque_publicado': max(0, int(item.get('quantidade_disponivel', 0))),
                    # Status comercial reportado na API (ex: active, paused)
                    'status': item.get('status', 'active'),
                    # SKU comercial do lojista já sanitizado
                    'sku_vendedor': sku_vendedor,
                    # Link da imagem miniatura
                    'thumbnail': item.get('thumbnail'),
                    # URL pública de acesso ao anúncio na plataforma
                    'permalink': item.get('permalink'),
                }

                # Executa operação idempotente de inserção ou atualização filtrando pela tupla única (conta + ID externo)
                anuncio, created = Anuncio.objects.update_or_create(
                    conta=conta,
                    item_id_externo=item_id,
                    defaults=defaults
                )

                # Incrementa contadores de acordo com a operação executada
                if created:
                    criados += 1
                else:
                    atualizados += 1

                # Vínculo automático inicial 1:1 por SKU físico caso exista na mesma loja
                # Avalia se a auto-associação por SKU está ativa e se o item importado possui SKU de vendedor
                if associar_produtos_por_sku and sku_vendedor:
                    # Somente associa automaticamente se o anúncio ainda não possuir nenhuma composição vinculada
                    if not anuncio.itens_composicao.exists():
                        # Consulta o catálogo buscando produto físico com correspondência exata de SKU (case-insensitive) na mesma Loja
                        produto_fisico = Produto.objects.filter(
                            loja=conta.loja,
                            sku__iexact=sku_vendedor
                        ).first()
                        # Se encontrou produto físico correspondente no catálogo do lojista
                        if produto_fisico:
                            # Cria o registro de composição 1:1 amarrando 1 unidade física ao anúncio importado
                            AnuncioComposicao.objects.create(
                                anuncio=anuncio,
                                produto=produto_fisico,
                                quantidade=1
                            )
                            # Incrementa o totalizador de anúncios vinculados com sucesso
                            vinculados += 1

            # Log de auditoria
            # Registra na trilha de auditoria o evento de sincronização/publicação em lote
            LogAuditoria.objects.create(
                # Loja proprietária da conta do marketplace
                loja=conta.loja,
                # Usuário que disparou a importação (ou nulo se for agendamento)
                autor=usuario,
                # Tipo do evento conforme enum de auditoria
                evento=EventoAuditoriaEnum.PUBLICACAO_ANUNCIO,
                # Texto detalhado consolidando as métricas de criação, alteração e vinculações efetuadas
                detalhes=(
                    f"Importação de anúncios do canal {conta.get_canal_display()} concluída. "
                    f"Total: {criados + atualizados} ({criados} novos, {atualizados} atualizados, "
                    f"{vinculados} auto-vinculados por SKU físico)."
                )
            )

        # Monta a mensagem descritiva de conclusão do processamento
        msg = (
            f"Importação de anúncios concluída com sucesso! "
            f"{criados + atualizados} anúncios processados ({criados} novos, {atualizados} atualizados"
        )
        # Adiciona complemento à mensagem caso vínculos automáticos tenham sido realizados
        if vinculados:
            msg += f", {vinculados} auto-vinculados a produtos físicos)."
        # Caso nenhum vínculo tenha sido feito, encerra os parênteses
        else:
            msg += ")."

        # Retorna o resumo consolidado da importação
        return {
            "sucesso": True,
            "mensagem": msg,
            "total": criados + atualizados,
            "total_importados": criados,
            "total_atualizados": atualizados,
            "total_vinculados": vinculados,
        }


# Classe de serviço para controle de sincronização de dados de estoque e preço
class AnuncioSincronizacaoService:
    # Documentação detalhando o propósito, regras defensivas, Circuit Breaker e multi-tenancy da classe
    """
    O QUE FAZ: Orquestra a sincronização segura de estoque e preço entre os produtos físicos (catálogo)
                 e os anúncios dos marketplaces (Mercado Livre, etc.).
    POR QUE FAZ: Aplica cálculo de cotas para kits, idempotência para evitar chamadas de rede redundantes,
                 clamping defensivo e Circuit Breaker contra variações de preço anômalas ou zeramento em lote acidental.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR; Sistema (disparado via Signals / Tarefas).
    MULTI-TENANCY: Todos os cálculos e sincronizações respeitam estritamente a Loja/Conta do anúncio.
    """

    # Limites de segurança do Circuit Breaker
    # Percentual máximo de desconto permitido sem aprovação forçada manual (50%)
    MAX_QUEDA_PRECO_PERCENTUAL = Decimal('0.50')   # 50% de queda máxima permitida sem override
    # Percentual máximo de acréscimo permitido sem aprovação forçada manual (100%)
    MAX_ALTA_PRECO_PERCENTUAL = Decimal('1.00')    # 100% de alta máxima permitida sem override
    # Quantidade máxima de anúncios permitida zerar simultaneamente em uma execução em lote
    LIMITE_ZERAMENTO_LOTE_ITENS = 5                # Mais de 5 itens zerando ao mesmo tempo
    # Proporção máxima do catálogo que pode zerar simultaneamente em um mesmo lote
    LIMITE_ZERAMENTO_LOTE_PERCENTUAL = 0.50        # Mais de 50% dos itens ativos zerando ao mesmo tempo

    # Método estático de utilidade para recalcular a cota vendável do anúncio pelo ID
    @classmethod
    def recalcular_cota(cls, anuncio_id: int) -> int:
        """Calcula a cota máxima disponível a partir dos produtos vinculados na composição."""
        # Busca a instância do anúncio no banco de dados pela chave primária
        anuncio = Anuncio.objects.get(pk=anuncio_id)
        # Calcula a cota disponível garantindo que o número não seja negativo (clamping)
        return max(0, anuncio.calcular_cota_disponivel())

    # Método que implementa as regras do Circuit Breaker para oscilações bruscas de preço
    @classmethod
    def validar_variacao_preco(cls, anuncio: Anuncio, novo_preco: Decimal, forcar: bool = False) -> Tuple[bool, str]:
        # Documentação detalhando a regra de proteção contra prejuízos operacionais
        """
        O QUE FAZ: Valida se o novo preço não apresenta oscilação anômala que indique erro operacional.
        POR QUE FAZ: Circuit breaker para evitar prejuízos por precificação incorreta (queda > 50% ou alta > 100%).
        """
        # Converte a entrada para Decimal tipado de forma segura
        novo_preco = Decimal(str(novo_preco))
        # Rejeita imediatamente valores menores ou iguais a zero
        if novo_preco <= Decimal('0.00'):
            return False, "Preço de venda deve ser estritamente positivo (maior que zero)."

        # Se a flag de força (override manual de operador) for enviada, pula as travas
        if forcar:
            return True, "Variação de preço autorizada por override explícito."

        # Obtém o preço atual já cadastrado no anúncio
        preco_atual = anuncio.preco_venda
        # Se não houver preço anterior cadastrado ou se for nulo, autoriza a primeira precificação
        if not preco_atual or preco_atual <= Decimal('0.00'):
            return True, "Preço inicial aprovado."

        # Avalia se a alteração representa uma redução de preço
        if novo_preco < preco_atual:
            # Calcula o percentual da queda em relação ao preço anterior
            queda = (preco_atual - novo_preco) / preco_atual
            # Se a redução for superior a 50%, dispara o bloqueio do Circuit Breaker
            if queda > cls.MAX_QUEDA_PRECO_PERCENTUAL:
                return False, (
                    f"Circuit Breaker acionado: Queda anômala de preço de {queda * 100:.1f}% "
                    f"(De R$ {preco_atual:.2f} para R$ {novo_preco:.2f}). "
                    f"Variação permitida sem confirmação explícita é de até 50%."
                )
        # Avalia se a alteração representa um aumento de preço
        elif novo_preco > preco_atual:
            # Calcula a proporção do aumento em relação ao preço anterior
            alta = (novo_preco - preco_atual) / preco_atual
            # Se o aumento superar 100%, aciona a proteção de segurança
            if alta > cls.MAX_ALTA_PRECO_PERCENTUAL:
                return False, (
                    f"Circuit Breaker acionado: Aumento anômalo de preço de {alta * 100:.1f}% "
                    f"(De R$ {preco_atual:.2f} para R$ {novo_preco:.2f}). "
                    f"Variação permitida sem confirmação explícita é de até 100%."
                )

        # Se as variações estiverem dentro das margens permitidas, aprova a modificação
        return True, "Preço aprovado pelo Circuit Breaker."

    # Validador para proteção contra falhas em lote que zerem o estoque de múltiplos anúncios simultaneamente
    @classmethod
    def validar_zeramento_em_lote(cls, total_itens_lote: int, total_zerando: int, forcar: bool = False) -> Tuple[bool, str]:
        # Documenta a proteção contra paralisia acidental de estoque
        """
        O QUE FAZ: Avalia se uma operação em lote resultará em zeramento simultâneo massivo de inventário.
        POR QUE FAZ: Previne paralisia acidental de vendas por inconsistências de rede ou integrações externas.
        """
        # Se for override explícito por operador autorizado, libera a operação
        if forcar:
            return True, "Zeramento em lote autorizado por override explícito."

        # Avalia se o número absoluto de itens zerando excede 5, ou se representa mais de 50% do lote enviado
        if total_zerando > cls.LIMITE_ZERAMENTO_LOTE_ITENS or (
            total_itens_lote > 1 and (total_zerando / total_itens_lote) > cls.LIMITE_ZERAMENTO_LOTE_PERCENTUAL
        ):
            # Retorna falso bloqueando a operação e informando a métrica em risco
            return False, (
                f"Circuit Breaker acionado: Tentativa de zeramento em massa de {total_zerando} anúncios "
                f"em um lote de {total_itens_lote} itens bloqueada para proteção de vendas."
            )

        # Autoriza a continuidade caso esteja abaixo dos gatilhos do Circuit Breaker
        return True, "Zeramento em lote aprovado."

    # Método que sincroniza o saldo de estoque físico calculado com o canal de venda
    @classmethod
    def sincronizar_estoque_anuncio(
        cls,
        anuncio: Anuncio,
        usuario=None,
        forcar: bool = False
    ) -> Dict[str, Any]:
        # Documentação descrevendo a lógica de cota física e despacho de saldo
        """
        O QUE FAZ: Recalcula a cota física disponível e atualiza o saldo de estoque no marketplace.
        POR QUE FAZ: Garante que anúncios unitários e kits reflitam com exatidão o inventário real.
        """
        # Checagem de segurança validando se o anúncio fornecido é válido e existente
        if not anuncio or not anuncio.pk:
            return {"sucesso": False, "mensagem": "Anúncio inválido para sincronização.", "estoque": 0}

        # 1. Recálculo da cota física disponível com clamping defensivo
        # Recalcula a cota vendável do anúncio e aplica clamp para impedir números negativos
        cota_calculada = max(0, anuncio.calcular_cota_disponivel())

        # 2. Otimização por idempotência (evita requisição externa redundante)
        # Se não for forçado e o saldo remoto for idêntico à cota calculada e o anúncio estiver ativo
        if not forcar and anuncio.estoque_publicado == cota_calculada and anuncio.status == 'active':
            # Aborta o envio de rede desnecessário e retorna resposta positiva idempotente
            return {
                "sucesso": True,
                "mensagem": f"Estoque já sincronizado ({cota_calculada} un). Requisição ignorada por idempotência.",
                "estoque_sincronizado": cota_calculada,
                "ignorado_idempotencia": True,
            }

        # 3. Disparo via conector do marketplace
        # Recupera o conector correspondente à conta integrada
        connector = anuncio.conta.get_connector()
        # Envia a instrução de atualização de estoque para o endpoint da API externa
        sucesso, msg, log = connector.atualizar_estoque(anuncio.item_id_externo, cota_calculada, usuario=usuario)

        # Se o canal externo aceitar a atualização
        if sucesso:
            # Atualiza o snapshot do estoque publicado local
            anuncio.estoque_publicado = cota_calculada
            # Persiste os campos no banco atualizando também o timestamp de modificação
            anuncio.save(update_fields=['estoque_publicado', 'atualizado_em'])

        # Retorna o resultado final da sincronização de estoque
        return {
            "sucesso": sucesso,
            "mensagem": msg,
            "estoque_sincronizado": cota_calculada,
            "log": log,
            "ignorado_idempotencia": False,
        }

    # Método que valida regras e propaga alterações de preço para o canal remoto
    @classmethod
    def sincronizar_preco_anuncio(
        cls,
        anuncio: Anuncio,
        novo_preco: Decimal,
        usuario=None,
        forcar: bool = False
    ) -> Dict[str, Any]:
        # Documentação descrevendo as etapas de validação de Circuit Breaker e propagação de preço
        """
        O QUE FAZ: Valida regras de segurança e sincroniza o preço de venda no marketplace externo.
        POR QUE FAZ: Previne precificação errônea via Circuit Breaker e propaga novos valores aprovados.
        """
        # Checagem de segurança da integridade do anúncio
        if not anuncio or not anuncio.pk:
            return {"sucesso": False, "mensagem": "Anúncio inválido para sincronização.", "preco": Decimal('0.00')}

        # Converte o novo preço para instância de Decimal
        novo_preco = Decimal(str(novo_preco))

        # 1. Validação de segurança via Circuit Breaker
        # Executa a validação de oscilação brusca de preço
        ok_cb, msg_cb = cls.validar_variacao_preco(anuncio, novo_preco, forcar=forcar)
        # Se a validação for reprovada pelo Circuit Breaker
        if not ok_cb:
            # Registra log de auditoria formalizando o bloqueio de segurança
            LogAuditoria.objects.create(
                loja=anuncio.conta.loja,
                autor=usuario,
                evento=EventoAuditoriaEnum.SYNC_PRECO,
                detalhes=f"Bloqueio de Circuit Breaker no anúncio [{anuncio.item_id_externo}]: {msg_cb}"
            )
            # Retorna estrutura informando o bloqueio preventivo da operação
            return {
                "sucesso": False,
                "mensagem": msg_cb,
                "bloqueado_circuit_breaker": True,
                "preco_sincronizado": anuncio.preco_venda,
            }

        # 2. Otimização por idempotência
        # Se o preço atual do anúncio já for idêntico ao novo preço proposto e não for chamada forçada
        if not forcar and anuncio.preco_venda == novo_preco:
            # Ignora a requisição de rede e retorna status idempotente
            return {
                "sucesso": True,
                "mensagem": f"Preço já sincronizado (R$ {novo_preco:.2f}). Requisição ignorada por idempotência.",
                "preco_sincronizado": novo_preco,
                "ignorado_idempotencia": True,
            }

        # 3. Disparo via conector
        # Obtém o conector do canal da conta
        connector = anuncio.conta.get_connector()
        # Dispara a requisição de ajuste de preço na API do marketplace
        sucesso, msg, log = connector.atualizar_preco(anuncio.item_id_externo, novo_preco, usuario=usuario)

        # Se a atualização for confirmada pelo marketplace
        if sucesso:
            # Atualiza o preço de venda local
            anuncio.preco_venda = novo_preco
            # Persiste os campos de preço e data no banco
            anuncio.save(update_fields=['preco_venda', 'atualizado_em'])

        # Retorna o resultado consolidado da alteração de preço
        return {
            "sucesso": sucesso,
            "mensagem": msg,
            "preco_sincronizado": novo_preco,
            "log": log,
            "ignorado_idempotencia": False,
        }

    # Método que recebe um produto do catálogo físico e sincroniza todos os anúncios que o utilizam
    @classmethod
    def sincronizar_anuncios_do_produto(
        cls,
        produto: Produto,
        usuario=None,
        apenas_estoque: bool = False,
        forcar: bool = False
    ) -> Dict[str, Any]:
        # Documentação descrevendo o acionamento em cadeia a partir de mutações de produto físico
        """
        O QUE FAZ: Identifica todos os anúncios vinculados ao produto no catálogo (unitários e kits)
                     e dispara a sincronização segura correspondente.
        POR QUE FAZ: Acionado automaticamente por Django Signals após alteração de estoque ou preço no produto mestre.
        """
        # Consulta todos os anúncios que utilizam o produto físico em suas composições
        anuncios = Anuncio.objects.filter(
            composicoes__produto=produto
        # Pré-carrega relações da conta e loja e elimina duplicações de instâncias
        ).select_related('conta', 'conta__loja').distinct()

        # Lista para coletar os resultados de atualização de estoque
        resultados_estoque = []
        # Lista para coletar os resultados de atualização de preço
        resultados_preco = []

        # Itera por cada anúncio dependente do produto
        for anuncio in anuncios:
            # Sincroniza estoque recalculado para o anúncio
            # Executa a sincronização segura de estoque
            res_est = cls.sincronizar_estoque_anuncio(anuncio, usuario=usuario, forcar=forcar)
            # Armazena o feedback na lista de resultados
            resultados_estoque.append({"anuncio_id": anuncio.pk, "item_id": anuncio.item_id_externo, "resultado": res_est})

            # Se não for apenas estoque e o anúncio for unitário (1:1 com o produto), propaga o preço atualizado
            # Se a sincronização não for restrita a estoque, avalia se pode sincronizar preço
            if not apenas_estoque:
                # Obtém a lista dos itens da composição do anúncio
                itens = list(anuncio.itens_composicao.all())
                # Propaga preço apenas se for um item simples (1 componente, mesmo produto e quantidade igual a 1)
                if len(itens) == 1 and itens[0].produto_id == produto.pk and itens[0].quantidade == 1:
                    # Sincroniza o novo preço do produto mestre no anúncio correspondente
                    res_prc = cls.sincronizar_preco_anuncio(anuncio, produto.preco, usuario=usuario, forcar=forcar)
                    # Registra o resultado da atualização de preço
                    resultados_preco.append({"anuncio_id": anuncio.pk, "item_id": anuncio.item_id_externo, "resultado": res_prc})

        # Retorna o sumário completo de todos os anúncios atualizados
        return {
            "total_anuncios": anuncios.count(),
            "resultados_estoque": resultados_estoque,
            "resultados_preco": resultados_preco,
        }


# Alias de compatibilidade
# Atribui um alias para manter compatibilidade com códigos ou imports legados
SincronizacaoAnuncioService = AnuncioSincronizacaoService

