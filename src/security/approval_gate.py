"""
Security feature: approval_gate

PR Janitor's core safety principle: the system can READ and ANALYZE
autonomously, but it can never WRITE (post a comment, apply a label,
merge, close) without an explicit human decision per item.

This module implements that gate as a simple, auditable queue:
1. Drafter Agent produces a DraftAction
2. The queue holds it in PENDING state
3. A maintainer calls approve() / reject() / edit_and_approve()
4. Only approved actions are ever passed to GitHubClient.post_comment_if_approved

A full audit log (who/when/what) is kept in memory and can be persisted
to disk — important for any team adopting this in a real org, since
"an autonomous agent commented on our PR" is exactly the kind of action
that needs a paper trail.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class ActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED_AND_APPROVED = "edited_and_approved"


@dataclass
class DraftAction:
    pr_number: int
    category: str
    draft_comment: str
    reasoning: str
    status: ActionStatus = ActionStatus.PENDING
    final_comment: str | None = None
    decided_at: str | None = None


class ApprovalQueue:
    def __init__(self, audit_log_path: str | None = None):
        self._items: dict[int, DraftAction] = {}
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None

    def add(self, action: DraftAction) -> None:
        self._items[action.pr_number] = action

    def pending(self) -> list[DraftAction]:
        return [a for a in self._items.values() if a.status == ActionStatus.PENDING]

    def approve(self, pr_number: int) -> DraftAction:
        action = self._items[pr_number]
        action.status = ActionStatus.APPROVED
        action.final_comment = action.draft_comment
        action.decided_at = datetime.now(timezone.utc).isoformat()
        self._audit(action)
        return action

    def reject(self, pr_number: int) -> DraftAction:
        action = self._items[pr_number]
        action.status = ActionStatus.REJECTED
        action.decided_at = datetime.now(timezone.utc).isoformat()
        self._audit(action)
        return action

    def edit_and_approve(self, pr_number: int, edited_comment: str) -> DraftAction:
        action = self._items[pr_number]
        action.status = ActionStatus.EDITED_AND_APPROVED
        action.final_comment = edited_comment
        action.decided_at = datetime.now(timezone.utc).isoformat()
        self._audit(action)
        return action

    def _audit(self, action: DraftAction) -> None:
        if not self.audit_log_path:
            return
        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps(asdict(action), default=str) + "\n")
