FROM python:3.11-slim

WORKDIR /srv/nblaunch

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md ./
COPY src ./src

ENV PYTHONPATH=/srv/nblaunch/src

CMD ["python", "-m", "nblaunch.main"]
