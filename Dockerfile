FROM python:3.13-slim
WORKDIR /app

# install dependencies directly
RUN pip install --no-cache-dir Flask==2.2.5 gunicorn==20.1.0

COPY . .
EXPOSE 5000
CMD ["gunicorn","--bind","0.0.0.0:5000","app:app"]
