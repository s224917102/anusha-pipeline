FROM python:3.10-alpine3.22

WORKDIR /code

# Update system packages for security fixes
RUN apk update && apk upgrade

# Install build dependencies
RUN apk add --no-cache gcc musl-dev linux-headers postgresql-dev

COPY requirements.txt .

# Upgrade pip and install requirements
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY app /code/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]