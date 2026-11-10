"""Pydantic models that validate data before it reaches the database."""

from datetime import date, datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Largest whole number JavaScript can store exactly. IDs stay below it.
MAX_ID = 9_007_199_254_740_991

ShortText = Annotated[str, Field(min_length=1, max_length=120)]
CoreCount = Annotated[int, Field(ge=0, le=2_147_483_647)]


# ==================== GPUS ====================

class GPUCreate(BaseModel):
    """The editable fields of a GPU. Used as the body of POST and PUT."""

    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)

    brand: Literal["NVIDIA", "AMD", "Intel"]
    manufacturer: Literal[
        "NVIDIA", "AMD", "Intel", "ASUS", "MSI", "Gigabyte", "Zotac", "PNY",
        "Palit", "Colorful", "Gainward", "Inno3D", "EVGA", "PowerColor",
        "Sapphire", "XFX", "ASRock"
    ]
    model: ShortText
    series: ShortText
    architecture: ShortText
    vram: ShortText
    memory_type: Literal["DDR3", "GDDR5", "GDDR5X", "GDDR6", "GDDR6X", "GDDR7"]
    cuda_cores: CoreCount
    core_count: CoreCount
    core_type: Literal["CUDA Cores", "Stream Processors", "Xe Cores"]
    memory_bus: ShortText
    memory_bandwidth_gbps: float = Field(
        gt=0, le=1_000_000,
        description="Memory bandwidth in GB/s (gigabytes per second)."
    )
    power: ShortText
    base_clock: ShortText
    boost_clock: ShortText
    recommended_psu: ShortText
    process_node_nm: int = Field(gt=0, le=2_147_483_647)
    pcie_interface: Literal[
        "PCIe 2.0 x8", "PCIe 2.0 x16", "PCIe 3.0 x4", "PCIe 3.0 x16",
        "PCIe 4.0 x8", "PCIe 4.0 x16", "PCIe 5.0 x8", "PCIe 5.0 x16"
    ]
    launch_price_usd: Optional[float] = Field(default=None, ge=0, le=1_000_000_000)
    release_date: date = Field(description="Release date as YYYY-MM-DD.")
    description: str = Field(min_length=1, max_length=4000)


class GPU(GPUCreate):
    """A stored GPU, including the ID the database generated."""

    id: int = Field(gt=0, le=MAX_ID)


class GPUList(BaseModel):
    count: int
    gpus: list[GPU]


class GPUSearchResults(BaseModel):
    query: str
    count: int
    results: list[GPU]


# ==================== USERS ====================

class Credentials(BaseModel):
    """The body of POST /auth/register and POST /auth/login."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(
        min_length=3, max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        examples=["student@example.com"],
    )
    password: str = Field(min_length=8, max_length=128, examples=["a-long-password"])

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()


class User(BaseModel):
    """An account as the API returns it. The password hash is never included."""

    id: int
    email: str
    role: Literal["user", "admin"]
    created_at: datetime


class LoginResult(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires.")
    user: User
