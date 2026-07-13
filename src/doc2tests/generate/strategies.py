from __future__ import annotations

import random
from typing import Protocol

from faker import Faker

from doc2tests.contracts.enums import FieldType
from doc2tests.validators.israeli_id import complete_israeli_id


class FieldStrategy(Protocol):
    def generate(self, like: str = "") -> str: ...


class _Base:
    def __init__(self, rng: random.Random):
        self.rng = rng


class IsraeliIdStrategy(_Base):
    def generate(self, like: str = "") -> str:
        prefix = "".join(str(self.rng.randint(0, 9)) for _ in range(8))
        return complete_israeli_id(prefix)


class DateStrategy(_Base):
    def generate(self, like: str = "") -> str:
        d = self.rng.randint(1, 28)
        m = self.rng.randint(1, 12)
        y = self.rng.randint(1960, 2024)
        sep = "/" if "/" in like else "."
        return f"{d:02d}{sep}{m:02d}{sep}{y}"


class PhoneStrategy(_Base):
    def generate(self, like: str = "") -> str:
        return "05" + "".join(str(self.rng.randint(0, 9)) for _ in range(8))


class BankBranchStrategy(_Base):
    def generate(self, like: str = "") -> str:
        return f"{self.rng.randint(100, 999)}"


class GushHelkaStrategy(_Base):
    def generate(self, like: str = "") -> str:
        return f"{self.rng.randint(1000, 9999)}-{self.rng.randint(1, 999)}-0"


class NumberStrategy(_Base):
    def generate(self, like: str = "") -> str:
        # match the original's digit count so the replacement looks right in the form
        n = sum(c.isdigit() for c in like) or 9
        n = max(1, min(n, 18))
        return "".join(str(self.rng.randint(0, 9)) for _ in range(n))


class _FakerStrategy(_Base):
    _faker = Faker("he_IL")

    def __init__(self, rng: random.Random):
        super().__init__(rng)
        self._faker.seed_instance(rng.randint(0, 10_000_000))


class HebrewNameStrategy(_FakerStrategy):
    def generate(self, like: str = "") -> str:
        return str(self._faker.name())


class AddressStrategy(_FakerStrategy):
    def generate(self, like: str = "") -> str:
        # single line — form fields are one row; drop faker's newlines
        return " ".join(str(self._faker.address()).split())


class FreeTextStrategy(_FakerStrategy):
    def generate(self, like: str = "") -> str:
        words = max(2, min(len(like.split()) or 3, 6))
        return str(self._faker.sentence(nb_words=words)).rstrip(".")


_REGISTRY: dict[FieldType, type[_Base]] = {
    FieldType.israeli_id: IsraeliIdStrategy,
    FieldType.date: DateStrategy,
    FieldType.hebrew_name: HebrewNameStrategy,
    FieldType.address: AddressStrategy,
    FieldType.phone: PhoneStrategy,
    FieldType.bank_branch: BankBranchStrategy,
    FieldType.gush_helka: GushHelkaStrategy,
    FieldType.assessment_number: NumberStrategy,
    FieldType.currency: NumberStrategy,
}


def strategy_for(field_type: FieldType, rng: random.Random) -> FieldStrategy:
    cls = _REGISTRY.get(field_type, FreeTextStrategy)
    return cls(rng)  # type: ignore[return-value]
