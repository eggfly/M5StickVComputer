import lcd
import image
import time
import uos
import os
import gc
import sys

from Maix import GPIO
from board import board_info
from fpioa_manager import fm

from Maix import I2S
import audio

from my_pmu import AXP192

from framework import BaseApp
from app_camera import CameraApp

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
        x_offset = 4
        y_offset = 6
        lcd.clear()
        print("progress 0")
        for i in range(self.current_offset, len(self.current_dir_files)):
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
            gc.collect()
            lcd.draw_string(lcd.width() - 50, y_offset,
                            file_readable_size, lcd.WHITE, lcd.BLUE)
            gc.collect()
            print("progress 2")
            y_offset += 18
            if y_offset > lcd.height():
                print("y_offset > height(), break")
                break
            del file_name
            print("progress 3")
            
class LauncherApp(BaseApp):
    def __init__(self, system_singleton):
        super(LauncherApp, self).__init__(system_singleton)
        print("LauncherApp: super.__init__() called")
        self.app_list = [
            {"id": "camera", "icon": "/sd/icons/camera.jpg"},
            {"id": "explorer", "icon": "/sd/icons/memory_card.jpg"},
            {"id": "settings", "icon": "/sd/icons/settings.jpg"},
            {"id": "music", "icon": "/sd/icons/music.jpg"},
            {"id": "tools", "icon": "/sd/icons/tools.jpg"},
        ]
        self.app_count = len(self.app_list)
        self.cursor_index = 0

    def on_draw(self):
        print("LauncherApp.on_draw()")
        icon_width = icon_height = 64
        icon_padding = 6
        screen_canvas = image.Image()

        # closure: an inner function inside a method
        def draw_icon(icon_path, center_x, center_y):
            icon = image.Image(icon_path)
            screen_canvas.draw_image(icon, center_x - icon.width() // 2,
                                     center_y - icon.height() // 2)
            del icon

        icons_count = screen_canvas.width() // (icon_width + icon_padding)
        if icons_count % 2 == 0:
            icons_count += 1
        else:
            icons_count += 2
        # icons_count must be an odd integer
        icons_half_count = icons_count // 2
        for i in range(-icons_half_count, icons_half_count + 1):
            icon_center_x = screen_canvas.width() // 2 + i * (icon_width + icon_padding)
            icon_center_y = screen_canvas.height() // 2 - 5
            index = (self.cursor_index + i) % self.app_count
            draw_icon(self.app_list[index]["icon"], icon_center_x, icon_center_y)
        # draw center small arrow icon below
        draw_icon('/sd/icons/arrow_top_24.jpg', screen_canvas.width() // 2,
                  screen_canvas.height() // 2 + icon_height // 2 + icon_padding + 5)
        lcd.display(screen_canvas)
        del screen_canvas

    def navigate(self, app):
        self.system_singleton.navigate(app)
        print("navigate from", self, "to", app)

    def on_home_button_changed(self, state):
        app_id = self.app_list[self.cursor_index]["id"]
        if app_id == "camera":
            self.navigate(CameraApp(self.system_singleton))
        elif app_id == "explorer":
            self.navigate(ExplorerApp(self.system_singleton))
        return True

    def on_top_button_changed(self, state):
        if state == "pressed":
            self.cursor_index += 1
            print(self.cursor_index, len(self.app_list))
            if self.cursor_index >= self.app_count:
                self.cursor_index = 0
            self.invalidate_drawing()
            print(self.cursor_index, len(self.app_list))
        return True

    def on_back_pressed(self):
        # handled by launcher app
        self.cursor_index = 0
        self.invalidate_drawing()
        return True


class StickVSystem:
    def __init__(self):
        self.pmu = AXP192()
        self.pmu.setScreenBrightness(8)  # 7-15 is ok, normally 8
        self.pmu.set_on_pressed_listener(self.on_pek_button_pressed)
        self.pmu.set_on_long_pressed_listener(self.on_pek_button_long_pressed)
        self.app_stack = []

        lcd.init()
        lcd.rotation(2)  # Rotate the lcd 180deg

        self.fm = None
        self.home_button = None
        self.top_button = None
        self.led_w = None
        self.led_r = None
        self.led_g = None
        self.led_b = None
        self.spk_sd = None
        self.init_fm()

        self.is_drawing_dirty = False
        self.navigate(LauncherApp(self))

    def button_irq(self, gpio, pin_num):
        value = gpio.value()
        state = "released" if value else "pressed"
        print("button_irq:", gpio, pin_num, state)
        if self.home_button is gpio:
            self.on_home_button_changed(state)
        elif self.top_button is gpio:
            self.on_top_button_changed(state)

    # noinspection SpellCheckingInspection
    def init_fm(self):
        # noinspection PyGlobalUndefined
        global fm
        self.fm = fm

        # home button
        fm.register(board_info.BUTTON_A, fm.fpioa.GPIOHS21)
        # PULL_UP is required here!
        self.home_button = GPIO(GPIO.GPIOHS21, GPIO.IN, GPIO.PULL_UP)
        self.home_button.irq(self.button_irq, GPIO.IRQ_BOTH,
                             GPIO.WAKEUP_NOT_SUPPORT, 7)

        if self.home_button.value() == 0:  # If don't want to run the demo
            sys.exit()

        # top button
        fm.register(board_info.BUTTON_B, fm.fpioa.GPIOHS22)
        # PULL_UP is required here!
        self.top_button = GPIO(GPIO.GPIOHS22, GPIO.IN, GPIO.PULL_UP)
        self.top_button.irq(self.button_irq, GPIO.IRQ_BOTH,
                            GPIO.WAKEUP_NOT_SUPPORT, 7)

        fm.register(board_info.LED_W, fm.fpioa.GPIO3)
        self.led_w = GPIO(GPIO.GPIO3, GPIO.OUT)
        self.led_w.value(1)  # RGBW LEDs are Active Low

        fm.register(board_info.LED_R, fm.fpioa.GPIO4)
        self.led_r = GPIO(GPIO.GPIO4, GPIO.OUT)
        self.led_r.value(1)  # RGBW LEDs are Active Low

        fm.register(board_info.LED_G, fm.fpioa.GPIO5)
        self.led_g = GPIO(GPIO.GPIO5, GPIO.OUT)
        self.led_g.value(1)  # RGBW LEDs are Active Low

        fm.register(board_info.LED_B, fm.fpioa.GPIO6)
        self.led_b = GPIO(GPIO.GPIO6, GPIO.OUT)
        self.led_b.value(1)  # RGBW LEDs are Active Low

        fm.register(board_info.SPK_SD, fm.fpioa.GPIO0)
        self.spk_sd = GPIO(GPIO.GPIO0, GPIO.OUT)
        self.spk_sd.value(1)  # Enable the SPK output

        fm.register(board_info.SPK_DIN, fm.fpioa.I2S0_OUT_D1)
        fm.register(board_info.SPK_BCLK, fm.fpioa.I2S0_SCLK)
        fm.register(board_info.SPK_LRCLK, fm.fpioa.I2S0_WS)

    def invalidate_drawing(self):
        self.is_drawing_dirty = True

    def run(self):
        while True:
            if self.is_drawing_dirty:
                self.is_drawing_dirty = False
                current_app = self.get_current_app()
                current_app.on_draw()
                print("on_draw() of", current_app, "called, free memory:", gc.mem_free())
                # this gc is to avoid: "core dump: misaligned load" error
                gc.collect()
                print("after gc.collect(), free memory:", gc.mem_free())
            time.sleep_ms(10)  # TODO check

    def navigate(self, app):
        self.app_stack.append(app)
        self.invalidate_drawing()

    def navigate_back(self):
        self.app_stack.pop()
        self.invalidate_drawing()

    def get_current_app(self):
        return self.app_stack[-1]

    def on_pek_button_pressed(self, axp):
        # treat short press as navigate back
        print("on_pek_button_pressed", axp)
        handled = self.get_current_app().on_back_pressed()
        if handled is False:
            print("on_back_pressed() not handled, exit current app")
            self.navigate_back()
        machine.reset()

    # noinspection PyMethodMayBeStatic
    def on_pek_button_long_pressed(self, axp):
        print("on_pek_button_long_pressed", axp)
        axp.setEnterSleepMode()

    def on_home_button_changed(self, state):
        print("on_home_button_changed", state)
        self.get_current_app().on_home_button_changed(state)

    def on_top_button_changed(self, state):
        print("on_top_button_changed", state)
        self.get_current_app().on_top_button_changed(state)


m5stickv_system = StickVSystem()
m5stickv_system.run()
