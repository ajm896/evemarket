import msgspec

class Price(msgspec.Struct):
    type_id: int
    adjusted_price: float | None = None
    average_price:  float | None = None

