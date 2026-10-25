from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QFont
app=QApplication([])
windows=[]
for name,color in [('LEFT','#19364a'),('RIGHT','#423459')]:
 w=QWidget();w.setWindowTitle('Snap Test '+name);w.resize(500,500);w.setMinimumSize(160,160)
 w.setStyleSheet('background:'+color+';color:white;')
 layout=QVBoxLayout(w)
 title=QLabel(name);title.setFont(QFont('sans-serif',36));layout.addWidget(title)
 layout.addWidget(QLabel('Drag the shared edge to resize both windows.\nIsolated KWin / no host desktop input'))
 w.show();windows.append(w)
app.exec()
