from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from web3 import Web3

Hash = Annotated[str, Field(pattern=r"^0x[0-9a-f]{64}$")]
Address = Annotated[str, Field(pattern=r"^0x[0-9a-fA-F]{40}$")]
UInt = Annotated[int, Field(ge=0, le=2**64 - 1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Metadata(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    mediaType: str = Field(default="text/plain;charset=utf-8", min_length=1, max_length=120)
    model: str = Field(default="unspecified", min_length=1, max_length=160)
    application: str = Field(default="ProofTrail", min_length=1, max_length=160)


class Domain(StrictModel):
    name: Literal["ProofTrail"] = "ProofTrail"
    version: Literal["1"] = "1"
    chainId: int = Field(gt=0, le=2**256 - 1)
    verifyingContract: Address

    @field_validator("verifyingContract")
    @classmethod
    def checksum(cls, value: str) -> str:
        return Web3.to_checksum_address(value)


class Claim(StrictModel):
    issuer: Address
    contentHash: Hash
    metadataHash: Hash
    parentId: Hash
    salt: Hash
    issuedAt: UInt
    expiresAt: UInt

    @field_validator("issuer")
    @classmethod
    def checksum(cls, value: str) -> str:
        return Web3.to_checksum_address(value)


class SignedReceipt(StrictModel):
    schemaVersion: Literal["prooftrail/1"] = "prooftrail/1"
    domain: Domain
    claim: Claim
    metadata: Metadata
    signature: str = Field(pattern=r"^0x[0-9a-f]{130}$")
    receiptId: Hash


class ReceiptBundle(SignedReceipt):
    batchId: Hash
    root: Hash
    proof: list[Hash] = Field(max_length=12)
    batchCount: int = Field(ge=1, le=4096)


class Check(StrictModel):
    key: str
    label: str
    passed: bool | None
    detail: str


class Verification(StrictModel):
    status: Literal["valid", "invalid", "unavailable"]
    receiptId: str
    checks: list[Check]
    anchoredAt: int | None = None
    issuer: str | None = None
    network: str
