from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional

from .models import BenchResult, TestCase


class BenchRunner:
    def __init__(self, python_bin: Optional[str] = None):
        self.python_bin = python_bin or sys.executable

    def _build_command(self, case: TestCase, output_file: str) -> list[str]:
        args = case.to_bench_args()
        for i, a in enumerate(args):
            if a == "--output-file":
                args[i + 1] = output_file
                break
        return [self.python_bin, "-m", "sglang.bench_serving"] + args

    async def run(
        self, case: TestCase, on_output: Optional[callable] = None
    ) -> tuple[Optional[BenchResult], Optional[str]]:
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", prefix="faststress_", delete=False
        ) as f:
            output_file = f.name

        cmd = self._build_command(case, output_file)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output_lines = []
            async for line in self._read_stream(proc.stdout):
                output_lines.append(line)
                if on_output:
                    on_output(line)

            await proc.wait()

            if proc.returncode != 0:
                return None, "\n".join(output_lines)

            result = self._parse_result(output_file)
            return result, None
        except FileNotFoundError:
            return None, "sglang not found. Install with: pip install sglang[all]"
        except Exception as e:
            return None, str(e)

    async def run_stream(self, case: TestCase) -> AsyncIterator[str]:
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", prefix="faststress_", delete=False
        ) as f:
            output_file = f.name

        cmd = self._build_command(case, output_file)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in self._read_stream(proc.stdout):
            yield line

        await proc.wait()
        if proc.returncode == 0:
            yield f"\n__RESULT_FILE__:{output_file}"
        else:
            yield f"\n__ERROR__:Process exited with code {proc.returncode}"

    @staticmethod
    async def _read_stream(stream: asyncio.StreamReader) -> AsyncIterator[str]:
        while True:
            line = await stream.readline()
            if not line:
                break
            yield line.decode("utf-8", errors="replace").rstrip("\n")

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

    def cancel(self, proc: asyncio.subprocess.Process):
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
