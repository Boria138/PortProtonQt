import os
import shutil

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton,
    QHBoxLayout, QDialogButtonBox, QFileDialog, QLabel
)
from PySide6.QtDBus import QDBusInterface, QDBusConnection, QDBusMessage

from portprotonqt.config_utils import get_portproton_location
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
import portprotonqt.themes.standart.styles as default_styles

logger = get_logger(__name__)

def configure_xdg_portal() -> bool:
    # Проверяем, есть ли вообще портал
    connection = QDBusConnection.sessionBus()

    interface = QDBusInterface(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.FileChooser",
        connection
    )

    if not interface.isValid():
        logger.warning("XDG Desktop Portal is not available. Skipping portal-related configuration.")
        return False

    # Проверка через introspection на наличие метода OpenFile
    introspect_iface = QDBusInterface(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.DBus.Introspectable",
        connection
    )

    if not introspect_iface.isValid():
        logger.warning("Cannot introspect portal interface.")
        return False

    reply = introspect_iface.call("Introspect")
    if reply.type() != QDBusMessage.MessageType.ReplyMessage or not reply.arguments():
        logger.warning("Failed to introspect portal interface.")
        return False

    introspection_xml = reply.arguments()[0]
    if "<method name=\"OpenFile\"" not in introspection_xml:
        logger.warning("OpenFile method not found in FileChooser interface.")
        return False

    # Всё ок, теперь можно установить переменную окружения
    os.environ["QT_QPA_PLATFORMTHEME"] = "xdgdesktopportal"
    logger.info("XDG Desktop Portal and OpenFile method are available. Set QT_QPA_PLATFORMTHEME to xdgdesktopportal.")
    return True

configure_xdg_portal()

class AddGameDialog(QDialog):
    def __init__(self, parent=None, theme=None):
        super().__init__(parent)
        self.theme = theme if theme else default_styles

        self.setWindowTitle(_("Add Game"))
        self.setModal(True)

        layout = QFormLayout(self)

        # Game name
        self.nameEdit = QLineEdit(self)
        layout.addRow(_("Game Name:"), self.nameEdit)

        # Exe path
        self.exeEdit = QLineEdit(self)
        exeBrowseButton = QPushButton(_("Browse..."), self)
        exeBrowseButton.clicked.connect(self.browseExe)

        exeLayout = QHBoxLayout()
        exeLayout.addWidget(self.exeEdit)
        exeLayout.addWidget(exeBrowseButton)
        layout.addRow(_("Path to Executable:"), exeLayout)

        # Cover path
        self.coverEdit = QLineEdit(self)
        coverBrowseButton = QPushButton(_("Browse..."), self)
        coverBrowseButton.clicked.connect(self.browseCover)

        coverLayout = QHBoxLayout()
        coverLayout.addWidget(self.coverEdit)
        coverLayout.addWidget(coverBrowseButton)
        layout.addRow(_("Custom Cover:"), coverLayout)

        # Preview
        self.coverPreview = QLabel(self)
        layout.addRow(_("Cover Preview:"), self.coverPreview)

        # Dialog buttons
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addRow(buttonBox)

        self.coverEdit.textChanged.connect(self.updatePreview)
        self.exeEdit.textChanged.connect(self.updatePreview)

    def browseExe(self):
        fileNameAndFilter = QFileDialog.getOpenFileName(
            self,
            _("Select Executable"),
            "",
            "Windows Executables (*.exe)"
        )
        fileName = fileNameAndFilter[0]
        if fileName:
            self.exeEdit.setText(fileName)
            base = os.path.basename(fileName)
            name = os.path.splitext(base)[0]
            self.nameEdit.setText(name)

    def browseCover(self):
        fileNameAndFilter = QFileDialog.getOpenFileName(
            self,
            _("Select Cover Image"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        fileName = fileNameAndFilter[0]
        if fileName:
            self.coverEdit.setText(fileName)

    def updatePreview(self):
        path = self.coverEdit.text().strip()

        if os.path.isfile(path):
            self.coverPreview.setPixmap(QPixmap(path))
        elif os.path.isfile(self.exeEdit.text().strip()):
            temp_icon = "/tmp/portproton_temp_icon.png"
            os.system(f'exe-thumbnailer "{self.exeEdit.text().strip()}" "{temp_icon}"')
            if os.path.exists(temp_icon):
                self.coverPreview.setPixmap(QPixmap(temp_icon))
            else:
                self.coverPreview.clear()
        else:
            self.coverPreview.clear()

    def getDesktopEntryData(self):
        """Returns the .desktop content and save path"""
        exe_path = self.exeEdit.text().strip()
        name = self.nameEdit.text().strip()

        if not exe_path or not name:
            return None, None

        portproton_path = get_portproton_location()
        if portproton_path is None:
            return None, None

        is_flatpak = ".var" in portproton_path
        base_path = os.path.join(portproton_path, "data")

        if is_flatpak:
            exec_str = f'flatpak run ru.linux_gaming.PortProton "{exe_path}"'
        else:
            start_sh = os.path.join(base_path, "scripts", "start.sh")
            exec_str = f'env "{start_sh}" "{exe_path}"'

        icon_path = os.path.join(base_path, "img", f"{name}.png")
        desktop_path = os.path.join(portproton_path, f"{name}.desktop")
        working_dir = os.path.join(base_path, "scripts")

        user_cover_path = self.coverEdit.text().strip()
        if os.path.isfile(user_cover_path):
            shutil.copy(user_cover_path, icon_path)
        else:
            os.makedirs(os.path.dirname(icon_path), exist_ok=True)
            os.system(f'exe-thumbnailer "{exe_path}" "{icon_path}"')

        comment = _('Launch game "{name}" with PortProton').format(name=name)

        desktop_entry = f"""[Desktop Entry]
Name={name}
Comment={comment}
Exec={exec_str}
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
Path={working_dir}
Icon={icon_path}
"""

        return desktop_entry, desktop_path
