import os
import shutil
import difflib
from pathlib import Path
from polyforge.models import LLMResponse, RepoSnapshot, PatchResult


class RepoManager:
    def __init__(self, repo_path: str, workspace_base: str, query_id: str):
        self._repo_path = Path(repo_path)
        self._workspace_dir = Path(workspace_base) / query_id
        self._query_id = query_id

    def create_snapshot(self, provider: str) -> str:
        """Copy the full repo into a provider-specific snapshot directory."""
        snapshot_path = self._workspace_dir / f"snapshot_{provider}"
        shutil.copytree(self._repo_path, snapshot_path)
        return str(snapshot_path)

    def apply_patch(self, snapshot_path: str, response: LLMResponse) -> PatchResult:
        """Write each modified/new file into the snapshot and generate a diff."""
        files_modified = []
        files_created = []

        for filename, new_content in response.modified_files.items():
            target = Path(snapshot_path) / filename
            original_exists = target.exists()

            os.makedirs(target.parent, exist_ok=True)
            target.write_text(new_content)

            if original_exists:
                files_modified.append(filename)
            else:
                files_created.append(filename)

        diff = self._generate_diff(snapshot_path)

        return PatchResult(
            provider=response.provider,
            snapshot_path=snapshot_path,
            diff=diff,
            files_modified=files_modified,
            files_created=files_created,
        )

    def build_repo_snapshot(self, response: LLMResponse, project_type: str) -> RepoSnapshot:
        """Create snapshot, apply patch, and return a RepoSnapshot."""
        snapshot_path = self.create_snapshot(response.provider)
        patch = self.apply_patch(snapshot_path, response)

        return RepoSnapshot(
            query_id=self._query_id,
            provider=response.provider,
            snapshot_path=snapshot_path,
            diff=patch.diff,
            project_type=project_type,
        )

    def cleanup(self):
        """Remove the entire workspace directory for this query."""
        if self._workspace_dir.exists():
            shutil.rmtree(self._workspace_dir)

    def _generate_diff(self, snapshot_path: str) -> str:
        """Unified diff between the original repo and the patched snapshot."""
        diffs = []
        snapshot = Path(snapshot_path)

        for snap_file in snapshot.rglob("*"):
            if not snap_file.is_file():
                continue

            relative = snap_file.relative_to(snapshot)
            original = self._repo_path / relative

            snap_lines = snap_file.read_text(errors="replace").splitlines(keepends=True)

            if original.exists():
                orig_lines = original.read_text(errors="replace").splitlines(keepends=True)
            else:
                orig_lines = []

            if orig_lines != snap_lines:
                diff = difflib.unified_diff(
                    orig_lines,
                    snap_lines,
                    fromfile=f"a/{relative}",
                    tofile=f"b/{relative}",
                )
                diffs.append("".join(diff))

        return "\n".join(diffs)
