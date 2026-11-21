from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Гроші: у коді Decimal (точна арифметика), у JSON — число, а не рядок "74.99",
# який Pydantic v2 віддає для Decimal за замовчуванням.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
