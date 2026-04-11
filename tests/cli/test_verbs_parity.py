"""Test that verb wrappers pass all parameters their target functions accept.

When a verb wrapper calls a target function directly (not through Typer),
any parameter not explicitly passed gets the raw typer.Option default
(an OptionInfo object) instead of the resolved value. This test catches
missing parameters so they can't silently break CLI commands.
"""

import inspect

import pytest


def _collect_pairs():
    """Build the list of verb/target pairs by inspecting verbs.py imports and calls."""
    from notebooklm_tools.cli.commands import (
        alias,
        download,
        notebook,
        research,
        source,
        studio,
        verbs,
    )

    # Each entry: (verb_func_name, verb_func, target_func, skip_set)
    # skip_set contains params the verb handles differently (e.g. wraps in a list)
    pairs = [
        ("create_audio_verb", verbs.create_audio_verb, studio.create_audio, set()),
        ("create_video_verb", verbs.create_video_verb, studio.create_video, set()),
        ("create_report_verb", verbs.create_report_verb, studio.create_report, set()),
        (
            "create_infographic_verb",
            verbs.create_infographic_verb,
            studio.create_infographic,
            set(),
        ),
        ("create_slides_verb", verbs.create_slides_verb, studio.create_slides, set()),
        ("create_quiz_verb", verbs.create_quiz_verb, studio.create_quiz, set()),
        ("create_flashcards_verb", verbs.create_flashcards_verb, studio.create_flashcards, set()),
        ("create_data_table_verb", verbs.create_data_table_verb, studio.create_data_table, set()),
        ("create_mindmap_verb", verbs.create_mindmap_verb, studio.create_mindmap, set()),
        (
            "add_url_verb",
            verbs.add_url_verb,
            source.add_source,
            {"text", "drive", "youtube", "file", "title", "doc_type", "notebook_id"},
        ),
        (
            "add_text_verb",
            verbs.add_text_verb,
            source.add_source,
            {"url", "drive", "youtube", "file", "doc_type", "notebook_id"},
        ),
        (
            "add_drive_verb",
            verbs.add_drive_verb,
            source.add_source,
            {"url", "text", "youtube", "file", "notebook_id"},
        ),
        ("describe_notebook_verb", verbs.describe_notebook_verb, notebook.describe_notebook, set()),
        ("describe_source_verb", verbs.describe_source_verb, source.describe_source, set()),
        ("query_notebook_verb", verbs.query_notebook_verb, notebook.query_notebook, set()),
        ("content_source_verb", verbs.content_source_verb, source.get_source_content, set()),
        ("download_slides_verb", verbs.download_slides_verb, download.download_slide_deck, set()),
        ("delete_alias_verb", verbs.delete_alias_verb, alias.delete_alias, set()),
        ("research_start_verb", verbs.research_start_verb, research.start_research, set()),
    ]
    return pairs


def _get_target_params(func) -> set[str]:
    """Get parameter names from a function."""
    sig = inspect.signature(func)
    return {
        name
        for name, param in sig.parameters.items()
        if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
    }


def _get_call_args(func, target_func) -> set[str]:
    """Get keyword argument names that a verb wrapper passes to its target.

    Uses the AST to inspect the actual function call site, not regex.
    This avoids false positives from parameter annotations, local variable
    assignments, or typer.Option() declarations.
    """
    import ast
    import textwrap

    src = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(src)
    target_name = target_func.__name__

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == target_name
        ):
            return {kw.arg for kw in node.keywords if kw.arg is not None}
    return set()


_PAIRS = _collect_pairs()


@pytest.mark.parametrize(
    "verb_name,verb_func,target_func,skip_params",
    [(name, vf, tf, skip) for name, vf, tf, skip in _PAIRS],
    ids=[name for name, _, _, _ in _PAIRS],
)
def test_verb_passes_all_target_params(verb_name, verb_func, target_func, skip_params):
    """Every parameter on the target function must be passed by the verb wrapper.

    If a target function accepts a parameter (e.g. --style, --focus, --wait),
    the verb wrapper must either:
    1. Accept it as a CLI option and pass it through, OR
    2. Be listed in skip_params with a reason

    Failing this test means the verb wrapper silently drops a parameter,
    which causes the target to receive a raw OptionInfo object instead of
    the intended default value.
    """
    target_params = _get_target_params(target_func)
    verb_call_args = _get_call_args(verb_func, target_func)

    missing = target_params - verb_call_args - skip_params

    assert not missing, (
        f"{verb_name} does not pass these parameters to {target_func.__name__}: "
        f"{missing}. Either add them to the verb wrapper or add to skip_params with a reason."
    )
