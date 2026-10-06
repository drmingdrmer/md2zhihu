# md2zhihu with every tool that it runs: git, pandoc, graphviz, mermaid-cli and Chromium.
#
#   docker run --rm -v "${PWD}:/work" ghcr.io/drmingdrmer/md2zhihu md2zhihu post.md

FROM node:24-bookworm-slim

LABEL org.opencontainers.image.source=https://github.com/drmingdrmer/md2zhihu

# Keep the browsers out of $HOME, so that any user can run them.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    PUPPETEER_CACHE_DIR=/opt/puppeteer \
    PATH=/opt/venv/bin:$PATH

COPY packages.txt /tmp/
# puppeteer, which mermaid-cli uses, needs unzip to extract its browser.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates python3 python3-venv unzip $(cat /tmp/packages.txt) \
    && rm -rf /var/lib/apt/lists/* /tmp/packages.txt

# k3down2 runs `npm exec -- mmdc`, which finds a global mmdc in any directory.
# The version is the same as in package.json.
RUN npm install -g "@mermaid-js/mermaid-cli@^11.4.3" \
    && npm cache clean --force

COPY pyproject.toml README.md /src/
COPY md2zhihu /src/md2zhihu
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir /src \
    && playwright install --with-deps chromium \
    && rm -rf /src /var/lib/apt/lists/*

# The mounted directory belongs to the host user, and git refuses to work in it otherwise.
RUN git config --system --add safe.directory '*'

# Render mermaid and code to images, so that the build fails if a renderer is broken.
# puppeteer's install script exits 0 even when the browser download fails.
RUN cd /tmp \
    && printf '```mermaid\ngraph LR\n  a --> b\n```\n\n```python\nprint(1)\n```\n' > smoke.md \
    && md2zhihu smoke.md -p simple \
    && rm -rf smoke.md _md2

WORKDIR /work
CMD ["md2zhihu", "--help"]
