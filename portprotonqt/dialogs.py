import os
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout,
    QDialogButtonBox, QFileDialog, QMessageBox
)
from portprotonqt.config_utils import get_portproton_location
from portprotonqt.localization import _
import portprotonqt.themes.standart.styles as default_styles

class AddGameDialog(QDialog):
    def __init__(self, parent=None, theme=None):
        super().__init__(parent)
        self.theme = theme if theme else default_styles

        self.setWindowTitle(_("Add Game"))
        self.setModal(True)

        layout = QFormLayout(self)

        self.nameEdit = QLineEdit(self)
        self.exeEdit = QLineEdit(self)

        browseButton = QPushButton(_("Browse..."), self)
        browseButton.clicked.connect(self.browseExe)

        exeLayout = QHBoxLayout()
        exeLayout.addWidget(self.exeEdit)
        exeLayout.addWidget(browseButton)

        layout.addRow(_("Game Name:"), self.nameEdit)
        layout.addRow(_("Executable File:"), exeLayout)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox.accepted.connect(self.onAccept)
        buttonBox.rejected.connect(self.reject)

        layout.addRow(buttonBox)

    def browseExe(self):
        fileName = QFileDialog.getOpenFileName(
            self,
            _("Select Executable"),
            "",
            "Windows Executables (*.exe)"
        )[0]
        if fileName:
            self.exeEdit.setText(fileName)
            if not self.nameEdit.text():
                name = os.path.splitext(os.path.basename(fileName))[0]
                self.nameEdit.setText(name)

    def onAccept(self):
        desktop_entry, desktop_path = self.getDesktopEntryData()
        if desktop_entry and desktop_path:
            try:
                with open(desktop_path, "w") as f:
                    f.write(desktop_entry)
                QMessageBox.information(self, _("Success"), _("Game added successfully."))
                self.accept()
                os.system(f"chmod +x \"{desktop_path}\"")
            except Exception as e:
                QMessageBox.critical(self, _("Error"), str(e))
        else:
            # already handled by inner message boxes
            pass

    def getDesktopEntryData(self):
        exe_path = self.exeEdit.text().strip()
        name = self.nameEdit.text().strip()

        if not exe_path or not name:
            QMessageBox.warning(self, _("Error"), _("Please provide a game name and the .exe path."))
            return None, None

        portproton_path = get_portproton_location()
        is_flatpak = ".var" in (portproton_path if portproton_path else "")
        if portproton_path:
            base_path = os.path.join(portproton_path, "data")
        else:
            raise ValueError("PortProton path is not available.")

        if is_flatpak:
            exec_str = f'flatpak run ru.linux_gaming.PortProton "{exe_path}"'
        else:
            start_sh = os.path.join(base_path, "scripts/start.sh")
            exec_str = f'env "{start_sh}" "{exe_path}"'

        icon_path = os.path.join(base_path, "img", f"{name}.png")
        desktop_path = os.path.join(portproton_path, f"{name}.desktop")
        working_dir = os.path.join(base_path, "scripts")
        os.makedirs(os.path.dirname(icon_path), exist_ok=True)
        os.system(f'exe-thumbnailer "{exe_path}" "{icon_path}"')

        comment = _('Launch game "{name}" with PortProton').format(name=name)

        desktop_entry = f"""[Desktop Entry]
Name={name}
Comment={comment}
Exec={exec_str}
Type=Application
Categories=Game
StartupNotify=true
Path={working_dir}
Icon={icon_path}
"""

        return desktop_entry, desktop_path
