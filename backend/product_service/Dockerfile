FROM python:3.10-alpine3.22

WORKDIR /code

# Update system packages for security fixes
RUN apk update
RUN apk --no-cache upgrade
# Install build dependencies for psycopg2 and other packages
RUN apk add --no-cache gcc musl-dev linux-headers postgresql-dev libffi-dev

COPY requirements.txt .

# Upgrade pip, setuptools, and wheel before installing your packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY app /code/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]