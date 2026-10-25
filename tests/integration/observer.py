import dbus,dbus.service,json,pathlib,sys
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
root=pathlib.Path(sys.argv[1])
class Observer(dbus.service.Object):
 @dbus.service.method('local.SnapTest',in_signature='s',out_signature='')
 def report(self,value):
  (root/'snapshot.json').write_text(value)
bus=dbus.SessionBus();name=dbus.service.BusName('local.SnapTest',bus);obj=Observer(bus,'/test')
GLib.MainLoop().run()
