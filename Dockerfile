FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    curl \
    unzip \
    ca-certificates \
    openssl \
    fonts-noto-core \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Deno install (used by supported media extractors)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:$PATH"
RUN deno --version

COPY requirements.txt .
# Remove the legacy Pyrogram distribution if present; it conflicts with PyrogramMod's
# shared `pyrogram` import package and lacks the Telegram API methods PyTgCalls needs.
RUN pip uninstall -y pyrogram pyrogrammod || true
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Fail the image build if Railway resolves the legacy Pyrogram package.
# PyTgCalls 3.0.1 requires the newer PyrogramMod raw API (Layer 229).
RUN python -c "import pyrogram; from pyrogram.raw.functions.phone import CreateConferenceCall; print('PyrogramMod:', pyrogram.__version__, '| CreateConferenceCall: OK')"

COPY . .

CMD ["python", "bot.py"]
