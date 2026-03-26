import sys

from PyQt6.QtWidgets import QApplication

from notch_window import NotchWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = NotchWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
