from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

from .models import BenchResult, ServerConfig, TestCase

LOGS_DIR = Path.home() / ".faststress" / "logs"


class BenchRunner:
    def __init__(self, python_bin: Optional[str] = None):
        self.python_bin = python_bin or sys.executable
        self._proc: Optional[asyncio.subprocess.Process] = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    def _build_command(self, case: TestCase, server: ServerConfig, output_file: str) -> list[str]:
        args = case.to_bench_args(server)
        for i, a in enumerate(args):
            if a == "--output-file":
                args[i + 1] = output_file
                break
        return [self.python_bin, "-m", "sglang.bench_serving"] + args

    @staticmethod
    def _make_env(server: ServerConfig) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        extra = TestCase.get_env(server)
        if extra:
            env.update(extra)
        return env

    async def run(
        self, case: TestCase, server: ServerConfig, on_output: Optional[callable] = None
    ) -> tuple[Optional[BenchResult], Optional[str]]:
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", prefix="faststress_", delete=False
        ) as f:
            output_file = f.name

        cmd = self._build_command(case, server, output_file)
        env = self._make_env(server)
        log_path = self._log_path(case.name)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            self._proc = proc

            output_lines = []
            with open(log_path, "w") as log_file:
                log_file.write(f"# {' '.join(cmd)}\n")
                log_file.flush()
                async for line in self._read_stream(proc.stdout):
                    log_file.write(line + "\n")
                    log_file.flush()
                    output_lines.append(line)
                    if on_output:
                        on_output(line)

            await proc.wait()
            self._proc = None

            if proc.returncode != 0:
                return None, "\n".join(output_lines)

            result = self._parse_result(output_file)
            return result, None
        except FileNotFoundError:
            self._proc = None
            return None, "sglang not found. Install with: pip install sglang[all]"
        except Exception as e:
            self._proc = None
            return None, str(e)

    async def run_stream(self, case: TestCase, server: ServerConfig) -> AsyncIterator[str]:
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", prefix="faststress_", delete=False
        ) as f:
            output_file = f.name

        cmd = self._build_command(case, server, output_file)
        env = self._make_env(server)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        self._proc = proc
        async for line in self._read_stream(proc.stdout):
            yield line

        await proc.wait()
        self._proc = None
        if proc.returncode == 0:
            yield f"\n__RESULT_FILE__:{output_file}"
        else:
            yield f"\n__ERROR__:Process exited with code {proc.returncode}"

    @staticmethod
    async def _read_stream(stream: asyncio.StreamReader) -> AsyncIterator[str]:
        buf = ""
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                if buf.strip():
                    yield buf.strip()
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.rstrip("\r")
                if "\r" in line:
                    line = line.split("\r")[-1]
                if line.strip():
                    yield line
            if "\r" in buf:
                parts = buf.split("\r")
                last = parts[-1]
                if last.strip():
                    yield last
                buf = last

    @staticmethod
    def _parse_result(output_file: str) -> Optional[BenchResult]:
        if not os.path.exists(output_file):
            return None
        try:
            with open(output_file) as f:
                lines = f.readlines()
            if not lines:
                return None
            data = json.loads(lines[-1])
            return BenchResult(
                request_throughput=data.get("request_throughput"),
                output_throughput=data.get("output_throughput"),
                total_input_tokens=data.get("total_input_tokens"),
                total_output_tokens=data.get("total_output_tokens"),
                mean_ttft_ms=data.get("mean_ttft_ms"),
                median_ttft_ms=data.get("median_ttft_ms"),
                p99_ttft_ms=data.get("p99_ttft_ms"),
                mean_tpot_ms=data.get("mean_tpot_ms"),
                median_tpot_ms=data.get("median_tpot_ms"),
                p99_tpot_ms=data.get("p99_tpot_ms"),
                mean_e2e_latency_ms=data.get("mean_e2e_latency_ms"),
                median_e2e_latency_ms=data.get("median_e2e_latency_ms"),
                p99_e2e_latency_ms=data.get("p99_e2e_latency_ms"),
                completed=data.get("completed"),
                duration=data.get("duration"),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def cancel(self):
        import signal

        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        self._proc = None

    @staticmethod
    def _log_path(case_name: str) -> Path:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return LOGS_DIR / f"{case_name}_{ts}.log"
