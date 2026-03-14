import typer, os, asyncio, uuid
from pathlib import Path
from datetime import datetime
from polyforge.config import load_config
from polyforge.models import QueryRequest

app = typer.Typer()
SUPPORTED_MODELS = ["claude", "gpt4o", "gemini"]


@app.callback(invoke_without_command=True)
def welcome():
    typer.echo()
    typer.secho("[PolyForge] v1.0", fg=typer.colors.CYAN, bold=True)
    typer.echo()


@app.command()
def run(
      repo: str = typer.Option(..., help="Path to local repository"),
      models: str = typer.Option("claude,gpt4o,gemini", help="Comma-separated list of models"),
      manual_select: bool = typer.Option(False, help="Skip file selection assistant"),
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

    # Scan repo for project type
    repo_path = os.path.abspath(repo)
    typer.secho(f"[PolyForge] Scanning repository: {repo_path}", fg=typer.colors.CYAN)

    # TODO: Detect project type (repo/detector.py)
    # TODO: Scan file tree and extract signatures (repo/scanner.py)

    if manual_select:
        typer.secho("[PolyForge] Manual file selection mode", fg=typer.colors.YELLOW)
        file_input = typer.prompt("Enter file names (comma separated)")
        selected_files = [Path(f.strip()) for f in file_input.split(",")]
        if len(selected_files) > config.execution.max_files:
            typer.secho(f"Error: At the time being, PolyForge only accepts 5"
                        "files to minimize costs. Removing the following files from selection:\n", fg=typer.colors.RED, bold=True, err=True)
            for file_to_be_removed in selected_files[5:]:
                typer.secho(file_to_be_removed)
            selected_files = selected_files[:5]
    else:
        typer.secho("[PolyForge] Running File Selection Assistant...", fg=typer.colors.CYAN)
        # TODO: Run FileSelectionAssistant (llm_components/file_selection.py)
        selected_files = []

    # Confirm with the user that the files selected are the ones to be used in the query
    # TODO: Display selected files, token estimates, cost estimate
    typer.confirm("\nConfirm these files?", abort=True)

    typer.echo()
    question = typer.prompt("What is your question?")

    query_request = QueryRequest(
        repo_path=repo_path,
        question=question,
        selected_files=selected_files,
        selected_models=selected_models,
        query_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
    )

    typer.echo()
    typer.secho("[PolyForge] Sending to models...", fg=typer.colors.CYAN)

    # TODO: Hand off to orchestrator
    # result = asyncio.run(orchestrator.run(query_request, config))

    # TODO: Render results
    # renderer.display(result)

    typer.echo()
    typer.secho("[PolyForge] Done.", fg=typer.colors.GREEN, bold=True)


if __name__ == "__main__":
    app()