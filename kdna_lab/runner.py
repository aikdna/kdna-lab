"""KDNA Lab — Experiment Runner base classes and shared logic."""

import json
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional


class ExperimentRunner:
    """Base class for all KDNA Lab experiment runners.

    Subclasses implement `run_all()` which processes cases and
    returns result dicts. The base class handles case loading,
    output saving, run indexing, progress reporting, and parallel
    execution.

    Parallel execution: set `config.runners.<name>.workers` to a number
    > 1 to enable concurrent API calls. Default is 1 (sequential).
    """

    def __init__(self, lab_root: Path, config: Dict[str, Any]):
        self.lab_root = lab_root
        self.config = config
        self.run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self._output_dir = None

    @property
    def output_dir(self) -> Path:
        if self._output_dir is None:
            d = self.config.get("output", {}).get("dir", "outputs")
            if not os.path.isabs(d):
                d = str(self.lab_root / d)
            self._output_dir = Path(d)
        return self._output_dir

    @property
    def raw_dir(self) -> Path:
        d = self.output_dir / "raw"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_output(self, case_id: str, output: str, **meta) -> str:
        """Save a single case output and return the file path."""
        ext = meta.pop("_ext", "txt")
        filepath = self.raw_dir / f"{self.run_id}_{case_id}.{ext}"
        with open(filepath, "w") as f:
            for key, val in meta.items():
                f.write(f"# {key}: {val}\n")
            f.write(f"# Timestamp: {datetime.now().isoformat()}\n")
            f.write("---\n")
            f.write(output)
        return str(filepath)

    def save_index(self, results: List[Dict]) -> str:
        """Save run index and return the path."""
        index_path = self.output_dir / f"{self.run_id}_index.json"
        with open(index_path, "w") as f:
            json.dump([{
                "run_id": r.get("run_id", self.run_id),
                "case_id": r["case_id"],
                "condition": r.get("condition", ""),
                "output_path": r.get("output_path", ""),
                "exit_code": r.get("exit_code"),
                "expected_exit_code": r.get("expected_exit_code"),
                "exit_ok": r.get("exit_ok"),
                "L1_pass": r.get("L1_pass"),
                "missing": r.get("missing", []),
                "violations": r.get("violations", []),
            } for r in results], f, indent=2, ensure_ascii=False)
        return str(index_path)

    def load_domain_prompt(self, domain_name: str) -> Optional[str]:
        """Load a KDNA domain as a prompt string via CLI."""
        result = subprocess.run(
            ["kdna", "load", domain_name, "--as=prompt"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout

    def call_api(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Call the configured LLM API via the multi-provider adapter."""
        api = self.config.get("api", {})
        provider = api.get("provider", "openai")
        model = api.get("model", "gpt-4o")
        api_key = os.environ.get(api.get("api_key_env", "OPENAI_API_KEY"), "")
        base_url = api.get("base_url")
        temperature = api.get("temperature", 0.3)
        max_tokens = api.get("max_tokens", 4000)

        from kdna_lab.providers import call_provider

        return call_provider(
            provider_name=provider,
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
        )

    def run_all(self, cases: List[dict]) -> List[dict]:
        """Run all cases. Override in subclasses for custom logic."""
        raise NotImplementedError

    def run_parallel(
        self,
        items: List[Any],
        worker_fn: Callable[[Any, int], Optional[Dict]],
        max_workers: int = 4,
        rate_limit: float = 0.0,
    ) -> List[Dict]:
        """Execute a worker function across items in parallel.

        Args:
            items: List of items to process
            worker_fn: Function(item, index) -> Optional[Dict] result
            max_workers: Number of parallel threads
            rate_limit: Seconds to sleep before each worker (for rate limiting)

        Returns:
            List of result dicts (None results filtered out), in original order.
        """
        if max_workers <= 1:
            results = []
            for i, item in enumerate(items):
                r = worker_fn(item, i)
                if r is not None:
                    results.append(r)
            return results

        results_map: Dict[int, Dict] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, item in enumerate(items):
                if rate_limit > 0 and i > 0:
                    time.sleep(rate_limit)
                futures[executor.submit(worker_fn, item, i)] = i

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    r = future.result()
                    if r is not None:
                        results_map[idx] = r
                except Exception:
                    pass

        return [results_map[i] for i in sorted(results_map.keys())]

    def get_workers(self, runner_name: str = "domain") -> int:
        """Get configured worker count for parallel execution."""
        return self.config.get("runners", {}).get(runner_name, {}).get("workers", 1)
