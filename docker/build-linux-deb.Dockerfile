# ==============================================================================
# Dockerfile for building the ECLI .deb package (Debian 11 for max compatibility)
# ==============================================================================

ARG PYTHON_VERSION=3.11
ARG DEBIAN_RELEASE=bullseye
FROM python:${PYTHON_VERSION}-${DEBIAN_RELEASE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System tools + FPM + Python + Ruff (list sorted A→Z)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    file \
    g++ \
    gcc \
    git \
    libncurses-dev \
    libncurses6 \
    libncursesw5-dev \
    libncursesw6 \
    libtinfo6 \
    libyaml-dev \
    make \
    ncurses-bin \
    ncurses-term \
    patchelf \
    python3 \
    python3-pip \
    python3-venv \
    rpm \
    ruby \
    ruby-dev \
    upx-ucl \
    xclip \
    xsel \
 && gem install --no-document fpm \
 && python3 -m pip install --no-cache-dir --upgrade pip \
 && python3 -m pip install --no-cache-dir ruff \
 && rm -rf /var/lib/apt/lists/*



# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# --- Cache dependency layer
COPY pyproject.toml ./
COPY uv.lock* requirements.txt* requirements-dev.txt* ./

RUN python -m pip install --upgrade pip wheel \
    && uv --version \
    && ( [ -f requirements.txt ]      && uv pip install --system -r requirements.txt      || true ) \
    && ( [ -f requirements-dev.txt ]  && uv pip install --system -r requirements-dev.txt  || true ) \
    && uv pip install --system pyinstaller \
    # ensure runtime deps are present during analysis so PyInstaller can bundle them
    && uv pip install --system aiohttp aiosignal yarl multidict frozenlist pyperclip \
    && uv pip install --system python-dotenv toml chardet wcwidth tato pygments ruff

# --- Project sources
COPY . .

RUN chmod +x scripts/build-and-package-deb.sh

# Build package inside the container
CMD ["bash", "-lc", "./scripts/build-and-package-deb.sh"]
