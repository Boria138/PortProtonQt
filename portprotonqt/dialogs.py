import portprotonqt.themes.standart.styles as default_styles
from PySide6.QtWidgets import QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QTextEdit, QDialogButtonBox, QFileDialog


class AddGameDialog(QDialog):
    def __init__(self, parent=None, theme=None):
        super().__init__(parent)
        self.theme = theme if theme else default_styles

        self.setWindowTitle("Добавить игру")
        self.setModal(True)

        layout = QFormLayout(self)

        self.nameEdit = QLineEdit(self)
        self.descEdit = QTextEdit(self)
        self.coverEdit = QLineEdit(self)

        browseButton = QPushButton("Обзор...", self)
        browseButton.setStyleSheet(self.theme.DIALOG_BROWSE_BUTTON_STYLE)
        browseButton.clicked.connect(self.browseCover)

        coverLayout = QHBoxLayout()
        coverLayout.addWidget(self.coverEdit)
        coverLayout.addWidget(browseButton)

        layout.addRow("Название:", self.nameEdit)
        layout.addRow("Описание:", self.descEdit)
        layout.addRow("Путь к обложке:", coverLayout)
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addRow(buttonBox)

    def browseCover(self):
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Выберите обложку", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if fileName:
            self.coverEdit.setText(fileName)
