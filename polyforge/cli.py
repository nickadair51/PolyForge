import typer, os, asyncio, uuid
from pathlib import Path
from datetime import datetime
from polyforge.config import load_config
from polyforge.models import QueryRequest
from polyforge.repo.ProjectTypeDetector import ProjectTypeDetector
from polyforge.Orchestrator import Orchestrator

app = typer.Typer()
SUPPORTED_MODELS = ["claude", "gpt4o", "openai", "chatgpt", "gemini"]

@app.command()
def run(
      repo: str = typer.Option(..., help="Path to local repository"),
      models: str = typer.Option("claude,gpt4o,gemini", help="Comma-separated list of models")
  ):
    if not os.path.isdir(repo):
        typer.secho(f"Error: '{repo}' is not a valid directory.", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(code=1)

    selected_models = [m.strip() for m in models.split(",")]
    for model in selected_models:
        if model not in SUPPORTED_MODELS:
            typer.secho(f"Error: Unsupported model '{model}'. Supported: {', '.join(SUPPORTED_MODELS)}.", fg=typer.colors.RED, bold=True, err=True)
            raise typer.Exit(code=1)

    config = load_config()

    # Scan repo for project type. The kind of repo is needed to create the docker container
    repo_path = Path(repo)
    typer.secho(f"[PolyForge] Scanning repository: {repo_path}", fg=typer.colors.CYAN)

    project_type_detector = ProjectTypeDetector(repo_path)
    project_type = project_type_detector.detect() #going to be used for docker
    typer.secho(f"Your repo is of type {project_type}   to be removed later (just used for testing)")

    typer.echo()
    question = typer.prompt("What is your question?")

    typer.echo()
    typer.secho("[PolyForge] Input up to 5 files (relative path) that relate to your question", fg=typer.colors.YELLOW)
    typer.echo()

    file_input = typer.prompt("Enter file names (comma separated)")
    selected_files = [Path(f.strip()) for f in file_input.split(",")]
    if len(selected_files) > config.execution.max_files:
        typer.secho(f"Error: At the time being, PolyForge only accepts 5"
                    "files to minimize costs. Removing the following files from selection:\n", fg=typer.colors.RED, bold=True, err=True)
        for file_to_be_removed in selected_files[5:]:
            typer.secho(file_to_be_removed)
        selected_files = selected_files[:5]

    query_request = QueryRequest(
        repo_path=repo_path,
        question=question,
        selected_files=selected_files,
        selected_models=selected_models,
        query_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
    )

    orchestrator = Orchestrator(query_request, config, project_type)

    cost_of_query = asyncio.run(orchestrator.estimate_cost_of_query())
    typer.confirm(f"\nThe price of your query is estimated to be {cost_of_query}\nIs this acceptable?", abort=True)

    typer.echo()
    typer.secho("[PolyForge] Sending to models...", fg=typer.colors.CYAN)

    llm_responses, exec_results = asyncio.run(orchestrator.run())

    typer.echo()
    for resp in llm_responses:
        typer.secho(f"\n--- {resp.provider} (LLM) ---", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"  Success: {resp.success}")
        typer.echo(f"  Latency: {resp.latency_ms}ms")
        typer.echo(f"  Cost: ${resp.cost:.4f}")
        if resp.error:
            typer.secho(f"  Error: {resp.error}", fg=typer.colors.RED)

    for result in exec_results:
        typer.secho(f"\n--- {result.provider} (Docker) ---", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"  Success: {result.success}")
        typer.echo(f"  Exit code: {result.exit_code}")
        typer.echo(f"  Runtime: {result.runtime_ms}ms")
        typer.echo(f"  Timed out: {result.timed_out}")
        if result.error:
            typer.secho(f"  Error: {result.error}", fg=typer.colors.RED)
        if result.stdout:
            typer.echo(f"  Stdout:\n{result.stdout[:2000]}")
        if result.stderr:
            typer.echo(f"  Stderr:\n{result.stderr[:2000]}")

    typer.echo()
    typer.secho("[PolyForge] Done.", fg=typer.colors.GREEN, bold=True)


if __name__ == "__main__":
    app()