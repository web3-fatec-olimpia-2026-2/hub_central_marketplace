# Os códigos foram gerados com auxilio de I.A.

# Início da docstring de módulo: documenta a finalidade e referências do arquivo.
"""
ASGI config for hub project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""
# Fim da docstring de documentação inicial.

# Importa o módulo nativo 'os' do Python para interagir com variáveis de ambiente e o sistema operacional.
import os

# Importa a função utilitária 'get_asgi_application' do Django, responsável por inicializar o manipulador de requisições assíncronas.
from django.core.asgi import get_asgi_application

# Define a variável de ambiente 'DJANGO_SETTINGS_MODULE' apontando para 'hub.settings', garantindo que o Django carregue as configurações do projeto caso ainda não tenham sido definidas.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Invoca a inicialização do Django e expõe o objeto executável 'application' compatível com a especificação ASGI (consumido por servidores como Uvicorn ou Daphne).
application = get_asgi_application()