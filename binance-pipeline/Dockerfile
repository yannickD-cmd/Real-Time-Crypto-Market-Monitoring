FROM python:3.11-slim

# PySpark requires Java
RUN apt-get update && apt-get install -y default-jdk curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the Spark Kafka connector JAR at build time so first startup isn't slow
RUN python -c "\
from pyspark.sql import SparkSession; \
spark = SparkSession.builder \
    .config('spark.jars.packages', 'org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1') \
    .getOrCreate(); \
spark.stop() \
"

COPY . .
