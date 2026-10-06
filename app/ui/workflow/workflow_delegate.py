"""Paint workflow rows: grip, number, vector icon, title, summary, selection."""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeView

from app.ui.styles.icons import icon_pixmap
from app.ui.styles.tokens import Colors, Control, Radius
from app.ui.workflow.workflow_model import WorkflowRoles


class WorkflowItemDelegate(QStyledItemDelegate):
    """Compact two-line step row for the automation IDE."""

    ROW_H = 52
    LEFT_PAD = 8

    def __init__(self, tree: QTreeView) -> None:
        super().__init__(tree)
        self._tree = tree

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), self.ROW_H)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = option.rect.adjusted(6, 2, -6, -2)
        depth = int(index.data(WorkflowRoles.Depth) or 0)
        step_index = index.data(WorkflowRoles.StepIndex)
        title = index.data(WorkflowRoles.Title) or ""
        summary = index.data(WorkflowRoles.Summary) or ""
        icon_key = index.data(WorkflowRoles.Icon) or "more"
        err = index.data(WorkflowRoles.Error)
        exec_state = index.data(WorkflowRoles.ExecState) or "normal"
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        # Surface
        if selected:
            bg = QColor(Colors.SURFACE_SELECTED)
        elif exec_state == "executing":
            bg = QColor(Colors.ACCENT)
            bg.setAlpha(28)
        elif hovered:
            bg = QColor(Colors.SURFACE_HOVER)
        else:
            bg = QColor(Colors.SURFACE)

        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(rect), Radius.MD, Radius.MD)

        # Left accent bar when selected
        if selected:
            painter.setBrush(QColor(Colors.ACCENT))
            painter.drawRoundedRect(QRectF(rect.left(), rect.top() + 8, 3, rect.height() - 16), 1.5, 1.5)

        # Nesting guide
        if depth > 0:
            gx = rect.left() + self.LEFT_PAD + (depth - 1) * 18 + 6
            painter.setPen(QPen(QColor(Colors.BORDER_STRONG), 1))
            painter.drawLine(gx, rect.top(), gx, rect.bottom())
            painter.drawLine(gx, rect.center().y(), gx + 10, rect.center().y())

        indent = self.LEFT_PAD + depth * 18
        x = rect.left() + indent + (6 if selected else 4)

        # Grip
        grip = icon_pixmap("grip", 12, Colors.TEXT_MUTED)
        painter.drawPixmap(x, rect.top() + 20, grip)

        # Number
        num = ""
        if step_index is not None:
            num = str(int(step_index) + 1).zfill(2)
        font_num = QFont(option.font)
        font_num.setPointSize(10)
        font_num.setWeight(QFont.Medium)
        painter.setFont(font_num)
        painter.setPen(QColor(Colors.TEXT_MUTED))
        painter.drawText(QRect(x + 16, rect.top() + 8, 26, 18), Qt.AlignLeft | Qt.AlignVCenter, num)

        # Icon
        icon_color = Colors.ACCENT if selected else Colors.TEXT_SECONDARY
        if exec_state == "executing":
            icon_color = Colors.ACCENT
        pm = icon_pixmap(str(icon_key), Control.ICON, icon_color)
        painter.drawPixmap(x + 42, rect.top() + 10, pm)

        # Title + summary
        title_x = x + 64
        content_w = rect.right() - title_x - 10

        font_title = QFont(option.font)
        font_title.setPointSize(13)
        font_title.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font_title)
        painter.setPen(QColor(Colors.TEXT))
        painter.drawText(QRect(title_x, rect.top() + 8, content_w, 20), Qt.AlignLeft | Qt.AlignVCenter, str(title))

        font_sub = QFont(option.font)
        font_sub.setPointSize(11)
        painter.setFont(font_sub)
        if err:
            painter.setPen(QColor(Colors.WARNING))
            warn = icon_pixmap("warning", 12, Colors.WARNING)
            painter.drawPixmap(title_x, rect.top() + 30, warn)
            painter.drawText(
                QRect(title_x + 16, rect.top() + 28, content_w - 16, 18),
                Qt.AlignLeft | Qt.AlignVCenter,
                str(err),
            )
        else:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRect(title_x, rect.top() + 28, content_w, 18),
                Qt.AlignLeft | Qt.AlignVCenter,
                str(summary),
            )

        painter.restore()
