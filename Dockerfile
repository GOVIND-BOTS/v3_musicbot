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
    chromium \
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
    && pip install --no-cache-dir -r requirements.txt \
    && (pip uninstall -y pyrogram || true) \
    && pip install --no-cache-dir --force-reinstall --no-deps pyrogrammod==2.4.1

# Fail the image build unless the exact PyrogramMod raw API required by
# PyTgCalls is available in the final installed environment.
RUN python -c "import pyrogram; print('Pyrogram package version:', pyrogram.__version__); from pyrogram.raw.functions.phone import CreateConferenceCall; print('CreateConferenceCall: OK')"

COPY . .

CMD ["python", "bot.py"]
