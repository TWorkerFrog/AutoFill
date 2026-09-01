import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import DiplomaGenerator

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DiplomaGenerator()
    window.show()
    sys.exit(app.exec())