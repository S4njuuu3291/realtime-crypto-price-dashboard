setup-kafka:
	docker exec -it kafka kafka-topics --create --topic crypto_prices --partitions 20 --replication-factor 1 --bootstrap-server localhost:9092

run-producer:
	poetry run python producer/crypto-price-producer.py

run-consumer:
	poetry run python producer/crypto-price-producer.py

run-spark:
	spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.7.2 main.py