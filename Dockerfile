FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
RUN python3 -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . /app/project/
WORKDIR /app/project
RUN pip install --no-cache-dir -e .
CMD ["python3", "-m", "shop_bot"]