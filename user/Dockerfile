FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY user/ ./user/

WORKDIR /app/user

EXPOSE 3203

CMD ["python", "user.py"]
