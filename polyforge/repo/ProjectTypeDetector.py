from pathlib import Path

"Very rudimentary file detector. For the MVP, we are just hard coding"
"the docker profiles based on the kind of manifest file is associated with the inputted repo."
"The user can specify what kind of project they are working on in the cofig file if their"
"project does not align with one of these project types."

class ProjectTypeDetector:
    def __init__(self, repo_root: Path):
        self._repo_root = repo_root

    
    def detect(self) -> str | None:
        if (self._repo_root / "pom.xml").exists():
            return "maven"
        if (self._repo_root / "build.gradle").exists():
            return "gradle"
        if (self._repo_root / "package.json").exists():
            return "node"
        if ((self._repo_root / "requirements.txt").exists()
            or (self._repo_root / "pyproject.toml").exists()):
            return "python"
        if (self._repo_root / "Cargo.toml").exists():
            return "rust"
 
        return None