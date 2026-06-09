from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Backend(str, Enum):
    SGLANG = "sglang"
    SGLANG_OAI = "sglang-oai"


class DatasetType(str, Enum):
    RANDOM_IDS = "random-ids"
    SHAREGPT = "sharegpt"
    GENERATED_SHARED_PREFIX = "generated-shared-prefix"


class ServerConfig(BaseModel):
    backend: Backend = Backend.SGLANG
    host: str = "127.0.0.1"
    port: int = 30000
    base_url: Optional[str] = None
    api_key: Optional[str] = None

    def effective_url(self) -> str:
        if self.base_url:
            return self.base_url
        return f"http://{self.host}:{self.port}"

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Parse server config from FASTSTRESS_SERVER_* environment variables."""
        import os
        env = os.environ
        kwargs: dict = {}
        if v := env.get("FASTSTRESS_SERVER_BACKEND"):
            kwargs["backend"] = Backend(v)
        if v := env.get("FASTSTRESS_SERVER_HOST"):
            kwargs["host"] = v
        if v := env.get("FASTSTRESS_SERVER_PORT"):
            kwargs["port"] = int(v)
        if v := env.get("FASTSTRESS_SERVER_BASE_URL"):
            kwargs["base_url"] = v
        if v := env.get("FASTSTRESS_SERVER_API_KEY"):
            kwargs["api_key"] = v
        return cls(**kwargs)


class RandomIdsParams(BaseModel):
    input_len: int = 1024
    output_len: int = 128
    range_ratio: float = 1.0


class SharegptParams(BaseModel):
    dataset_path: str = ""
    context_len: Optional[int] = None
    output_len: Optional[int] = None


class GspParams(BaseModel):
    num_groups: int = 4
    prompts_per_group: int = 8
    system_prompt_len: int = 512
    question_len: int = 128
    output_len: int = 128
    group_distribution: str = "uniform"
    zipf_alpha: Optional[float] = None


class DatasetConfig(BaseModel):
    dataset_type: DatasetType = DatasetType.RANDOM_IDS
    random_ids: RandomIdsParams = Field(default_factory=RandomIdsParams)
    sharegpt: SharegptParams = Field(default_factory=SharegptParams)
    gsp: GspParams = Field(default_factory=GspParams)


class LoadConfig(BaseModel):
    request_rate: float = Field(default=float("inf"), description="Requests per second, inf for burst")
    max_concurrency: Optional[int] = None
    num_prompts: int = 100


class TestCase(BaseModel):
    name: str = "unnamed"
    server: ServerConfig = Field(default_factory=ServerConfig)
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    load: LoadConfig = Field(default_factory=LoadConfig)
    extra_request_body: Optional[str] = None

    def to_bench_args(self) -> list[str]:
        args = [
            "--backend", self.server.backend.value,
            "--num-prompts", str(self.load.num_prompts),
        ]
        if self.server.base_url:
            args += ["--base-url", self.server.base_url]
        else:
            args += ["--host", self.server.host, "--port", str(self.server.port)]

        if self.load.request_rate != float("inf"):
            args += ["--request-rate", str(self.load.request_rate)]
        else:
            args += ["--request-rate", "inf"]

        if self.load.max_concurrency is not None:
            args += ["--max-concurrency", str(self.load.max_concurrency)]

        args += ["--dataset-name", self.dataset.dataset_type.value]

        if self.dataset.dataset_type == DatasetType.RANDOM_IDS:
            p = self.dataset.random_ids
            args += [
                "--random-input-len", str(p.input_len),
                "--random-output-len", str(p.output_len),
                "--random-range-ratio", str(p.range_ratio),
            ]
        elif self.dataset.dataset_type == DatasetType.SHAREGPT:
            p = self.dataset.sharegpt
            if p.dataset_path:
                args += ["--dataset-path", p.dataset_path]
            if p.context_len is not None:
                args += ["--sharegpt-context-len", str(p.context_len)]
            if p.output_len is not None:
                args += ["--sharegpt-output-len", str(p.output_len)]
        elif self.dataset.dataset_type == DatasetType.GENERATED_SHARED_PREFIX:
            p = self.dataset.gsp
            args += [
                "--gsp-num-groups", str(p.num_groups),
                "--gsp-prompts-per-group", str(p.prompts_per_group),
                "--gsp-system-prompt-len", str(p.system_prompt_len),
                "--gsp-question-len", str(p.question_len),
                "--gsp-output-len", str(p.output_len),
                "--gsp-group-distribution", p.group_distribution,
            ]
            if p.zipf_alpha is not None:
                args += ["--gsp-zipf-alpha", str(p.zipf_alpha)]

        if self.extra_request_body:
            args += ["--extra-request-body", self.extra_request_body]

        args += ["--output-file", "/tmp/faststress_result.jsonl"]
        return args

    def get_env(self) -> dict[str, str] | None:
        """Extra environment variables for bench_serving subprocess."""
        if self.server.api_key:
            return {"OPENAI_API_KEY": self.server.api_key}
        return None


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BenchResult(BaseModel):
    request_throughput: Optional[float] = None
    output_throughput: Optional[float] = None
    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None
    mean_ttft_ms: Optional[float] = None
    median_ttft_ms: Optional[float] = None
    p99_ttft_ms: Optional[float] = None
    mean_tpot_ms: Optional[float] = None
    median_tpot_ms: Optional[float] = None
    p99_tpot_ms: Optional[float] = None
    mean_e2e_latency_ms: Optional[float] = None
    median_e2e_latency_ms: Optional[float] = None
    p99_e2e_latency_ms: Optional[float] = None
    completed: Optional[int] = None
    duration: Optional[float] = None


class TestCaseRun(BaseModel):
    case_name: str
    status: RunStatus = RunStatus.PENDING
    result: Optional[BenchResult] = None
    error: Optional[str] = None
    output_file: Optional[str] = None


class TestGroup(BaseModel):
    name: str = "default"
    cases: list[TestCase] = Field(default_factory=list)


class Preset(BaseModel):
    name: str
    group: TestGroup
