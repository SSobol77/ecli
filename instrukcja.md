## DEBIAN

**Выполните следующие шаги**, чтобы собрать релиз **`ecli_0.1.0_amd64.deb`** (и сразу сделать `.sha256`). 

Два варианта: **через Docker (рекомендуется)** и **локально**.

---

### Вариант A — Docker (рекомендуется)

```bash
# 0) Убедись, что версия = 0.1.0 в pyproject.toml
grep -nE '^[[:space:]]*version[[:space:]]*=' pyproject.toml
# при необходимости проставь 0.1.0:
# sed -i 's/^\([[:space:]]*version[[:space:]]*=\).*/\1 "0.1.0"/' pyproject.toml

# 1) (Опционально) зафиксируй версию и тег
git add pyproject.toml
git commit -m "chore(release): bump version to 0.1.0"
git tag -a v0.1.0 -m "ECLI 0.1.0"
git push origin main --tags

# 2) Собери образ сборочной среды (Debian+buildeps)
docker build -f docker/build-linux-deb.Dockerfile \
  --build-arg PYTHON_VERSION=3.11 \
  --build-arg DEBIAN_RELEASE=bullseye \
  -t ecli-deb:py311-bullseye .

# 3) Запусти сборку .deb внутри контейнера
docker run --rm -v "$(pwd):/app" -w /app ecli-deb:py311-bullseye \
  bash -lc "./scripts/build-and-package-deb.sh"

# 4) Сгенерируй SHA256
sha256sum "releases/0.1.0/ecli_0.1.0_amd64.deb" > "releases/0.1.0/ecli_0.1.0_amd64.deb.sha256"

# 5) Проверь результат
ls -la releases/0.1.0/
```

> Короткий путь через Makefile:

```bash
make package-deb-docker
sha256sum releases/0.1.0/ecli_0.1.0_amd64.deb > releases/0.1.0/ecli_0.1.0_amd64.deb.sha256
ls -la releases/0.1.0/
```

---

### Вариант B — Локально (Debian/Ubuntu)

```bash
# 0) Убедись, что версия = 0.1.0
grep -nE '^[[:space:]]*version[[:space:]]*=' pyproject.toml

# 1) Установи системные зависимости (один раз)
sudo apt update && sudo apt install -y \
  build-essential ruby ruby-dev rpm patchelf file upx-ucl \
  python3 python3-pip python3-venv \
  libncurses6 libncursesw6 libtinfo6 ncurses-bin ncurses-term \
  libncurses-dev libncursesw5-dev libyaml-dev xclip xsel
sudo gem install --no-document fpm
python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller ruff

# 2) Запусти сборку .deb
chmod +x scripts/build-and-package-deb.sh
./scripts/build-and-package-deb.sh

# 3) Сгенерируй SHA256
sha256sum "releases/0.1.0/ecli_0.1.0_amd64.deb" > "releases/0.1.0/ecli_0.1.0_amd64.deb.sha256"

# 4) Проверь результат
ls -la releases/0.1.0/
```

Готово: после выполнения у тебя будут файлы:

```
releases/0.1.0/ecli_0.1.0_amd64.deb
releases/0.1.0/ecli_0.1.0_amd64.deb.sha256
```

<br>

---

<br>

## RedHat

Ок, вот **короткая, рабочая инструкция** как на Debian (через Docker) собрать **`ecli_0.1.0_amd64.rpm`** и сделать `.sha256`.

### Вариант A — через Docker (рекомендуется)

> Работает на Debian/Ubuntu; внутри контейнера — AlmaLinux 9.

```bash
# 0) Убедись, что версия = 0.1.0 в pyproject.toml
grep -nE '^[[:space:]]*version[[:space:]]*=' pyproject.toml

# 1) Собери образ RPM-сборочной среды (AlmaLinux 9)
docker build -f docker/build-linux-rpm.Dockerfile -t ecli-rpm:alma9 .

# 2) Запусти сборку RPM внутри контейнера
docker run --rm -v "$(pwd):/app" -w /app ecli-rpm:alma9 \
  bash -lc "./scripts/build-and-package-rpm.sh"

# 3) Нормализуй имя файла под требуемый шаблон (если скрипт выдал стандартное RPM-имя)
ver=0.1.0
outdir="releases/$ver"
target="$outdir/ecli_${ver}_amd64.rpm"
if [ ! -f "$target" ]; then
  src="$(ls -1 $outdir/*.rpm | head -1)"  # напр. ecli-0.1.0-1.el9.x86_64.rpm
  cp "$src" "$target"
fi

# 4) Сгенерируй SHA256
sha256sum "$target" > "$target.sha256"

# 5) Проверка наличия файлов
ls -la "$outdir/"
```

Короткий путь через Makefile (если цель уже есть):

```bash
make package-rpm-docker
ver=0.1.0; outdir="releases/$ver"; \
  src="$(ls -1 $outdir/*.rpm | head -1)"; \
  cp "$src" "$outdir/ecli_${ver}_amd64.rpm"
sha256sum "releases/0.1.0/ecli_0.1.0_amd64.rpm" > "releases/0.1.0/ecli_0.1.0_amd64.rpm.sha256"
```

### (Опционально) Быстрая проверка метаданных на хосте

```bash
sudo apt-get update && sudo apt-get install -y rpm
rpm -qpi releases/0.1.0/ecli_0.1.0_amd64.rpm | sed -n '1,20p'
```

Готово. После этого у тебя будут:

```
releases/0.1.0/ecli_0.1.0_amd64.rpm
releases/0.1.0/ecli_0.1.0_amd64.rpm.sha256
```
