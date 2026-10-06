"""Qt tree model for hierarchical workflow rows."""

from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from app.application.step_format import validate_step
from app.core.models import Action, Preset
from app.ui.workflow.step_icons import icon_key_for_type
from app.ui.workflow.workflow_tree import WorkflowNode, build_workflow_tree


class WorkflowRoles:
    """Custom model roles for delegates and DnD."""

    StepIndex = Qt.UserRole + 1
    Title = Qt.UserRole + 2
    Summary = Qt.UserRole + 3
    Icon = Qt.UserRole + 4
    Error = Qt.UserRole + 5
    ExecState = Qt.UserRole + 6
    BranchKind = Qt.UserRole + 7
    Depth = Qt.UserRole + 8


class WorkflowTreeModel(QAbstractItemModel):
    """Tree model backed by WorkflowNode hierarchy."""

    def __init__(self) -> None:
        super().__init__()
        self._roots: list[WorkflowNode] = []
        self._actions: list[Action] = []
        self._errors: dict[int, str] = {}
        self._exec_index: int | None = None

    def set_preset(self, preset: Preset | None) -> None:
        """Rebuild tree from preset actions."""
        self.beginResetModel()
        if preset is None:
            self._roots = []
            self._actions = []
            self._errors = {}
        else:
            self._actions = preset.actions
            try:
                self._roots = build_workflow_tree(preset.actions)
            except Exception:
                self._roots = []
            self._errors = {
                i: msg for i, act in enumerate(preset.actions) if (msg := validate_step(act))
            }
        self.endResetModel()

    def flat_actions(self) -> list[Action]:
        return list(self._actions)

    def node_from_index(self, index: QModelIndex) -> WorkflowNode | None:
        if not index.isValid():
            return None
        return index.internalPointer()

    def index_for_step(self, step_index: int | None) -> QModelIndex:
        """Find model index for a flat step index."""
        if step_index is None:
            return QModelIndex()

        found: list[QModelIndex] = []

        def walk(parent: QModelIndex, nodes: list[WorkflowNode]) -> None:
            for row, node in enumerate(nodes):
                idx = self.index(row, 0, parent)
                if node.step_index == step_index:
                    found.append(idx)
                    return
                if node.children:
                    walk(idx, node.children)
                if found:
                    return

        walk(QModelIndex(), self._roots)
        return found[0] if found else QModelIndex()

    def step_index_at(self, index: QModelIndex) -> int | None:
        node = self.node_from_index(index)
        return node.step_index if node else None

    def set_execution_index(self, step_index: int | None) -> None:
        """Highlight row during playback (hook for future player index)."""
        if self._exec_index == step_index:
            return
        old = self._exec_index
        self._exec_index = step_index
        for idx in (old, step_index):
            if idx is not None:
                model_idx = self.index_for_step(idx)
                if model_idx.isValid():
                    self.dataChanged.emit(model_idx, model_idx, [WorkflowRoles.ExecState])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            return len(self._roots)
        node: WorkflowNode = parent.internalPointer()
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 1

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  # noqa: N802
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            node = self._roots[row]
        else:
            parent_node: WorkflowNode = parent.internalPointer()
            node = parent_node.children[row]
        return self.createIndex(row, column, node)

    def parent(self, index: QModelIndex) -> QModelIndex:  # noqa: N802
        if not index.isValid():
            return QModelIndex()
        node: WorkflowNode = index.internalPointer()
        parent_node = node.parent
        if parent_node is None:
            return QModelIndex()
        grand = parent_node.parent
        if grand is None:
            row = self._roots.index(parent_node)
        else:
            row = grand.children.index(parent_node)
        return self.createIndex(row, 0, parent_node)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # noqa: N802
        node = self.node_from_index(index)
        if node is None:
            return None

        if role == Qt.DisplayRole:
            num = ""
            if node.step_index is not None:
                num = str(node.step_index + 1).zfill(2)
            return f"{num} {node.label}".strip()

        if role == WorkflowRoles.StepIndex:
            return node.step_index
        if role == WorkflowRoles.Title:
            return node.label
        if role == WorkflowRoles.Summary:
            return node.summary
        if role == WorkflowRoles.BranchKind:
            return node.branch_kind
        if role == WorkflowRoles.Depth:
            return node.depth
        if role == WorkflowRoles.Icon:
            if node.action is not None:
                return icon_key_for_type(node.action.type)
            if node.branch_kind == "else":
                return "else"
            if node.branch_kind == "endif":
                return "endif"
            return "more"
        if role == WorkflowRoles.Error:
            if node.step_index is not None:
                return self._errors.get(node.step_index)
            return None
        if role == WorkflowRoles.ExecState:
            if node.step_index is None:
                return "normal"
            if self._exec_index == node.step_index:
                return "executing"
            return "normal"
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # noqa: N802
        if not index.isValid():
            return Qt.NoItemFlags
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        node = self.node_from_index(index)
        if node and node.step_index is not None and node.action is not None:
            from app.core.models import ActionType

            if node.action.type not in (ActionType.ELSE, ActionType.ENDIF):
                base |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        return base

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.MoveAction

    def mimeTypes(self) -> list[str]:  # noqa: N802
        return ["application/x-cat-workflow-step"]

    def mimeData(self, indexes: list[QModelIndex]):  # noqa: N802
        from PySide6.QtCore import QMimeData

        mime = QMimeData()
        for idx in indexes:
            if idx.isValid() and idx.column() == 0:
                step = self.step_index_at(idx)
                if step is not None:
                    mime.setData("application/x-cat-workflow-step", str(step).encode())
                    break
        return mime

    def dropMimeData(  # noqa: N802
        self,
        data,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        return False  # handled in WorkflowTreeView

    def flat_drop_target(self, index: QModelIndex, before: bool) -> int | None:
        """Map a tree index to flat insert/move target."""
        node = self.node_from_index(index)
        if node is None:
            return len(self._actions)
        if node.step_index is not None:
            return node.step_index if before else node.step_index + 1
        return len(self._actions)
