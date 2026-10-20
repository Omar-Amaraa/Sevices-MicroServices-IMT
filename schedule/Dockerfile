FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY schedule/ ./schedule/

WORKDIR /app/schedule

EXPOSE 3202

CMD ["python", "schedule.py"]
