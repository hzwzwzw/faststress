from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable, Optional

from .models import BenchResult, LoadConfig, TestCase
from .runner import BenchRunner


@dataclass
class SLOTarget:
    max_ttft_ms: float = 500.0
    max_tpot_ms: float = 50.0
    use_p99: bool = False


@dataclass
class SearchConfig:
    rate_min: float = 1.0
    rate_max: float = 100.0
    rate_step: float = 5.0
    concurrency_min: int = 1
    concurrency_max: int = 128
    concurrency_step: int = 8
    num_prompts: int = 50


@dataclass
class SearchResult:
    rate: float
    concurrency: Optional[int]
    result: BenchResult
    meets_slo: bool


@dataclass
class OptimizationResult:
    best: Optional[SearchResult] = None
    history: list[SearchResult] = field(default_factory=list)
    stopped: bool = False


class Optimizer:
    def __init__(self, base_case: TestCase, slo: SLOTarget, search: SearchConfig):
        self.base_case = base_case
        self.slo = slo
        self.search = search
        self.runner = BenchRunner()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _check_slo(self, result: BenchResult) -> bool:
        if self.slo.use_p99:
            ttft = result.p99_ttft_ms
            tpot = result.p99_tpot_ms
        else:
            ttft = result.median_ttft_ms
            tpot = result.median_tpot_ms

        if ttft is None or tpot is None:
            return False
        return ttft <= self.slo.max_ttft_ms and tpot <= self.slo.max_tpot_ms

    def _make_case(self, rate: float, concurrency: Optional[int]) -> TestCase:
        case = self.base_case.model_copy(deep=True)
        case.load = LoadConfig(
            request_rate=rate,
            max_concurrency=concurrency,
            num_prompts=self.search.num_prompts,
        )
        return case

    async def search_grid(
        self,
        on_progress: Optional[Callable[[SearchResult], None]] = None,
    ) -> OptimizationResult:
        """Grid search over rate and concurrency to find max throughput within SLO."""
        result = OptimizationResult()

        rates = self._generate_rates()
        concurrencies = self._generate_concurrencies()

        for rate in rates:
            if self._cancelled:
                result.stopped = True
                break
            for conc in concurrencies:
                if self._cancelled:
                    result.stopped = True
                    break

                case = self._make_case(rate, conc)
                bench_result, error = await self.runner.run(case)

                if bench_result is None:
                    continue

                meets = self._check_slo(bench_result)
                sr = SearchResult(
                    rate=rate, concurrency=conc, result=bench_result, meets_slo=meets
                )
                result.history.append(sr)

                if on_progress:
                    on_progress(sr)

                if meets:
                    if result.best is None or (
                        bench_result.request_throughput
                        and (result.best.result.request_throughput or 0)
                        < bench_result.request_throughput
                    ):
                        result.best = sr

        return result

    async def search_binary(
        self,
        on_progress: Optional[Callable[[SearchResult], None]] = None,
    ) -> OptimizationResult:
        """Binary search: first find max rate, then max concurrency."""
        result = OptimizationResult()

        best_rate = await self._binary_search_rate(result, on_progress)
        if self._cancelled or best_rate is None:
            result.stopped = self._cancelled
            return result

        best_conc = await self._binary_search_concurrency(
            best_rate, result, on_progress
        )
        if self._cancelled:
            result.stopped = True

        return result

    async def _binary_search_rate(
        self,
        result: OptimizationResult,
        on_progress: Optional[Callable[[SearchResult], None]],
    ) -> Optional[float]:
        lo, hi = self.search.rate_min, self.search.rate_max
        best_rate = None

        while hi - lo > self.search.rate_step:
            if self._cancelled:
                return best_rate
            mid = (lo + hi) / 2
            case = self._make_case(mid, None)
            bench_result, _ = await self.runner.run(case)

            if bench_result is None:
                hi = mid
                continue

            meets = self._check_slo(bench_result)
            sr = SearchResult(rate=mid, concurrency=None, result=bench_result, meets_slo=meets)
            result.history.append(sr)
            if on_progress:
                on_progress(sr)

            if meets:
                best_rate = mid
                result.best = sr
                lo = mid
            else:
                hi = mid

        return best_rate

    async def _binary_search_concurrency(
        self,
        rate: float,
        result: OptimizationResult,
        on_progress: Optional[Callable[[SearchResult], None]],
    ) -> Optional[int]:
        lo, hi = self.search.concurrency_min, self.search.concurrency_max
        best_conc = None

        while hi - lo > self.search.concurrency_step:
            if self._cancelled:
                return best_conc
            mid = (lo + hi) // 2
            case = self._make_case(rate, mid)
            bench_result, _ = await self.runner.run(case)

            if bench_result is None:
                hi = mid
                continue

            meets = self._check_slo(bench_result)
            sr = SearchResult(rate=rate, concurrency=mid, result=bench_result, meets_slo=meets)
            result.history.append(sr)
            if on_progress:
                on_progress(sr)

            if meets:
                best_conc = mid
                if (
                    bench_result.request_throughput
                    and (result.best is None or (result.best.result.request_throughput or 0) < bench_result.request_throughput)
                ):
                    result.best = sr
                lo = mid
            else:
                hi = mid

        return best_conc

    def _generate_rates(self) -> list[float]:
        rates = []
        r = self.search.rate_min
        while r <= self.search.rate_max:
            rates.append(r)
            r += self.search.rate_step
        return rates

    def _generate_concurrencies(self) -> list[Optional[int]]:
        concs: list[Optional[int]] = [None]
        c = self.search.concurrency_min
        while c <= self.search.concurrency_max:
            concs.append(c)
            c += self.search.concurrency_step
        return concs
