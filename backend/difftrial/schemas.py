import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import Limits


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderConfig(Strict):
    kind: Literal["codexlb", "compatible", "ollama"] = "codexlb"
    transport: Literal["responses", "chat", "ollama"] = "responses"
    endpoint: str = Field(max_length=500)
    model: str = Field(min_length=1, max_length=120)
    key_env: str = "CODEX_LB_API_KEY"
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)

    @field_validator("key_env")
    @classmethod
    def env_name(cls, value):
        if value not in {"CODEX_LB_API_KEY", "OPENAI_API_KEY", "DIFFTRIAL_API_KEY", ""}:
            raise ValueError("Use CODEX_LB_API_KEY, OPENAI_API_KEY, or DIFFTRIAL_API_KEY")
        return value

    @field_validator("endpoint")
    @classmethod
    def endpoint_url(cls, value):
        url = urlsplit(value)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ValueError("Endpoint must be a base URL without credentials, query, or fragment")
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Use HTTPS, or HTTP on loopback for a local provider")
        return value.rstrip("/")

    @model_validator(mode="after")
    def compatible_transport(self):
        if self.kind == "codexlb" and (self.transport != "responses" or self.key_env != "CODEX_LB_API_KEY"):
            raise ValueError("CodexLB requires Responses transport and CODEX_LB_API_KEY")
        if (self.kind == "ollama") != (self.transport == "ollama"):
            raise ValueError("Ollama requires the Ollama transport")
        return self


class TaskInput(Strict):
    benchmark_id: str | None = None
    github_url: str | None = None
    ref: str = Field(default="HEAD", max_length=128)
    issue: str = Field(default="", max_length=12000)
    profile: Literal["python", "typescript"] = "python"

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.benchmark_id) == bool(self.github_url):
            raise ValueError("Choose exactly one benchmark or GitHub repository")
        if self.github_url and not self.issue.strip():
            raise ValueError("An imported repository needs an issue description")
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", self.ref) or ".." in self.ref:
            raise ValueError("Invalid Git ref")
        return self


class RunInput(Strict):
    task_id: str
    provider: ProviderConfig
    limits: Limits = Field(default_factory=Limits)


class Plan(Strict):
    summary: str = Field(min_length=1, max_length=4000)
    steps: list[str] = Field(min_length=1, max_length=12)


class Edit(Strict):
    path: str = Field(max_length=200)
    content: str = Field(max_length=60000)


class Proposal(Strict):
    summary: str = Field(min_length=1, max_length=4000)
    edits: list[Edit] = Field(min_length=1, max_length=12)


class ValidationRequest(Strict):
    summary: str = Field(min_length=1, max_length=4000)
    checks: list[Literal["tests", "static"]] = Field(min_length=1, max_length=2)


class Finding(Strict):
    rule: str = Field(pattern=r"^R(0[1-9]|1[0-2])$")
    severity: Literal["info", "warning", "error"]
    message: str = Field(min_length=1, max_length=2000)
    path: str | None = Field(default=None, max_length=200)


class Review(Strict):
    summary: str = Field(min_length=1, max_length=4000)
    verdict: Literal["accept", "revise", "reject", "uncertain"]
    findings: list[Finding] = Field(max_length=30)
