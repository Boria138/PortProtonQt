import os
import shutil
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QWidget, QCheckBox,
                               QPushButton, QMessageBox,
                               QLabel, QTextEdit, QHBoxLayout,
                               QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt
from portprotonqt.localization import _


class WineDeleteManager(QDialog):
    def __init__(self, parent=None, portproton_location=None, selected_wine=None):
        super().__init__(parent)
        self.selected_wines = set()  # Use set to store selected wine names
        self.portproton_location = portproton_location
        self.selected_wine = selected_wine  # The wine that should be pre-selected
        self.initUI()
        self.load_wine_data()

    def initUI(self):
        self.setWindowTitle(_('Delete Wine'))
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Wine list widget - основной растягивающийся элемент
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)  # Disable default selection to use checkboxes
        layout.addWidget(self.list_widget, 1)

        # Инфо-блок для показа выбранного (компактный для информации по выбранным закачкам)
        selection_widget = QWidget()
        selection_layout = QVBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 2, 0, 2)
        selection_layout.setSpacing(2)

        selection_label = QLabel(_("Selected WINE:"))
        selection_layout.addWidget(selection_label)

        self.selection_text = QTextEdit()
        self.selection_text.setMaximumHeight(80)
        self.selection_text.setReadOnly(True)
        self.selection_text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.selection_text.setPlainText(_("No WINE selected"))
        selection_layout.addWidget(self.selection_text)

        layout.addWidget(selection_widget)

        # Кнопки управления
        button_layout = QHBoxLayout()
        self.delete_btn = QPushButton(_('Delete Selected'))
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setMinimumHeight(40)
        self.clear_btn = QPushButton(_('Clear All'))
        self.clear_btn.clicked.connect(self.clear_selection)
        self.clear_btn.setMinimumHeight(40)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

    def load_wine_data(self):
        """Load wine data from dist directory"""
        if not self.portproton_location:
            return

        dist_path = os.path.join(self.portproton_location, "data", "dist")
        if not os.path.exists(dist_path):
            return

        # Get all wine directories
        wine_dirs = [d for d in os.listdir(dist_path) if os.path.isdir(os.path.join(dist_path, d))]

        # Add each wine to the list
        for wine_name in wine_dirs:
            self.add_wine_to_list(wine_name)

    def add_wine_to_list(self, wine_name):
        """Add a wine to the list with checkbox"""
        # Create a widget with checkbox and wine name
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(5, 2, 5, 2)
        item_layout.setSpacing(5)

        checkbox = QCheckBox(wine_name)


        checkbox.stateChanged.connect(lambda state, name=wine_name: self.on_wine_toggled(state, name))
        item_layout.addWidget(checkbox)
        item_layout.addStretch()  # Add stretch to align checkbox to the left

        # Create list item and set the widget
        list_item = QListWidgetItem(self.list_widget)
        list_item.setSizeHint(item_widget.sizeHint())
        self.list_widget.addItem(list_item)
        self.list_widget.setItemWidget(list_item, item_widget)


    def on_wine_toggled(self, state, wine_name):
        """Handle wine selection/deselection"""
        if state == Qt.CheckState.Checked.value:
            self.selected_wines.add(wine_name)
        else:
            self.selected_wines.discard(wine_name)

        self.update_selection_display()

    def update_selection_display(self):
        """Update the selection display"""
        # Get currently selected wines from the list
        currently_selected = set()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_widget = self.list_widget.itemWidget(item)
            if item_widget:
                checkbox = item_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    currently_selected.add(checkbox.text())

        # Update the internal set to match the current state
        self.selected_wines = currently_selected

        if self.selected_wines:
            selection_text = _('Selected {} WINE:\n').format(len(self.selected_wines))

            for i, wine_name in enumerate(sorted(self.selected_wines), 1):
                selection_text += f"{i}. {wine_name}\n"

            self.selection_text.setPlainText(selection_text)
            self.delete_btn.setEnabled(True)
        else:
            self.selection_text.setPlainText(_("No WINE selected"))
            self.delete_btn.setEnabled(False)

    def clear_selection(self):
        """Clear all selections"""
        self.selected_wines.clear()

        # Uncheck all checkboxes in the list
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_widget = self.list_widget.itemWidget(item)
            if item_widget:
                checkbox = item_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)

        self.update_selection_display()

    def delete_selected(self):
        """Delete all selected wines"""
        # Get currently selected wines from the list
        currently_selected = set()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_widget = self.list_widget.itemWidget(item)
            if item_widget:
                checkbox = item_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    currently_selected.add(checkbox.text())

        if not currently_selected:
            QMessageBox.warning(self, _("No Selection"), _("Please select at least one WINE to delete."))
            return

        # Confirm deletion
        wine_list = "\n".join(sorted(currently_selected))
        reply = QMessageBox.question(
            self,
            _("Confirm Deletion"),
            _("Are you sure you want to delete the following WINE versions?\n\n{}").format(wine_list),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if not self.portproton_location:
            return

        dist_path = os.path.join(self.portproton_location, "data", "dist")
        errors = []

        for wine_name in currently_selected:
            wine_path = os.path.join(dist_path, wine_name)
            try:
                if os.path.exists(wine_path):
                    shutil.rmtree(wine_path)
            except Exception as e:
                error_msg = _("Failed to delete WINE '{}': {}").format(wine_name, str(e))
                errors.append(error_msg)
                QMessageBox.warning(self, _("Error"), error_msg)

        if errors:
            QMessageBox.warning(self, _("Some Deletions Failed"),
                              _("Some WINE versions could not be deleted:\n\n{}").format("\n".join(errors)))
        else:
            QMessageBox.information(self, _("Success"), _("Selected WINE versions deleted successfully."))

        # Close the dialog after deletion
        self.accept()


def show_wine_delete_manager(parent=None, portproton_location=None, selected_wine=None):
    """
    Shows the WINE deletion dialog.

    Args:
        parent: Parent widget for the dialog
        portproton_location: Location of PortProton installation
        selected_wine: Wine that should be pre-selected

    Returns:
        WineDeleteManager dialog instance
    """
    dialog = WineDeleteManager(parent, portproton_location, selected_wine)
    dialog.exec()  # Use exec() for modal dialog
    return dialog
