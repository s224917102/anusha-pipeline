FROM python:3.10-alpine

WORKDIR /code

# Install required system dependencies
RUN apk add --no-cache gcc musl-dev linux-headers

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app /code/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]