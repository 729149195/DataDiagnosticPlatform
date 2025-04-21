FROM python:3.10-slim
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY . /app
EXPOSE 5000

CMD ["python", "manage.py", "runserver_plus", "--cert-file=10.1.108.231.pem", , "--key-file=10.1.108.231-key.pem", "0.0.0.0:5000"]
