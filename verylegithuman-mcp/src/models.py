"""Pydantic models and SQLAlchemy ORM for VeryLegitHuman MCP."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# SQLAlchemy ORM
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class PersonaRow(Base):
    __tablename__ = "personas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    codename = Column(String(64), unique=True, nullable=False, index=True)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    full_name = Column(String(256), nullable=False)
    gender = Column(String(32))
    date_of_birth = Column(String(10))  # ISO format YYYY-MM-DD
    age = Column(Integer)
    email_personal = Column(String(256))
    phone = Column(String(64))
    address_street = Column(String(256))
    address_city = Column(String(128))
    address_state = Column(String(128))
    address_zip = Column(String(32))
    address_country = Column(String(128))
    nationality = Column(String(128))
    locale = Column(String(16))
    occupation = Column(String(256))
    company = Column(String(256))
    bio = Column(Text)
    face_url = Column(String(512))
    face_source = Column(String(32), default="none")
    usernames_json = Column(Text, default="{}")  # JSON string
    username_availability_json = Column(Text, default="{}")  # JSON string
    metadata_json = Column(Text, default="{}")  # JSON string
    status = Column(String(16), default="active", index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    notes = relationship("PersonaNoteRow", back_populates="persona", cascade="all, delete-orphan")

    @property
    def usernames(self) -> dict:
        return json.loads(self.usernames_json or "{}")

    @usernames.setter
    def usernames(self, value: dict) -> None:
        self.usernames_json = json.dumps(value)

    @property
    def username_availability(self) -> dict:
        return json.loads(self.username_availability_json or "{}")

    @username_availability.setter
    def username_availability(self, value: dict) -> None:
        self.username_availability_json = json.dumps(value)

    @property
    def extra_metadata(self) -> dict:
        return json.loads(self.metadata_json or "{}")

    @extra_metadata.setter
    def extra_metadata(self, value: dict) -> None:
        self.metadata_json = json.dumps(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "codename": self.codename,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "gender": self.gender,
            "date_of_birth": self.date_of_birth,
            "age": self.age,
            "email_personal": self.email_personal,
            "phone": self.phone,
            "address": {
                "street": self.address_street,
                "city": self.address_city,
                "state": self.address_state,
                "zip": self.address_zip,
                "country": self.address_country,
            },
            "nationality": self.nationality,
            "locale": self.locale,
            "occupation": self.occupation,
            "company": self.company,
            "bio": self.bio,
            "face_url": self.face_url,
            "face_source": self.face_source,
            "usernames": self.usernames,
            "username_availability": self.username_availability,
            "metadata": self.extra_metadata,
            "status": self.status,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
            "notes": [n.to_dict() for n in (self.notes or [])],
        }


class PersonaNoteRow(Base):
    __tablename__ = "persona_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_id = Column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    persona = relationship("PersonaRow", back_populates="notes")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "persona_id": self.persona_id,
            "note": self.note,
            "created_at": str(self.created_at) if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Pydantic models (API layer)
# ---------------------------------------------------------------------------

class PersonaCreate(BaseModel):
    """Parameters for creating a new persona."""
    locale: str = "en_US"
    gender: Optional[str] = None
    age_min: Optional[int] = Field(None, ge=18, le=90)
    age_max: Optional[int] = Field(None, ge=18, le=90)
    nationality: Optional[str] = None
    occupation: Optional[str] = None
    codename: Optional[str] = None


class PersonaUpdate(BaseModel):
    """Partial update fields for a persona."""
    codename: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    email_personal: Optional[str] = None
    phone: Optional[str] = None
    occupation: Optional[str] = None
    company: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PersonaSummary(BaseModel):
    """Lightweight persona for list views."""
    id: str
    codename: str
    full_name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    locale: str
    status: str
    face_source: str = "none"
    created_at: Optional[str] = None


class UsernameResult(BaseModel):
    """Result of a username availability check."""
    username: str
    platforms: dict[str, bool]  # {platform: available}
    checked_at: str
