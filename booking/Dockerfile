FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY booking/ ./booking/

WORKDIR /app/booking

EXPOSE 3201

CMD ["python", "booking.py"]
