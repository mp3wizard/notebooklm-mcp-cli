"""Download tools - Consolidated download_artifact for all artifact types."""

import asyncio

from ...services import ServiceError, ValidationError
from ...services import downloads as downloads_service
from ._utils import ResultDict, coerce_list, error_result, get_client, logged_tool


@logged_tool()
def download_artifact(
    notebook_id: str,
    artifact_type: str,
    output_path: str,
    artifact_id: str | None = None,
    output_format: str = "json",
    slide_deck_format: str = "pdf",
) -> ResultDict:
    """Download any NotebookLM artifact to a file.

    Unified download tool replacing 9 separate download tools.
    Supports all artifact types: audio, video, report, mind_map, slide_deck,
    infographic, data_table, quiz, flashcards.

    Args:
        notebook_id: Notebook UUID
        artifact_type: Type of artifact to download:
            - audio: Audio Overview (MP4/MP3)
            - video: Video Overview (MP4)
            - report: Report (Markdown)
            - mind_map: Mind Map (JSON)
            - slide_deck: Slide Deck (PDF or PPTX)
            - infographic: Infographic (PNG)
            - data_table: Data Table (CSV)
            - quiz: Quiz (json|markdown|html)
            - flashcards: Flashcards (json|markdown|html)
        output_path: Path to save the file
        artifact_id: Optional specific artifact ID (uses latest if not provided)
        output_format: For quiz/flashcards only: json|markdown|html (default: json)
        slide_deck_format: For slide_deck only: pdf (default) or pptx

    Returns:
        dict with status and saved file path

    Example:
        download_artifact(notebook_id="abc123", artifact_type="audio", output_path="podcast.mp3")
        download_artifact(notebook_id="abc123", artifact_type="quiz", output_path="quiz.html", output_format="html")
        download_artifact(notebook_id="abc123", artifact_type="slide_deck", output_path="slides.pptx", slide_deck_format="pptx")
    """
    try:
        client = get_client()
        download_result = asyncio.run(
            downloads_service.download_async(
                client,
                notebook_id,
                artifact_type,
                output_path,
                artifact_id=artifact_id,
                output_format=output_format,
                slide_deck_format=slide_deck_format,
            )
        )
        return {"status": "success", **download_result}
    except ValidationError as e:
        message = str(e)
        if message.startswith("Unknown artifact type "):
            message = message.replace("Unknown artifact type", "Unknown artifact_type", 1)
        return error_result(message)
    except ServiceError as e:
        return error_result(e.user_message, hint=e.hint)
    except Exception as e:
        return error_result(str(e))


@logged_tool()
def download_all_artifacts(
    notebook_id: str | None = None,
    output_dir: str = ".",
    artifact_types: list[str] | str | None = None,
    output_format: str = "json",
    slide_deck_format: str = "pdf",
    all_notebooks: bool = False,
    skip_existing: bool = False,
) -> ResultDict:
    """Download all completed studio artifacts of one notebook — or every notebook.

    Creates a subdirectory of output_dir named after each notebook title and
    saves every completed artifact there, named after its title with the
    type's default extension (report → .md, mind_map → .json, video → .mp4,
    slide_deck → .pdf/.pptx, ...). Artifacts that are still generating or
    failed are skipped and listed in the result. A failure on one artifact
    (or one notebook in a sweep) does not stop the others.

    Args:
        notebook_id: Notebook UUID (omit when all_notebooks=True)
        output_dir: Base directory for the per-notebook folders (default: cwd)
        artifact_types: Restrict to these types, e.g. ["video", "slide_deck",
            "mind_map", "report"]. Default: all types.
        output_format: For quiz/flashcards only: json|markdown|html
        slide_deck_format: For slide decks only: pdf (default) or pptx
        all_notebooks: Sweep every notebook in the account instead of one
        skip_existing: Skip artifacts whose target file already exists —
            makes repeated runs incremental

    Returns:
        dict with status, output_dir, and per-artifact items (single notebook)
        or per-notebook outcomes (sweep), plus downloaded/failed counts

    Example:
        download_all_artifacts(notebook_id="abc123", output_dir="exports")
        download_all_artifacts(all_notebooks=True, output_dir="exports", skip_existing=True)
    """
    if all_notebooks == (notebook_id is not None):
        return error_result("Provide either notebook_id or all_notebooks=True (not both).")
    try:
        client = get_client()
        if all_notebooks:
            result = asyncio.run(
                downloads_service.download_all_notebooks(
                    client,
                    output_dir,
                    artifact_types=coerce_list(artifact_types),
                    output_format=output_format,
                    slide_deck_format=slide_deck_format,
                    skip_existing=skip_existing,
                )
            )
        else:
            result = asyncio.run(
                downloads_service.download_all(
                    client,
                    notebook_id,
                    output_dir,
                    artifact_types=coerce_list(artifact_types),
                    output_format=output_format,
                    slide_deck_format=slide_deck_format,
                    skip_existing=skip_existing,
                )
            )
        problems = result["failed"] + result.get("errored_notebooks", 0)
        if problems == 0:
            status = "success"
        elif result["downloaded"] > 0:
            status = "partial"
        else:
            status = "error"
        return {"status": status, **result}
    except ValidationError as e:
        return error_result(str(e))
    except ServiceError as e:
        return error_result(e.user_message, hint=e.hint)
    except Exception as e:
        return error_result(str(e))
