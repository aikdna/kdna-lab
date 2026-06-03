"""KDNA Lab — Experiment Runner base classes and shared logic.

Features built for VPN/proxy environments:
  - Exponential backoff retry (3 attempts: 1s, 2s, 4s)
  - Network health check before run
  - Checkpoint/resume — never lose progress on network failure
  - Provider fallback chain — if primary fails, try backups
"""

import json
import multiprocessing
import os
import re
import subprocess
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional


# ---- Network Resilience ----

RETRY_BACKOFF = [1, 2, 4]          # seconds between retries
MAX_RETRIES = 3
HEALTH_CHECK_TIMEOUT = 10          # seconds
API_CALL_TIMEOUT = 60              # seconds


def _provider_call_worker(queue, call_kwargs: Dict[str, Any]) -> None:
    """Run a provider call in a child process so the parent can hard-timeout it."""
    try:
        from kdna_lab.providers import call_provider

        queue.put({"ok": True, "result": call_provider(**call_kwargs)})
    except Exception as e:
        queue.put({"ok": False, "error": str(e)})


def safe_filename_part(value: Any) -> str:
    """Convert arbitrary metadata into a stable filename segment."""
    text = str(value or "unknown").strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text)
    text = text.strip("-._")
    return text or "unknown"


def exponential_backoff(attempt: int) -> float:
    """Sleep with exponential backoff before retry."""
    if attempt < len(RETRY_BACKOFF):
        time.sleep(RETRY_BACKOFF[attempt])
    else:
        time.sleep(RETRY_BACKOFF[-1] * (2 ** (attempt - len(RETRY_BACKOFF) + 1)))


def check_network_health(base_url: str, api_key: str, timeout: int = HEALTH_CHECK_TIMEOUT) -> bool:
    """Quick health check — can we reach the API at all?

    Uses a short timeout to avoid blocking the run.
    Returns False gracefully on any failure.
    """
    import socket
    try:
        import urllib.request
        req = urllib.request.Request(
            base_url.rstrip('/') + '/v1/chat/completions',
            data=b'{"model":"gpt-4o","messages":[{"role":"user","content":"ping"}],"max_tokens":1}',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
        )
        socket.setdefaulttimeout(timeout)
        urllib.request.urlopen(req, timeout=timeout)
        socket.setdefaulttimeout(None)
        return True
    except Exception:
        socket.setdefaulttimeout(None)
        return False


