# ==============================================================================
# Dockerfile for building the ECLI .rpm package (AlmaLinux 9 for max RHEL compat)
# ==============================================================================

FROM almalinux:9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Toolchain + Python 3.11 + Ruby/fpm + rpm-build
RUN dnf -y install \
    python3.11 python3.11-pip python3.11-devel \
    gcc gcc-c++ make git which file \
    ruby ruby-devel rpm-build \
    && dnf clean all

# fpm via gem
RUN gem install --no-document fpm

# uv in PATH (curl-minimal уже в базовом образе)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv
ENV PATH="/root/.local/bin:${PATH}"

# Явно заставляем uv использовать Python 3.11 (иначе на EL9 он цепляет системный 3.9)
ENV UV_PYTHON=python3.11

# (Опционально) переключим python3 -> 3.11
RUN alternatives --set python3 /usr/bin/python3.11 || true

WORKDIR /app

# ---- Cache layer только с метаданными (не будем тянуть requirements внутрь)
COPY pyproject.toml ./

# ВАЖНО:
# Не ставим requirements.txt/requirements-dev.txt — они могут содержать записи,
# несовместимые с Py 3.11 (например, pyyaml-ft>=8, требующий Py>=3.13),
# а также ссылаться на локальные пути хоста. Для сборки бандла это НЕ нужно.
# Ставим только PyInstaller и явно нужные рантайм-зависимости.
RUN python3.11 -m ensurepip --upgrade || true \
    && python3.11 -m pip install --upgrade pip wheel \
    && uv --version \
    && uv pip install --system --python python3.11 pyinstaller \
    # runtime deps for bundling (должны совпадать с тем, что ты добавил в deb-сборку)
    && uv pip install --system --python python3.11 \
    aiohttp aiosignal yarl multidict frozenlist \
    python-dotenv toml chardet \
    pyperclip wcwidth pygments tato

# ---- Project sources
COPY . .

RUN chmod +x scripts/build-and-package-rpm.sh

CMD ["bash", "-lc", "./scripts/build-and-package-rpm.sh"]
