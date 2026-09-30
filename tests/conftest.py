"""Manage a disposable application stack for the repository's HTTP/browser tests."""

import subprocess
from pathlib import Path
from uuid import uuid4

import pytest


class ComposeStack:
    def __init__(self, repo: Path):
        self.repo = repo
        self.project = f"notes-repo-test-{uuid4().hex[:12]}"
        self.compose = ["docker", "compose", "-p", self.project, "-f", str(repo / "compose.yaml")]
        try:
            result = subprocess.run(
                [*self.compose, "up", "--build", "--detach", "--wait", "--wait-timeout", "240"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=360,
            )
            if result.returncode:
                logs = subprocess.run(
                    [*self.compose, "logs", "api"], cwd=repo, capture_output=True, text=True, timeout=15,
                )
                raise RuntimeError(f"Compose startup failed:\n{result.stderr[-1000:]}\nAPI logs:\n{logs.stdout[-4000:]}{logs.stderr[-1000:]}")
            self.api_url = f"http://127.0.0.1:{self._port('api', 8000)}"
            self.web_url = f"http://127.0.0.1:{self._port('web', 80)}"
        except Exception:
            self.close()
            raise

    def _port(self, service: str, port: int) -> str:
        result = subprocess.run(
            [*self.compose, "port", service, str(port)],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip().splitlines()[-1].rsplit(":", 1)[-1]

    def close(self) -> None:
        subprocess.run(
            [*self.compose, "down", "--volumes", "--remove-orphans"],
            cwd=self.repo,
            capture_output=True,
            check=False,
            timeout=90,
        )

    def restart_api(self) -> None:
        subprocess.run([*self.compose, "restart", "api"], cwd=self.repo, check=True, timeout=60)
        subprocess.run(
            [*self.compose, "up", "--detach", "--wait", "--wait-timeout", "60", "api"],
            cwd=self.repo,
            check=True,
            timeout=90,
        )
        self.api_url = f"http://127.0.0.1:{self._port('api', 8000)}"


@pytest.fixture(scope="session")
def stack() -> ComposeStack:
    current = ComposeStack(Path(__file__).resolve().parents[1])
    try:
        yield current
    finally:
        current.close()


@pytest.fixture(scope="session")
def api_url(stack: ComposeStack) -> str:
    return stack.api_url


@pytest.fixture(scope="session")
def web_url(stack: ComposeStack) -> str:
    return stack.web_url
