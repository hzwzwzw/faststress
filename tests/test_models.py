from faststress.models import (
    Backend,
    BenchResult,
    DatasetConfig,
    DatasetType,
    GspParams,
    LoadConfig,
    RandomIdsParams,
    ServerConfig,
    SharegptParams,
    TestCase,
)


class TestToArgs:
    def test_random_ids_default(self):
        case = TestCase(name="test1")
        args = case.to_bench_args()
        assert "--backend" in args
        assert "sglang" in args
        assert "--dataset-name" in args
        assert "random-ids" in args
        assert "--random-input-len" in args
        assert "1024" in args
        assert "--random-output-len" in args
        assert "128" in args
        assert "--num-prompts" in args
        assert "100" in args

    def test_random_ids_custom(self):
        case = TestCase(
            name="custom",
            dataset=DatasetConfig(
                dataset_type=DatasetType.RANDOM_IDS,
                random_ids=RandomIdsParams(input_len=2048, output_len=256, range_ratio=0.5),
            ),
        )
        args = case.to_bench_args()
        assert "2048" in args
        assert "256" in args
        assert "0.5" in args

    def test_sharegpt(self):
        case = TestCase(
            name="sgpt",
            dataset=DatasetConfig(
                dataset_type=DatasetType.SHAREGPT,
                sharegpt=SharegptParams(dataset_path="/data/sg.json", output_len=512),
            ),
        )
        args = case.to_bench_args()
        assert "--dataset-name" in args
        assert "sharegpt" in args
        assert "--dataset-path" in args
        assert "/data/sg.json" in args
        assert "--sharegpt-output-len" in args
        assert "512" in args

    def test_sharegpt_no_optional(self):
        case = TestCase(
            name="sgpt2",
            dataset=DatasetConfig(
                dataset_type=DatasetType.SHAREGPT,
                sharegpt=SharegptParams(dataset_path="/data/sg.json"),
            ),
        )
        args = case.to_bench_args()
        assert "--sharegpt-output-len" not in args
        assert "--sharegpt-context-len" not in args

    def test_gsp(self):
        case = TestCase(
            name="gsp",
            dataset=DatasetConfig(
                dataset_type=DatasetType.GENERATED_SHARED_PREFIX,
                gsp=GspParams(num_groups=8, prompts_per_group=16, output_len=64),
            ),
        )
        args = case.to_bench_args()
        assert "generated-shared-prefix" in args
        assert "--gsp-num-groups" in args
        assert "8" in args
        assert "--gsp-prompts-per-group" in args
        assert "16" in args
        assert "--gsp-output-len" in args
        assert "64" in args

    def test_gsp_zipf(self):
        case = TestCase(
            name="gsp-zipf",
            dataset=DatasetConfig(
                dataset_type=DatasetType.GENERATED_SHARED_PREFIX,
                gsp=GspParams(group_distribution="zipf", zipf_alpha=1.5),
            ),
        )
        args = case.to_bench_args()
        assert "--gsp-group-distribution" in args
        assert "zipf" in args
        assert "--gsp-zipf-alpha" in args
        assert "1.5" in args

    def test_server_base_url(self):
        case = TestCase(
            name="url",
            server=ServerConfig(base_url="http://10.0.0.1:8080"),
        )
        args = case.to_bench_args()
        assert "--base-url" in args
        assert "http://10.0.0.1:8080" in args
        assert "--host" not in args
        assert "--port" not in args

    def test_server_host_port(self):
        case = TestCase(
            name="hp",
            server=ServerConfig(host="192.168.1.1", port=8000),
        )
        args = case.to_bench_args()
        assert "--host" in args
        assert "192.168.1.1" in args
        assert "--port" in args
        assert "8000" in args

    def test_load_config(self):
        case = TestCase(
            name="load",
            load=LoadConfig(request_rate=10.5, max_concurrency=32, num_prompts=200),
        )
        args = case.to_bench_args()
        assert "--request-rate" in args
        assert "10.5" in args
        assert "--max-concurrency" in args
        assert "32" in args
        assert "--num-prompts" in args
        assert "200" in args

    def test_load_inf_rate(self):
        case = TestCase(name="inf")
        args = case.to_bench_args()
        idx = args.index("--request-rate")
        assert args[idx + 1] == "inf"

    def test_backend_oai(self):
        case = TestCase(name="oai", server=ServerConfig(backend=Backend.SGLANG_OAI))
        args = case.to_bench_args()
        assert "sglang-oai" in args

    def test_api_key_env(self):
        case = TestCase(name="key", server=ServerConfig(api_key="sk-test123"))
        env = case.get_env()
        assert env == {"OPENAI_API_KEY": "sk-test123"}

    def test_no_api_key_env(self):
        case = TestCase(name="nokey")
        assert case.get_env() is None


class TestServerFromEnv:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("FASTSTRESS_SERVER_HOST", "10.0.0.5")
        monkeypatch.setenv("FASTSTRESS_SERVER_PORT", "9000")
        monkeypatch.setenv("FASTSTRESS_SERVER_BACKEND", "sglang-oai")
        monkeypatch.setenv("FASTSTRESS_SERVER_BASE_URL", "http://myserver:8080")
        monkeypatch.setenv("FASTSTRESS_SERVER_API_KEY", "sk-envkey")
        cfg = ServerConfig.from_env()
        assert cfg.host == "10.0.0.5"
        assert cfg.port == 9000
        assert cfg.backend == Backend.SGLANG_OAI
        assert cfg.base_url == "http://myserver:8080"
        assert cfg.api_key == "sk-envkey"

    def test_from_env_empty(self):
        cfg = ServerConfig.from_env()
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 30000


class TestBenchResult:
    def test_all_none(self):
        r = BenchResult()
        assert r.request_throughput is None
        assert r.median_ttft_ms is None

    def test_partial_values(self):
        r = BenchResult(request_throughput=50.0, median_ttft_ms=100.0)
        assert r.request_throughput == 50.0
        assert r.p99_ttft_ms is None

    def test_format_helper(self):
        from faststress.app import _fmt
        assert _fmt(None) == "N/A"
        assert _fmt(3.14159) == "3.1"
        assert _fmt(0.0) == "0.0"
        assert _fmt(100.0, "ms") == "100.0ms"
        assert _fmt(None, "ms") == "N/A"


class TestServerConfig:
    def test_effective_url_with_base(self):
        s = ServerConfig(base_url="http://custom:9000")
        assert s.effective_url() == "http://custom:9000"

    def test_effective_url_without_base(self):
        s = ServerConfig(host="10.0.0.1", port=8080)
        assert s.effective_url() == "http://10.0.0.1:8080"
