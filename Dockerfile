# Sceglie immagine di base -> Immagine del pilastro: Python 3.12 + dipendenze bloccate in uv.lock. Nessun segreto né appunto dentro.
FROM python:3.12-slim-trixie

# COPY: copia fil edal build context
# uv preso dalla sua immagine ufficiale, versione fissata (stessa famiglia di uv_build nel pyproject)
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /uvx /bin/

#ENV: imposta variabili
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# RUN: esegue comando dopo la build
# 1) Solo le dipendenze: questo strato si ricostruisce solo se cambiano pyproject.toml o uv.lock
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# 2) Il codice del progetto (il .dockerignore tiene fuori .env, appunti e dati)
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# 3) Utente senza privilegi: se qualcosa va storto, dentro il container non è root
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data /app/logs \
    && chown app /app/data /app/logs
USER app
#-> fa girare il contatiner come utente senza privilegi (pratica std di sicurezza)
ENV PATH="/app/.venv/bin:$PATH"
#CMD:comando predefinto all'avvio del container
CMD ["python", "chat_v1.py"] 
