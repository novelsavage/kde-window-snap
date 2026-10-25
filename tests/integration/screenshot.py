import os,threading,dbus,pathlib
from PyQt6.QtGui import QImage
r,w=os.pipe()
parts=[]
def read():
 while True:
  data=os.read(r,65536)
  if not data:break
  parts.append(data)
thread=threading.Thread(target=read,daemon=True);thread.start()
b=dbus.SessionBus();api=dbus.Interface(b.get_object('org.kde.KWin','/org/kde/KWin/ScreenShot2'),'org.kde.KWin.ScreenShot2')
try:
 meta=api.CaptureWorkspace(dbus.Dictionary({},signature='sv'),dbus.types.UnixFd(w), timeout=10)
finally:os.close(w)
thread.join(timeout=10)
print(dict(meta),sum(map(len,parts)))
data=b''.join(parts)
image=QImage(data,int(meta['width']),int(meta['height']),int(meta['stride']),QImage.Format(int(meta['format'])))
import sys
image.save(sys.argv[1])
