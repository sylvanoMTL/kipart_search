"""Detail panel widget — shows full specs, pricing, and assign button for a selected part."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.models import PartResult


_GUIDANCE_HTML = (
    '<p style="text-align:center; color:#888; margin-top:40%;">'
    "Select a search result to view details</p>"
)


def render_part_html(part: PartResult) -> str:
    """Render an HTML detail view for a PartResult."""
    lines: list[str] = []

    lines.append(f"<h2>{escape(part.mpn)}</h2>")

    if part.source_part_id:
        lines.append(f"<b>LCSC:</b> {escape(part.source_part_id)}<br>")
    if part.manufacturer:
        lines.append(f"<b>Manufacturer:</b> {escape(part.manufacturer)}<br>")
    if part.category:
        lines.append(f"<b>Category:</b> {escape(part.category)}<br>")
    if part.package:
        lines.append(f"<b>Package:</b> {escape(part.package)}<br>")
    if part.lifecycle:
        lines.append(f"<b>Lifecycle:</b> {escape(part.lifecycle)}<br>")
    if part.description:
        lines.append(f"<b>Description:</b> {escape(part.description)}<br>")
    if part.datasheet_url:
        url = escape(part.datasheet_url)
        lines.append(f'<b>Datasheet:</b> <a href="{url}">{url}</a><br>')
    if part.source_url:
        url = escape(part.source_url)
        lines.append(f'<b>Source:</b> <a href="{url}">{url}</a><br>')
    if part.stock is not None:
        lines.append(f"<b>Stock:</b> {part.stock:,}<br>")

    # Parametric specs table
    if part.specs:
        lines.append("<h3>Parameters</h3>")
        lines.append('<table border="1" cellpadding="4" cellspacing="0">')
        lines.append("<tr><th>Parameter</th><th>Value</th></tr>")
        for spec in part.specs:
            lines.append(
                f"<tr><td>{escape(spec.name)}</td>"
                f"<td>{escape(spec.raw_value)}</td></tr>"
            )
        lines.append("</table>")

    # Pricing table
    if part.price_breaks:
        lines.append("<h3>Pricing</h3>")
        lines.append('<table border="1" cellpadding="4" cellspacing="0">')
        lines.append("<tr><th>Qty</th><th>Unit Price</th></tr>")
        for pb in part.price_breaks:
            lines.append(
                f"<tr><td>{pb.quantity}</td>"
                f"<td>{pb.unit_price:.4f} {escape(pb.currency)}</td></tr>"
            )
        lines.append("</table>")

    return "\n".join(lines)


class DetailPanel(QWidget):
    """Panel showing full detail for a selected search result."""

    assign_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._browser = QTextBrowser()
        self._browser.setReadOnly(True)
        self._browser.setOpenExternalLinks(True)
        layout.addWidget(self._browser)

        self._assign_btn = QPushButton()
        self._assign_btn.setVisible(False)
        self._assign_btn.clicked.connect(self.assign_requested.emit)
        layout.addWidget(self._assign_btn)

        self._current_part: PartResult | None = None

        # Show empty-state guidance
        self._browser.setHtml(_GUIDANCE_HTML)

    def set_part(self, part: PartResult | None) -> None:
        """Display detail for *part*, or revert to guidance text if None."""
        self._current_part = part
        if part is None:
            self._browser.setHtml(_GUIDANCE_HTML)
        else:
            self._browser.setHtml(render_part_html(part))

    def set_assign_target(self, reference: str | None) -> None:
        """Show or hide the assign button based on whether a target is set."""
        if reference:
            self._assign_btn.setText(f"Assign to {reference}")
            self._assign_btn.setVisible(True)
        else:
            self._assign_btn.setVisible(False)

    @property
    def current_part(self) -> PartResult | None:
        """The part currently displayed, if any."""
        return self._current_part
