"""Identity generation using Faker and Mimesis."""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime
from typing import Optional

from faker import Faker

from ..config import CODENAME_ADJECTIVES, CODENAME_NOUNS, DEFAULT_LOCALE


def generate_codename() -> str:
    """Generate a random two-word codename like 'shadow-wolf'."""
    adj = random.choice(CODENAME_ADJECTIVES)
    noun = random.choice(CODENAME_NOUNS)
    suffix = random.randint(10, 99)
    return f"{adj}-{noun}-{suffix}"


def generate_identity(
    locale: str = DEFAULT_LOCALE,
    gender: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    nationality: Optional[str] = None,
    occupation: Optional[str] = None,
    codename: Optional[str] = None,
) -> dict:
    """Generate a complete identity using Faker.

    Returns a flat dict ready for database insertion.
    """
    fake = Faker(locale)

    # Gender
    if gender and gender.lower() in ("male", "m"):
        first_name = fake.first_name_male()
        resolved_gender = "male"
    elif gender and gender.lower() in ("female", "f"):
        first_name = fake.first_name_female()
        resolved_gender = "female"
    else:
        resolved_gender = random.choice(["male", "female"])
        first_name = fake.first_name_male() if resolved_gender == "male" else fake.first_name_female()

    last_name = fake.last_name()
    full_name = f"{first_name} {last_name}"

    # Age / DOB
    min_age = age_min or 21
    max_age = age_max or 55
    if min_age > max_age:
        min_age, max_age = max_age, min_age
    today = date.today()
    start_date = date(today.year - max_age, today.month, today.day)
    end_date = date(today.year - min_age, today.month, today.day)
    dob = fake.date_between(start_date=start_date, end_date=end_date)
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    # Address
    address = fake.address()
    # Parse structured address where possible
    address_street = fake.street_address()
    address_city = fake.city()
    address_state = fake.state() if hasattr(fake, "state") else fake.province() if hasattr(fake, "province") else ""
    address_zip = fake.zipcode() if hasattr(fake, "zipcode") else fake.postcode()
    address_country = fake.current_country()

    # Email (placeholder — not a real provisioned address)
    email_local = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}"
    email_domain = random.choice(["gmail.com", "outlook.com", "yahoo.com", "protonmail.com"])
    email = f"{email_local}@{email_domain}"

    # Phone (placeholder format)
    phone = fake.phone_number()

    # Occupation
    resolved_occupation = occupation or fake.job()
    company = fake.company()

    # Nationality
    resolved_nationality = nationality or fake.current_country()

    return {
        "id": str(uuid.uuid4()),
        "codename": codename or generate_codename(),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "gender": resolved_gender,
        "date_of_birth": dob.isoformat(),
        "age": age,
        "email_personal": email,
        "phone": phone,
        "address_street": address_street,
        "address_city": address_city,
        "address_state": address_state,
        "address_zip": address_zip,
        "address_country": address_country,
        "nationality": resolved_nationality,
        "locale": locale,
        "occupation": resolved_occupation,
        "company": company,
        "bio": None,
        "face_url": None,
        "face_source": "none",
        "usernames_json": "{}",
        "username_availability_json": "{}",
        "metadata_json": "{}",
        "status": "active",
    }


def generate_usernames_for_identity(
    first_name: str,
    last_name: str,
    style: str = "professional",
    count: int = 5,
) -> list[str]:
    """Generate username candidates based on a persona's name.

    Styles:
        professional — firstname.lastname variants
        casual — adjective+name combos
        random — fully random words
    """
    candidates: list[str] = []
    fn = first_name.lower().replace(" ", "")
    ln = last_name.lower().replace(" ", "")

    if style == "professional":
        candidates.extend([
            f"{fn}.{ln}",
            f"{fn}_{ln}",
            f"{fn}{ln}",
            f"{fn[0]}{ln}",
            f"{fn}{ln[0]}",
            f"{fn}.{ln}{random.randint(1, 99)}",
            f"{fn}_{ln}{random.randint(100, 999)}",
            f"{ln}.{fn}",
            f"{fn}{random.randint(10, 99)}",
            f"{ln}{fn[0]}{random.randint(1, 99)}",
        ])
    elif style == "casual":
        adjectives = ["cool", "real", "the", "just", "hey", "not", "its", "im", "xo", "big"]
        candidates.extend([
            f"{random.choice(adjectives)}{fn}",
            f"{fn}{random.choice(adjectives)}{random.randint(1, 99)}",
            f"{random.choice(adjectives)}_{fn}_{random.randint(1, 99)}",
            f"{fn}x{random.randint(100, 999)}",
            f"x{fn}{ln[0]}",
            f"{fn}vibes",
            f"{fn}_official",
            f"not{fn}{ln[0]}",
            f"the.real.{fn}",
            f"{fn}{random.randint(1000, 9999)}",
        ])
    else:  # random
        fake = Faker()
        for _ in range(count + 5):
            candidates.append(fake.user_name())

    # Deduplicate and limit
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        c_clean = c.strip().lower()
        if c_clean not in seen and len(c_clean) >= 3:
            seen.add(c_clean)
            unique.append(c_clean)
    return unique[:count]
