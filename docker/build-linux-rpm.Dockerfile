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

# uv in PATH
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv
ENV PATH="/root/.local/bin:${PATH}"

# Explicitly force uv to use Python 3.11 (otherwise, on EL9 it will use the system 3.9)
ENV UV_PYTHON=python3.11

# Switch python3 -> 3.11
RUN alternatives --set python3 /usr/bin/python3.11 || true

WORKDIR /app

# ----Cache layer with metadata only (don't include requirements inside)
COPY pyproject.toml ./

# IMPORTANT:
# Do not install requirements.txt/requirements-dev.txt - it may contain entries
# incompatible with Py 3.11 (for example, pyyaml-ft>=8, which requires Py>=3.13),
# or reference local host paths. This is NOT needed for building the bundle.
# Install only PyInstaller and any explicitly required runtime dependencies.
RUN python3.11 -m ensurepip --upgrade || true \
    && python3.11 -m pip install --upgrade pip wheel \
    && uv --version \
    && uv pip install --system --python python3.11 pyinstaller \
    # Runtime deps for bundling (must match those in the deb build)
    && uv pip install --system --python python3.11 \
    aiohttp aiosignal yarl multidict frozenlist \
    python-dotenv toml chardet \
    pyperclip wcwidth pygments tato

# ---- Project sources
COPY . .

RUN chmod +x scripts/build-and-package-rpm.sh

CMD ["bash", "-lc", "./scripts/build-and-package-rpm.sh"]
