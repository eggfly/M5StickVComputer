from framework import BaseApp
import os
import lcd
import machine
import ubinascii
# import uos


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


class SystemInfoApp(BaseApp):
    def __init__(self, system):
        super(SystemInfoApp, self).__init__(system)
        self.__initialized = False

    def __lazy_init(self):
        self.system_uname = os.uname()
        self.device_id = ubinascii.hexlify(machine.unique_id()).decode()
        self.__initialized = True

    def on_top_button_changed(self, state):
        pass

    def on_draw(self):
        if not self.__initialized:
            self.__lazy_init()
        lcd.clear()
        lcd.draw_string(3, 3, self.system_uname.machine, lcd.WHITE, lcd.BLUE)
        lcd.draw_string(3, 3 + 16, self.system_uname.version, lcd.WHITE, lcd.BLUE)
        lcd.draw_string(3, 3 + 16, self.system_uname.version, lcd.WHITE, lcd.BLUE)
        lcd.draw_string(3, 3 + 16 * 2, self.device_id, lcd.WHITE, lcd.BLUE)