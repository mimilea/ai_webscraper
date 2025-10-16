install:
    CODEARTIFACT_AUTH_TOKEN=$(aws codeartifact get-authorization-token --domain nova-packages --domain-owner 399839194709 --profile nova --query authorizationToken --output text) && \
    uv sync --extra-index-url "https://aws:${CODEARTIFACT_AUTH_TOKEN}@nova-packages-399839194709.d.codeartifact.us-east-1.amazonaws.com/pypi/nova-python-packages/simple/"

add package:
    CODEARTIFACT_AUTH_TOKEN=$(aws codeartifact get-authorization-token --domain nova-packages --domain-owner 399839194709 --query authorizationToken --output text) && \
    uv add {{package}} --extra-index-url "https://aws:${CODEARTIFACT_AUTH_TOKEN}@nova-packages-399839194709.d.codeartifact.us-east-1.amazonaws.com/pypi/nova-python-packages/simple/" && \
    uv sync --extra-index-url "https://aws:${CODEARTIFACT_AUTH_TOKEN}@nova-packages-399839194709.d.codeartifact.us-east-1.amazonaws.com/pypi/nova-python-packages/simple/" && \
    uv pip freeze > requirements.txt
