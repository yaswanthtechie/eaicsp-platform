FROM python:3.12.4-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3000

CMD ["bentoml", "serve", "src.service", "--host", "0.0.0.0", "--port", "3000"]