"""Build a visual tree from flat if/else/endif action lists."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.step_format import format_step_summary, format_step_title
from app.core.control_flow import find_if_block
from app.core.models import Action, ActionType

IF_TYPES = {ActionType.IF_TEXT, ActionType.IF_IMAGE}


@dataclass
class WorkflowNode:
    """One row in the workflow tree (structural or a real step)."""

    step_index: int | None  # index in flat Preset.actions; None for branch-only rows
    action: Action | None
    label: str
    summary: str
    branch_kind: str | None = None  # "then", "else", "endif", "if"
    children: list[WorkflowNode] = field(default_factory=list)
    depth: int = 0
    parent: WorkflowNode | None = field(default=None, repr=False)


def action_title(action: Action) -> str:
    """Short English title (re-export for inspector)."""
    return format_step_title(action)


def build_workflow_tree(actions: list[Action]) -> list[WorkflowNode]:
    """Parse flat actions into top-level workflow nodes with nested branches."""
    return _build_range(actions, 0, len(actions), depth=0, parent=None)


def _build_range(
    actions: list[Action],
    start: int,
    end: int,
    depth: int,
    parent: WorkflowNode | None,
) -> list[WorkflowNode]:
    nodes: list[WorkflowNode] = []
    i = start
    while i < end:
        action = actions[i]
        if action.type in IF_TYPES:
            block = find_if_block(actions, i)
            then_end = block.else_index if block.else_index is not None else block.endif_index
            then_nodes = _build_range(actions, i + 1, then_end, depth + 1, parent=None)
            child_blocks: list[WorkflowNode] = list(then_nodes)
            if block.else_index is not None:
                else_nodes = _build_range(
                    actions, block.else_index + 1, block.endif_index, depth + 1, parent=None
                )
                child_blocks.append(
                    WorkflowNode(
                        step_index=block.else_index,
                        action=actions[block.else_index],
                        label="Else",
                        summary=format_step_summary(actions[block.else_index]),
                        branch_kind="else",
                        depth=depth + 1,
                        children=else_nodes,
                    )
                )
            child_blocks.append(
                WorkflowNode(
                    step_index=block.endif_index,
                    action=actions[block.endif_index],
                    label="End If",
                    summary=format_step_summary(actions[block.endif_index]),
                    branch_kind="endif",
                    depth=depth + 1,
                    children=[],
                )
            )
            if_node = WorkflowNode(
                step_index=i,
                action=action,
                label=format_step_title(action),
                summary=format_step_summary(action),
                branch_kind="if",
                depth=depth,
                children=child_blocks,
            )
            for ch in child_blocks:
                ch.parent = if_node
            nodes.append(if_node)
            i = block.endif_index + 1
            continue
        nodes.append(
            WorkflowNode(
                step_index=i,
                action=action,
                label=format_step_title(action),
                summary=format_step_summary(action),
                depth=depth,
            )
        )
        i += 1
    for n in nodes:
        n.parent = parent
    return nodes
