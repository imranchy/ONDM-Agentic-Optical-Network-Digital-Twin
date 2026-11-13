# Minimal, network-less execution image for VLM-generated NetworkX code.
FROM python:3.12-slim
RUN pip install --no-cache-dir networkx==3.4.2 && useradd -u 10001 -M -s /usr/sbin/nologin sandbox
COPY runner.py /opt/ondm/runner.py
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "/opt/ondm/runner.py"]
