from framework import BaseApp
import os
import lcd

# import uos

S_IFDIR = 0o040000  # directory


# noinspection PyPep8Naming
def S_IFMT(mode):
    """Return the portion of the file's mode that describes the
    file type.
    """
    return mode & 0o170000


# noinspection PyPep8Naming
def S_ISDIR(mode):
    """Return True if mode is from a directory."""
    return S_IFMT(mode) == S_IFDIR


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)



class ExplorerApp(BaseApp):
    def __init__(self, system_singleton):
        super(LauncherApp, self).__init__(system_singleton)
        self.current_offset = 0
        self.current_selected_index = 0
        self.__initialized = False
    def __lazy_init(self):
        self.current_dir_files = os.listdir("/sd/")
        print(self.current_dir_files)
        self.__initialized = True
    def on_top_button_changed(self, state):
        if state == "pressed":
            self.current_selected_index += 1
            if self.current_selected_index >= len(self.current_dir_files):
                self.current_selected_index = 0
            if self.current_selected_index >= 7:
                self.current_offset = self.current_selected_index - 6
            else:
                self.current_offset = 0
            print("current_selected=", self.current_selected_index,
                  "current_offset=", self.current_offset)
            self.invalidate_drawing()
    def on_draw(self):
        if not self.__initialized:
            self.__lazy_init()
        return
        x_offset = 4
        y_offset = 6
        lcd.clear()
        print("progress 0")
        for i in range(self.current_offset, len(self.current_dir_files)):
            # gc.collect()
            print("progress 1")
            file_name = self.current_dir_files[i]
            f_stat = os.stat('/sd/' + file_name)
            file_readable_size = sizeof_fmt(f_stat[6])
            if S_ISDIR(f_stat[0]):
                file_name = file_name + '/'
            print("current i =", i)
            is_current = self.current_selected_index == i
            line = "%s %d %s" % ("->" if is_current else "  ", i, file_name)
            lcd.draw_string(x_offset, y_offset, line, lcd.WHITE, lcd.RED)
            # gc.collect()
            lcd.draw_string(lcd.width() - 50, y_offset,
                            file_readable_size, lcd.WHITE, lcd.BLUE)
            # gc.collect()
            print("progress 2")
            y_offset += 18
            if y_offset > lcd.height():
                print("y_offset > height(), break")
                break
            print("progress 3")
            