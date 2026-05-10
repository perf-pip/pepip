## 🛠 Development

```bash
# Clone and install in editable mode
git clone https://github.com/perf-pip/pepip
cd pepip
pip install -e .

# Run tests
pip install pytest
pytest
```

## CLI behavior

`pepip install ...` uses pepip's shared package store and links the resolved
entries into the target virtual environment.

All other invocations are forwarded to `uv` unchanged, for example:

```bash
pepip sync --all
pepip run python -m pytest
pepip pip install ".[all]"
pepip --version
```

### 🚢 Docker usage

`pepip` is primarily designed for local machine workflows where multiple projects can reuse one shared store over time. In Docker, images are usually ephemeral and already layer-cached, so the benefit is smaller.

That said, `pepip` can still be useful in Docker when you want to share one package store across repeated container runs (for example during local development).

#### 1) Simple container install

```dockerfile
FROM python:3.12-slim

# uv is required by pepip
RUN pip install --no-cache-dir uv pepip

WORKDIR /app
COPY requirements.txt .

# Creates /app/.venv and links packages from /root/.pepip
RUN pepip install -r requirements.txt
```

#### 2) Attach system-level `PEPIP_HOME` from host

Bind your host's `~/.pepip` into the container's default pepip path (`/root/.pepip`):

```bash
docker run --rm \
    -v "$PWD":/app \
    -v "$HOME/.pepip":/root/.pepip \
    -e PEPIP_HOME=/root/.pepip \
    -w /app \
    python:3.12-slim \
    sh -lc "pip install -q uv pepip && pepip install -r requirements.txt"
```

This attaches the host-level pepip store directly, so both local and container workflows reuse the same resolved package versions.