class ExperimentRunner:
    """Base class for all KDNA Lab experiment runners.

    Network resilience built-in:
      - Exponential backoff retry on API failures
      - Network health check before batch runs
      - Checkpoint/resume: save progress every N cases, resume from checkpoint
      - Provider fallback: if primary fails, try backup providers in config

    Config keys:
      api.provider / api.model / api.base_url / api.api_key_env
      api.fallback_providers: [list of provider configs to try on failure]
      runners.<name>.retries: override MAX_RETRIES
      runners.<name>.checkpoint_every: save checkpoint every N cases (default 5)
    """

    def __init__(self, lab_root: Path, config: Dict[str, Any]):
        self.lab_root = lab_root
        self.config = config
        self.run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self._output_dir = None
        self._api_call_count = 0
        self._api_fail_count = 0
        self._checkpoint_path = None

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

    @property
    def checkpoint_path(self) -> Path:
        if self._checkpoint_path is None:
            self._checkpoint_path = self.output_dir / f"{self.run_id}_checkpoint.json"
        return self._checkpoint_path

    # ---- Network Health ----

    def health_check(self) -> bool:
        """Verify network connectivity before starting batch run."""
        api = self.config.get("api", {})
        base_url = api.get("base_url", "")
        api_key_env = api.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env, "")

        if not base_url or not api_key:
            return True  # Skip check if not configured

        print(f"[NET] Health check to {base_url} ... ", end="", flush=True)
        ok = check_network_health(base_url, api_key)
        print("OK" if ok else "FAILED")
        return ok

    def _call_provider_with_timeout(self, call_kwargs: Dict[str, Any], timeout: int | float | None) -> Optional[str]:
        """Run a provider call under a hard deadline in an isolated child process."""
        if not timeout:
            from kdna_lab.providers import call_provider

            return call_provider(**call_kwargs)

        start_methods = multiprocessing.get_all_start_methods()
        method = "fork" if "fork" in start_methods else start_methods[0]
        ctx = multiprocessing.get_context(method)
        queue = ctx.Queue(maxsize=1)
        proc = ctx.Process(target=_provider_call_worker, args=(queue, call_kwargs))
        proc.daemon = True
        proc.start()
        proc.join(float(timeout))

        if proc.is_alive():
            proc.terminate()
            proc.join(1)
            if proc.is_alive() and hasattr(proc, "kill"):
                proc.kill()
                proc.join(1)
            return None

        if queue.empty():
            return None
        payload = queue.get()
        if payload.get("ok"):
            return payload.get("result")
        return None

    # ---- API with Retry ----

    def call_api(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Call the configured LLM API with exponential backoff retry.

        On failure, tries up to MAX_RETRIES times with increasing delays.
        If primary provider fails, tries fallback_providers from config.
        """
        api = self.config.get("api", {})
        primary_provider = api.get("provider", "openai")
        primary_model = api.get("model", "gpt-4o")
        primary_base_url = api.get("base_url")
        primary_key_env = api.get("api_key_env", "OPENAI_API_KEY")
        temperature = api.get("temperature", 0.3)
        max_tokens = api.get("max_tokens", 4000)
        timeout = api.get("timeout", API_CALL_TIMEOUT)

        max_retries = self.config.get("runners", {}).get("domain", {}).get("retries", MAX_RETRIES)

        from kdna_lab.providers import call_provider

        providers_to_try = [{
            "provider": primary_provider,
            "model": primary_model,
            "base_url": primary_base_url,
            "api_key": os.environ.get(primary_key_env, ""),
        }]

        fallbacks = api.get("fallback_providers", [])
        for fb in fallbacks:
            providers_to_try.append({
                "provider": fb.get("provider", "openai_compatible"),
                "model": fb.get("model", "gpt-4o"),
                "base_url": fb.get("base_url"),
                "api_key": os.environ.get(fb.get("api_key_env", "OPENAI_API_KEY"), ""),
            })

        last_error = None
        for prov_idx, prov in enumerate(providers_to_try):
            if prov_idx > 0:
                print(f"    [FALLBACK] Trying provider #{prov_idx+1}: {prov['model']}")

            for attempt in range(max_retries):
                try:
                    call_kwargs = {
                        "provider_name": prov["provider"],
                        "prompt": prompt,
                        "model": prov["model"],
                        "system_prompt": system_prompt,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "api_key": prov["api_key"],
                        "base_url": prov["base_url"],
                        "timeout": timeout,
                    }
                    result = self._call_provider_with_timeout(call_kwargs, 0)  # 0 = skip process isolation, rely on SDK timeout
                    if result is not None:
                        self._api_call_count += 1
                        return result
                except Exception as e:
                    last_error = str(e)

                if attempt < max_retries - 1:
                    backoff = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                    time.sleep(backoff)

        self._api_fail_count += 1
        return None

    # ---- Checkpoint / Resume ----

    def save_checkpoint(self, results: List[Dict], completed_indices: List[int]):
        """Save incremental progress so failed runs can resume."""
        data = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "completed_count": len(results),
            "completed_indices": completed_indices,
            "results": results,
        }
        self.checkpoint_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def load_checkpoint(self) -> Optional[Dict]:
        """Load a previous checkpoint to resume from."""
        if not self.checkpoint_path.exists():
            return None
        try:
            return json.loads(self.checkpoint_path.read_text())
        except json.JSONDecodeError:
            return None

    def clear_checkpoint(self):
        """Remove checkpoint after successful completion."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()

    # ---- Metrics ----

    def network_metrics(self) -> Dict[str, Any]:
        """Return network reliability metrics for this run."""
        total = self._api_call_count + self._api_fail_count
        return {
            "api_calls": self._api_call_count,
            "api_failures": self._api_fail_count,
            "total_attempts": total,
            "reliability": round(self._api_call_count / total * 100) if total else 100,
        }

    # ---- Core Methods ----

    def save_output(self, case_id: str, output: str, **meta) -> str:
        """Save a single case output and return the file path."""
        ext = meta.pop("_ext", "txt")
        filename_parts = [self.run_id, safe_filename_part(case_id)]
        for key in ("Condition", "Provider", "Model"):
            if meta.get(key):
                filename_parts.append(safe_filename_part(meta[key]))
        filepath = self.raw_dir / f"{'_'.join(filename_parts)}.{ext}"
        with open(filepath, "w") as f:
            if "Case" not in meta:
                f.write(f"# Case: {case_id}\n")
            for key, val in meta.items():
                f.write(f"# {key}: {val}\n")
            f.write(f"# Timestamp: {datetime.now().isoformat()}\n")
            f.write("---\n")
            f.write(output)
        return str(filepath)

    def save_index(self, results: List[Dict]) -> str:
        """Save run index and return the path."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
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
        """Execute a worker function across items in parallel."""
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
