from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import time
from utils import write_to_postgres_price,write_to_postgres_window

spark = SparkSession.builder \
    .appName("RealTimeSalesAnalytics") \
    .master("local[*]") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.7.2") \
    .config("spark.sql.shuffle.partitions", "4") \
    .getOrCreate()

spark.sparkContext.setLogLevel("OFF")

schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DecimalType(38, 18), True),
    StructField("event_time", LongType(), True),
    StructField("processed_time", IntegerType(), True)
])

# Read
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "crypto_prices") \
    .option("startingOffsets", "earliest") \
    .option("maxOffsetsPerTrigger", "1000") \
    .load()

# Select and parse
parsed_stream = raw_stream.selectExpr("CAST(value AS STRING) as json_value") \
    .select(from_json(col("json_value"), schema).alias("data")) \
    .select("data.*")

# cast event time and processed time to timestamp
parsed_stream = parsed_stream.withColumn("event_time", col("event_time").cast("timestamp"))
parsed_stream = parsed_stream.withColumn("processed_time", col("processed_time").cast("timestamp"))
# Add watermark
final_stream = parsed_stream.withWatermark("event_time", "10 seconds")

query_price = final_stream.writeStream \
    .foreachBatch(write_to_postgres_price) \
    .outputMode("append") \
    .trigger(processingTime="2 seconds") \
    .option("checkpointLocation", ".//checkpoint//crypto_prices") \
    .start()

# Windowing for OLDC
window_stream = final_stream.withColumn(
    "time_price", 
    struct(col("event_time"), col("price"))
)

ohlc_stream = window_stream \
    .groupBy(
        window(col("event_time"), "1 minute"), 
        col("symbol")
    ).agg(
        # Logika Struct Sort untuk Open & Close
        min("time_price").getField("price").alias("open"),
        max("time_price").getField("price").alias("close"),
        # Logika murni untuk High & Low
        max("price").alias("high"),
        min("price").alias("low")
    ).select(
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        "symbol",
        "open",
        "high",
        "low",
        "close"
    )

ohlc_console = ohlc_stream.writeStream \
    .outputMode("update") \
    .format("console") \
    .option("truncate", "false") \
    .trigger(processingTime="1 minute") \
    .start()

query_window_1m = ohlc_stream.writeStream \
    .foreachBatch(write_to_postgres_window) \
    .outputMode("update") \
    .trigger(processingTime="1 minute") \
    .option("checkpointLocation", ".//checkpoint//window_1m") \
    .start()

if __name__ == "__main__":
    try:
        print(f"Starting Streams...")
        spark.streams.awaitAnyTermination()
    except KeyboardInterrupt:
        print(f"Stopping Streams...")
        spark.streams.stop()

