# ==============================================================================
# Dockerfile for building the ECLI .rpm package (AlmaLinux 9 for broad RHEL compat)
# ==============================================================================

FROM almalinux:9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Toolchain + Python 3.11 + Ruby/fpm + RPM build tooling
# (A→Z sorting, weak deps disabled, cache cleanup)
# Toolchain + Python 3.11 + Ruby/fpm + RPM build tooling
RUN dnf -y --setopt=install_weak_deps=False install \
      file \
      gcc \
      gcc-c++ \
      git \
      make \
      python3.11 \
      python3.11-devel \
      python3.11-pip \
      redhat-rpm-config \
      rpm-build \
      rpmdevtools \
      ruby \
      ruby-devel \
      rubygem-json \
      tar \
      which \
  && dnf clean all \
  && rm -rf /var/cache/dnf

# Install fpm via RubyGems
RUN gem install --no-document fpm

# Install uv and expose it on PATH
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && ln -s /root/.local/bin/uv /usr/local/bin/uv
ENV PATH="/root/.local/bin:${PATH}"

# Force uv to use Python 3.11 (EL9 default python3 may be 3.9)
ENV UV_PYTHON=python3.11

# Switch system `python3` alternative to Python 3.11 if available
RUN alternatives --set python3 /usr/bin/python3.11 || true

WORKDIR /app

# Cache layer with project metadata only
COPY pyproject.toml ./

# Only install the tools required to build the bundle
RUN python3.11 -m ensurepip --upgrade || true \
 && python3.11 -m pip install --upgrade pip wheel \
 && uv --version \
 && uv pip install --system --python python3.11 \
      pyinstaller \
      ruff \
 && uv pip install --system --python python3.11 \
      aiohttp \
      aiosignal \
      chardet \
      frozenlist \
      multidict \
      pygments \
      pyperclip \
      python-dotenv \
      tato \
      toml \
      wcwidth \
      yarl



# Project sources
COPY . .

RUN chmod +x scripts/build-and-package-rpm.sh

CMD ["bash", "-lc", "./scripts/build-and-package-rpm.sh"]
