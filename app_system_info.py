from framework import BaseApp
import os
import lcd
import machine
import ubinascii


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
        root_files = os.listdir('/')
        self.fs_info_list = []
        for f in root_files:
            fs_path = '/' + f
            fs_stat = os.statvfs(fs_path)
            bs1 = fs_stat[0]
            bs2 = fs_stat[1]
            total_blocks = fs_stat[2]
            free_blocks = fs_stat[3]
            info = "%s total=%s free=%s" % (
                fs_path,
                sizeof_fmt(bs1 * total_blocks),
                sizeof_fmt(bs2 * free_blocks)
            )
            self.fs_info_list.append(info)
            print(info)
        self.__initialized = True

    def on_top_button_changed(self, state):
        pass

    def on_draw(self):
        if not self.__initialized:
            self.__lazy_init()
        lcd.clear()
        y = 3
        lcd.draw_string(3, 3, self.system_uname.machine, lcd.WHITE, lcd.BLUE)
        y += 16
        lcd.draw_string(3, y, self.system_uname.version,
                        lcd.WHITE, lcd.BLUE)
        y += 16
        lcd.draw_string(3, y, self.device_id, lcd.WHITE, lcd.BLUE)
        for info in self.fs_info_list:
            y += 16
            lcd.draw_string(3, y, info, lcd.WHITE, lcd.BLUE)
