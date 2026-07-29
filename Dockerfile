# =============================================================================
# Dockerfile — WakeOnCasa Dashboard & WoL Engine para CasaOS
# =============================================================================

FROM python:3.12-slim

LABEL org.opencontainers.image.title="WakeOnCasa"
LABEL org.opencontainers.image.description="Painel de Wake-on-LAN e monitoramento de ativos para CasaOS"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV DATA_DIR=/app/data

# Instala dependências de sistema para ferramentas de rede
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    net-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação e arquivos estáticos
COPY backend/ backend/
COPY static/ static/

# Cria diretório de persistência de dados
RUN mkdir -p /app/data

# Porta exposta para o CasaOS Dashboard
EXPOSE 8089

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8089/api/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8089"]
