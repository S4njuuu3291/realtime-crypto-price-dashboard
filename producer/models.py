import time
from pydantic import BaseModel
from decimal import Decimal

class CryptoPrice(BaseModel):
    symbol: str
    price: Decimal
    # event time is long
    event_time: int
    processed_time: int

    @classmethod
    def from_kafka_message(cls, message):
        return cls(
            symbol = message["s"],
            price = Decimal(message["p"]),
            event_time = message["T"] // 1000,
            processed_time = int(time.time())
        )
    
    
