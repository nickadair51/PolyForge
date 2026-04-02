import time
import docker
from polyforge.models import RepoSnapshot, ExecutionResult
from polyforge.config import PolyForgeConfig


# Project type → (image, build+test command)
DOCKER_PROFILES = {
    "node":   ("node:20-alpine",       "npm ci && npm test"),
    "python": ("python:3.11-slim",     "pip install -r requirements.txt -q && pytest"),
    "maven":  ("maven:3.9-openjdk-17", "mvn test -B"),
    "gradle": ("gradle:8-jdk17",       "gradle test --no-daemon"),
    "rust":   ("rust:1.75-slim",       "cargo test"),
}


class DockerExecutor:
    def __init__(self, config: PolyForgeConfig):
        self._client = docker.from_env()
        self._timeout = config.execution.docker_timeout_seconds
        self._memory_limit = config.docker.memory_limit
        self._nano_cpus = config.docker.cpu_cores * 1_000_000_000

    async def execute(self, snapshot: RepoSnapshot) -> ExecutionResult:
        """Run the snapshot in a Docker container and capture results."""
        profile = DOCKER_PROFILES.get(snapshot.project_type)
        if not profile:
            return self._error_result(snapshot, f"No Docker profile for project type: {snapshot.project_type}")

        image, command = profile
        container = None
        start_time = time.perf_counter()

        try:
            container = self._client.containers.run(
                image=image,
                command=["sh", "-c", command],
                volumes={snapshot.snapshot_path: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                network_disabled=True,
                mem_limit=self._memory_limit,
                nano_cpus=self._nano_cpus,
                detach=True,
            )

            result = container.wait(timeout=self._timeout)
            runtime_ms = int((time.perf_counter() - start_time) * 1000)

            stdout = container.logs(stdout=True, stderr=False).decode(errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode(errors="replace")
            exit_code = result.get("StatusCode", -1)

            return ExecutionResult(
                query_id=snapshot.query_id,
                provider=snapshot.provider,
                success=exit_code == 0,
                build_passed=exit_code == 0,
                tests_passed=0,
                tests_failed=0,
                tests_errored=0,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                runtime_ms=runtime_ms,
                timed_out=False,
                error=None,
            )

        except Exception as e:
            runtime_ms = int((time.perf_counter() - start_time) * 1000)
            timed_out = "timed out" in str(e).lower() or "read timed out" in str(e).lower()

            return ExecutionResult(
                query_id=snapshot.query_id,
                provider=snapshot.provider,
                success=False,
                build_passed=False,
                tests_passed=0,
                tests_failed=0,
                tests_errored=0,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                runtime_ms=runtime_ms,
                timed_out=timed_out,
                error=str(e),
            )

        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _error_result(self, snapshot: RepoSnapshot, error: str) -> ExecutionResult:
        return ExecutionResult(
            query_id=snapshot.query_id,
            provider=snapshot.provider,
            success=False,
            build_passed=False,
            tests_passed=0,
            tests_failed=0,
            tests_errored=0,
            exit_code=-1,
            stdout="",
            stderr="",
            runtime_ms=0,
            timed_out=False,
            error=error,
        )
