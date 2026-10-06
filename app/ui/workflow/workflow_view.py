"""QTreeView with internal drag-drop mapped to flat action indices."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QTreeView

from app.ui.workflow.workflow_model import WorkflowTreeModel


class WorkflowTreeView(QTreeView):
    """Workflow tree with drop validation delegated to MacroController."""

    move_requested = Signal(int, int)  # source flat index, target flat index

    def __init__(self, model: WorkflowTreeModel) -> None:
        super().__init__()
        self.setModel(model)
        self._model = model
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAnimated(True)
        self.setIndentation(0)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setStyleSheet("QTreeView { border: none; background: transparent; }")
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasFormat("application/x-cat-workflow-step"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat("application/x-cat-workflow-step"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if not event.mimeData().hasFormat("application/x-cat-workflow-step"):
            super().dropEvent(event)
            return
        raw = event.mimeData().data("application/x-cat-workflow-step")
        try:
            source = int(bytes(raw).decode())
        except (ValueError, TypeError):
            event.ignore()
            return
        idx = self.indexAt(event.position().toPoint())
        before = True
        if idx.isValid():
            rect = self.visualRect(idx)
            before = event.position().y() < rect.center().y()
        target = self._model.flat_drop_target(idx, before)
        if target is None:
            event.ignore()
            return
        self.move_requested.emit(source, target)
        event.acceptProposedAction()

    def expand_all(self) -> None:
        """Expand every branch for editing."""
        self.expandAll()
