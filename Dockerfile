FROM python:3.10
COPY poetry.lock pyproject.toml /app/
WORKDIR /app
RUN pip install poetry && \
    poetry config virtualenvs.in-project true && \
    poetry install --no-interaction --no-ansi
COPY . /app
EXPOSE 5000