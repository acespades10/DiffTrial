FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.5 ruff==0.11.13 && useradd --uid 10001 --create-home runner && mkdir /work /opt/runner && chown runner:runner /work
COPY execute.py /opt/runner/execute.py
USER 10001:10001
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/work:/work/deps PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
CMD ["python", "/opt/runner/execute.py", "python", "tests"]
