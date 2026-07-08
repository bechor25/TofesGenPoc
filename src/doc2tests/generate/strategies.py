from __future__ import annotations

import random
from typing import Protocol

from faker import Faker

from doc2tests.contracts.enums import FieldType
from doc2tests.validators.israeli_id import complete_israeli_id


class FieldStrategy(Protocol):
    def equivalence(self) -> str: ...
    def boundary(self) -> str: ...
    def negative(self) -> list[str]: ...


class _Base:
    def __init__(self, rng: random.Random):
        self.rng = rng


class IsraeliIdStrategy(_Base):
    def equivalence(self) -> str:
        prefix = "".join(str(self.rng.randint(0, 9)) for _ in range(8))
        return complete_israeli_id(prefix)

    def boundary(self) -> str:
        # valid id that starts with a zero (leading-zero handling)
        prefix = "0" + "".join(str(self.rng.randint(0, 9)) for _ in range(7))
        return complete_israeli_id(prefix)

    def negative(self) -> list[str]:
        good = self.equivalence()
        bad_checksum = good[:-1] + str((int(good[-1]) + 1) % 10)
        return [bad_checksum, good[:8], good + "0"]  # wrong checksum, too short, too long


class DateStrategy(_Base):
    def equivalence(self) -> str:
        d = self.rng.randint(1, 28)
        m = self.rng.randint(1, 12)
        y = self.rng.randint(2000, 2024)
        return f"{d:02d}.{m:02d}.{y}"

    def boundary(self) -> str:
        return "29.02.2020"  # leap day

    def negative(self) -> list[str]:
        return ["31.02.2021", "00.13.2020"]


class _FakerStrategy(_Base):
    _faker = Faker("he_IL")

    def __init__(self, rng: random.Random):
        super().__init__(rng)
        self._faker.seed_instance(rng.randint(0, 10_000_000))


class HebrewNameStrategy(_FakerStrategy):
    def equivalence(self) -> str:
        return str(self._faker.name())

    def boundary(self) -> str:
        return "א"  # single character

    def negative(self) -> list[str]:
        return ["", "123"]  # empty, digits-only


class PhoneStrategy(_Base):
    def equivalence(self) -> str:
        return "05" + "".join(str(self.rng.randint(0, 9)) for _ in range(8))

    def boundary(self) -> str:
        return "0" + "".join(str(self.rng.randint(0, 9)) for _ in range(8))  # 9-digit landline

    def negative(self) -> list[str]:
        return ["123", "0" + "0" * 11]


class BankBranchStrategy(_Base):
    def equivalence(self) -> str:
        return f"{self.rng.randint(100, 999)}"

    def boundary(self) -> str:
        return f"{self.rng.randint(1, 9)}"

    def negative(self) -> list[str]:
        return ["12X", "1234"]


class GushHelkaStrategy(_Base):
    def equivalence(self) -> str:
        return f"{self.rng.randint(1000, 9999)}-{self.rng.randint(1, 999)}-0"

    def boundary(self) -> str:
        return f"{self.rng.randint(1, 9)}-1"

    def negative(self) -> list[str]:
        return ["9007", "gush-12"]


class NumberStrategy(_Base):
    def equivalence(self) -> str:
        return "".join(str(self.rng.randint(0, 9)) for _ in range(9))

    def boundary(self) -> str:
        return "0"

    def negative(self) -> list[str]:
        return ["not-a-number"]


class FreeTextStrategy(_FakerStrategy):
    def equivalence(self) -> str:
        return str(self._faker.sentence(nb_words=4))

    def boundary(self) -> str:
        return "א" * 200  # long string / RTL stress

    def negative(self) -> list[str]:
        return [""]


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
