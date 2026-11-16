FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home runner && mkdir /work /opt/runner && chown runner:runner /work
COPY execute.py vitest.config.mjs /opt/runner/
USER 10001:10001
WORKDIR /work
ENV CI=true
CMD ["python3", "/opt/runner/execute.py", "typescript", "tests"]
