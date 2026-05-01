"""LabelsMixin - Source label management operations.

Requires 5+ sources for auto-label to be available in the NotebookLM UI.
"""

from .base import BaseClient


class LabelsMixin(BaseClient):
    """Mixin for source label management operations."""

    @staticmethod
    def _parse_label_response(result: list | None) -> list[dict]:
        """Parse raw agX4Bc response into list of label dicts.

        Raw format: [null, [[name, [[src_id], ...], label_id, emoji], ...]]
        """
        if not result or not isinstance(result, list) or len(result) < 2:
            return []
        raw_labels = result[1]
        if not raw_labels or not isinstance(raw_labels, list):
            return []
        labels = []
        for lbl in raw_labels:
            if not isinstance(lbl, list) or len(lbl) < 3:
                continue
            sources = lbl[1] or []
            source_ids = [s[0] for s in sources if isinstance(s, list) and s]
            labels.append(
                {
                    "id": lbl[2] or "",
                    "name": lbl[0] or "",
                    "emoji": (lbl[3] if len(lbl) > 3 else "") or "",
                    "source_ids": source_ids,
                }
            )
        return labels

    def auto_label(self, notebook_id: str) -> list[dict]:
        """Auto-label all sources using AI-generated thematic categories.

        If labels already exist, returns the current label state without
        re-running AI categorization.
        """
        params = [[2], notebook_id, None, None, []]
        result = self._call_rpc(self.RPC_LABEL_MANAGE, params, f"/notebook/{notebook_id}")
        return self._parse_label_response(result)

    def reorganize_labels(self, notebook_id: str, unlabeled_only: bool = False) -> list[dict]:
        """Force AI re-categorization of sources into new labels.

        API mode [0] = unlabeled sources only; [1] = force-replace all labels.
        """
        mode = [0] if unlabeled_only else [1]
        params = [[2], notebook_id, None, None, mode]
        result = self._call_rpc(self.RPC_LABEL_MANAGE, params, f"/notebook/{notebook_id}")
        return self._parse_label_response(result)

    def list_labels(self, notebook_id: str) -> list[dict]:
        """List current labels. Triggers AI auto-labeling if none exist."""
        return self.auto_label(notebook_id)

    def create_label(self, notebook_id: str, name: str, emoji: str = "") -> list[dict]:
        """Create a new empty label. Returns updated full label list."""
        params = [[2], notebook_id, None, None, None, [[name, emoji]]]
        result = self._call_rpc(self.RPC_LABEL_MANAGE, params, f"/notebook/{notebook_id}")
        return self._parse_label_response(result)

    def rename_label(self, notebook_id: str, label_id: str, new_name: str) -> bool:
        """Rename an existing label."""
        params = [[2], notebook_id, label_id, [[[new_name]]]]
        result = self._call_rpc(self.RPC_LABEL_MUTATE, params, f"/notebook/{notebook_id}")
        return result == [] or result is not None

    def set_label_emoji(self, notebook_id: str, label_id: str, emoji: str) -> bool:
        """Set or clear the emoji marker on a label (pass "" to clear)."""
        params = [[2], notebook_id, label_id, [[[None, emoji]]]]
        result = self._call_rpc(self.RPC_LABEL_MUTATE, params, f"/notebook/{notebook_id}")
        return result == [] or result is not None

    def move_source_to_label(self, notebook_id: str, label_id: str, source_id: str) -> bool:
        """Assign a source to a label. Multi-label: does not remove from other labels."""
        params = [[2], notebook_id, label_id, [[None, [[source_id]]]]]
        result = self._call_rpc(self.RPC_LABEL_MUTATE, params, f"/notebook/{notebook_id}")
        return result == [] or result is not None

    def delete_labels(self, notebook_id: str, label_ids: list[str]) -> bool:
        """Delete one or more labels. Sources are NOT deleted."""
        params = [[2], notebook_id, label_ids]
        result = self._call_rpc(self.RPC_LABEL_DELETE, params, f"/notebook/{notebook_id}")
        return result == [] or result is not None
