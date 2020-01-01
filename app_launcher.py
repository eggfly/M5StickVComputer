
import os
import lcd
import sys
import time
import machine

import image

from framework import BaseApp
from app_camera import CameraApp
from app_explorer import ExplorerApp
from app_system_info import SystemInfoApp

import config
import resource


class LauncherApp(BaseApp):
    def __init__(self, system):
        super(LauncherApp, self).__init__(system)
        print("LauncherApp: super.__init__() called")
        self.app_list = resource.app_list
        self.battery_icon_list = resource.battery_icon_list
        self.battery_charging_icon_list = resource.battery_charging_icon_list
        self.arrow_icon_path = resource.arrow_icon_path
        self.app_count = len(self.app_list)
        self.cursor_index = 0
        self.need_show_top_button_tip = True
        self.animation_count = 3
        self.pending_animation_values = []
        self.icon_path_to_image_cache = {}
        self.app_periodic_task_last_time = 0

    def draw_icon(self, screen_canvas, icon_path, x, y, horizontal_align, vertical_align):
        """closure: an inner function inside a method"""
        try:
            icon = None
            if icon_path in self.icon_path_to_image_cache:
                icon = self.icon_path_to_image_cache[icon_path]
            else:
                icon = image.Image(icon_path)
                self.icon_path_to_image_cache[icon_path] = icon
            # calculate horizontal
            if "center" == horizontal_align:
                left = x - icon.width() // 2
            elif "right" == horizontal_align:
                left = x - icon.width()
            # calculate vertical
            if "center" == vertical_align:
                top = y - icon.height() // 2
            elif "top" == vertical_align:
                top = y
            screen_canvas.draw_image(icon, left, top)
        except Exception as e:
            print("cannot draw icon:", e)
            sys.print_exception(e)

    def on_draw(self):
        print("LauncherApp.on_draw()")
        icon_width = 64
        icon_height = 60
        icon_padding = 6
        icon_margin_top = 0
        screen_canvas = image.Image()
        vbat = self.get_system().pmu.getVbatVoltage() / 1000.0
        usb_plugged = self.get_system().pmu.is_usb_plugged_in()
        battery_level = self.calculate_battery_level(vbat)
        vbat_str = str(vbat) + "V"
        print("vbat", vbat_str)
        # screen_canvas.draw_string(180, 10, vbat_str, lcd.GREEN, scale=1)

        icons_count = screen_canvas.width() // (icon_width + icon_padding)
        if icons_count % 2 == 0:
            icons_count += 1
        else:
            icons_count += 2
        # icons_count must be an odd integer
        icons_half_count = icons_count // 2
        animation_offset = 0
        # handle animation
        if len(self.pending_animation_values) > 0:
            anim_index = self.pending_animation_values.pop()
            animation_offset = int(
                (icon_width + icon_padding * 2) * anim_index / self.animation_count)
            # invalidate when need animation
            self.invalidate_drawing()
        for i in range(-icons_half_count, icons_half_count + 1):
            icon_center_x = screen_canvas.width() // 2 + i * (icon_width + icon_padding)
            icon_center_y = screen_canvas.height() // 2 + icon_margin_top
            icon_center_x += animation_offset
            index = (self.cursor_index + i) % self.app_count
            self.draw_icon(screen_canvas, self.app_list[index]["icon"],
                           icon_center_x, icon_center_y, "center", "center")
        # draw center small arrow icon below
        self.draw_icon(screen_canvas, self.arrow_icon_path, screen_canvas.width() // 2,
                       screen_canvas.height() // 2 + icon_height // 2 + icon_padding + icon_margin_top, "center", "top")
        print("draw arrow ok")
        battery_percent = battery_level * 100.0
        battery_icon = self.find_battery_icon(battery_percent, usb_plugged)
        print("before draw battery")
        battery_icon_padding = 3
        self.draw_icon(screen_canvas, battery_icon,
                       screen_canvas.width() - battery_icon_padding, battery_icon_padding, "right", "top")
        print("after draw battery")
        lcd.display(screen_canvas)
        del screen_canvas
        lcd.draw_string(3, 3, "Battery: %.3fV %.1f%%" %
                        (vbat, battery_percent), lcd.GREEN)
        print("launcher on_draw end")

    def navigate(self, app):
        self.get_system().navigate(app)
        print("navigate from", self, "to", app)

    def on_home_button_changed(self, state):
        # avoid navigate twice here
        if state == "pressed":
            app_id = self.app_list[self.cursor_index]["id"]
            if app_id == "camera":
                self.navigate(CameraApp(self.get_system()))
            elif app_id == "explorer":
                self.navigate(ExplorerApp(self.get_system()))
            elif app_id == "reboot":
                machine.reset()
            elif app_id == "power":
                self.get_system().pmu.setEnterSleepMode()
            elif app_id == "system_info":
                self.navigate(SystemInfoApp(self.get_system()))
            elif app_id == "brightness":
                self.change_brightness()
        return True

    def change_brightness(self):
        value = config.get_brightness()
        value += 1
        if value > 15:
            value = 7
        self.get_system().pmu.setScreenBrightness(value)
        config.save_config("brightness", value)
        print("set and save brightness value to", value)

    def on_top_button_changed(self, state):
        if state == "pressed":
            self.cursor_index += 1
            print(self.cursor_index, len(self.app_list))
            if self.cursor_index >= self.app_count:
                self.cursor_index = 0
            self.generate_pending_animations()
            self.invalidate_drawing()
            print(self.cursor_index, len(self.app_list))
        return True

    def generate_pending_animations(self):
        self.pending_animation_values = list(range(self.animation_count))

    def on_back_pressed(self):
        # handled by launcher app
        # TODO show power options
        self.cursor_index = 0
        self.invalidate_drawing()
        return True

    def app_periodic_task(self):
        now_ticks_ms = time.ticks_ms()
        if now_ticks_ms - self.app_periodic_task_last_time > 2000:
            self.app_periodic_task_last_time = now_ticks_ms
            self.invalidate_drawing()

    def find_battery_icon(self, battery_percent, is_charging):
        icon_list = self.battery_charging_icon_list if is_charging else self.battery_icon_list
        index = int(battery_percent / 20.0)
        return icon_list[index]

    def calculate_battery_level(self, vbat):
        levels = [4.13, 4.06, 3.98, 3.92, 3.87,
                  3.82, 3.79, 3.77, 3.74, 3.68, 3.45, 3.00]
        level = 1.0
        if vbat >= levels[0]:
            level = 1.0
        elif vbat >= levels[1]:
            level = 0.9
            level += 0.1 * (vbat - levels[1]) / (levels[0] - levels[1])
        elif vbat >= levels[2]:
            level = 0.8
            level += 0.1 * (vbat - levels[2]) / (levels[1] - levels[2])
        elif vbat >= levels[3]:
            level = 0.7
            level += 0.1 * (vbat - levels[3]) / (levels[2] - levels[3])
        elif vbat >= levels[4]:
            level = 0.6
            level += 0.1 * (vbat - levels[4]) / (levels[3] - levels[4])
        elif vbat >= levels[5]:
            level = 0.5
            level += 0.1 * (vbat - levels[5]) / (levels[4] - levels[5])
        elif vbat >= levels[6]:
            level = 0.4
            level += 0.1 * (vbat - levels[6]) / (levels[5] - levels[6])
        elif vbat >= levels[7]:
            level = 0.3
            level += 0.1 * (vbat - levels[7]) / (levels[6] - levels[7])
        elif vbat >= levels[8]:
            level = 0.2
            level += 0.1 * (vbat - levels[8]) / (levels[7] - levels[8])
        elif vbat >= levels[9]:
            level = 0.1
            level += 0.1 * (vbat - levels[9]) / (levels[8] - levels[9])
        elif vbat >= levels[10]:
            level = 0.05
            level += 0.05 * (vbat - levels[10]) / (levels[9] - levels[10])
        elif vbat >= levels[11]:
            level = 0.0
            level += 0.05 * (vbat - levels[11]) / (levels[10] - levels[11])
        else:
            level = 0.0
        return level
