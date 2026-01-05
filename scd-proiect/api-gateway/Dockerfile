FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set env var for Flask
ENV FLASK_APP=app.main.py

# Run flask
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8000"]
