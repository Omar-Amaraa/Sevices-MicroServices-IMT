FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY movie/ ./movie/

WORKDIR /app/movie

EXPOSE 3200

CMD ["python", "movie.py"]
