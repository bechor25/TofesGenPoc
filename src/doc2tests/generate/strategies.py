from __future__ import annotations

import random
from typing import Protocol

from faker import Faker

from doc2tests.contracts.enums import FieldType
from doc2tests.validators.israeli_id import complete_israeli_id


class FieldStrategy(Protocol):
    def generate(self) -> str: ...


class _Base:
    def __init__(self, rng: random.Random):
        self.rng = rng


class IsraeliIdStrategy(_Base):
    def generate(self) -> str:
        prefix = "".join(str(self.rng.randint(0, 9)) for _ in range(8))
        return complete_israeli_id(prefix)


class DateStrategy(_Base):
    def generate(self) -> str:
        d = self.rng.randint(1, 28)
        m = self.rng.randint(1, 12)
        y = self.rng.randint(1960, 2024)
        return f"{d:02d}.{m:02d}.{y}"


class PhoneStrategy(_Base):
    def generate(self) -> str:
        return "05" + "".join(str(self.rng.randint(0, 9)) for _ in range(8))


class BankBranchStrategy(_Base):
    def generate(self) -> str:
        return f"{self.rng.randint(100, 999)}"


class GushHelkaStrategy(_Base):
    def generate(self) -> str:
        return f"{self.rng.randint(1000, 9999)}-{self.rng.randint(1, 999)}-0"


class NumberStrategy(_Base):
    def generate(self) -> str:
        return "".join(str(self.rng.randint(0, 9)) for _ in range(9))


class _FakerStrategy(_Base):
    _faker = Faker("he_IL")

    def __init__(self, rng: random.Random):
        super().__init__(rng)
        self._faker.seed_instance(rng.randint(0, 10_000_000))


class HebrewNameStrategy(_FakerStrategy):
    def generate(self) -> str:
        return str(self._faker.name())


class FreeTextStrategy(_FakerStrategy):
    def generate(self) -> str:
        return str(self._faker.sentence(nb_words=3))


_REGISTRY: dict[FieldType, type[_Base]] = {
    FieldType.israeli_id: IsraeliIdStrategy,
    FieldType.date: DateStrategy,
    FieldType.hebrew_name: HebrewNameStrategy,
    FieldType.phone: PhoneStrategy,
    FieldType.bank_branch: BankBranchStrategy,
    FieldType.gush_helka: GushHelkaStrategy,
    FieldType.assessment_number: NumberStrategy,
    FieldType.currency: NumberStrategy,
}


def strategy_for(field_type: FieldType, rng: random.Random) -> FieldStrategy:
    cls = _REGISTRY.get(field_type, FreeTextStrategy)
    return cls(rng)  # type: ignore[return-value]
