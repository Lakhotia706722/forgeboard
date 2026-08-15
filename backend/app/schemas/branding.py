"""
Pydantic schemas for white-label branding — Phase 9d.
"""
import re
import uuid
from pydantic import BaseModel, Field, field_validator


class BrandingOut(BaseModel):
    workspace_id: uuid.UUID
    display_name: str | None = None
    brand_logo_url: str | None = None
    brand_primary_color: str | None = None
    brand_app_name: str | None = None
    managed_by_agency_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class BrandingUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    brand_logo_url: str | None = Field(
        default=None,
        description="HTTPS URL to a logo image (PNG/SVG, max ~500KB recommended).",
    )
    brand_primary_color: str | None = Field(
        default=None,
        description="CSS hex color, e.g. '#6366f1'. Must be 6-digit hex with #.",
    )
    brand_app_name: str | None = Field(
        default=None,
        max_length=100,
        description="Override the 'ForgeBoard' app name shown in the UI.",
    )

    @field_validator("brand_primary_color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError("brand_primary_color must be a 6-digit hex color, e.g. '#6366f1'.")
        return v.lower()

    @field_validator("brand_logo_url")
    @classmethod
    def validate_https_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError("brand_logo_url must be an HTTPS URL.")
        return v
