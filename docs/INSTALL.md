# как ставить из пакетов (deb/rpm/pkg/exe)

### deb

TODO:

### rpm

TODO:

### pkg

TODO:

### exe

TODO:

### через uv (рекомендуется для изоляции окружений)

```bash
pipx install uv           # если ещё нет
uv venv .venv             # создать .venv локально (опционально)
uv pip install ecli       # глобально через uv (аналог pip)
# или в активированном venv:
uv pip install ecli
```

### классический pip/pipx

```bash
pipx install ecli         # ставит консольный ecli изолированно (супер для CLI)
# или:
python -m pip install ecli
```
