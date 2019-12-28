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

# start of pmu.py
from machine import I2C, Timer
import machine


class PMUError(Exception):
    pass


class NotFoundError(PMUError):
    pass


class OutOfRange(PMUError):
    pass


class AXP192:
    def __init__(self, i2cDev=None):
        if i2cDev is None:
            try:
                self.i2cDev = I2C(I2C.I2C0, freq=400000, scl=28, sda=29)
            except Exception:
                raise PMUError("Unable to init I2C0 as Master")
        else:
            self.i2cDev = i2cDev

        self.axp192Addr = 52

        self.__preButPressed__ = -1
        self.onPressedListener = None
        self.onLongPressedListener = None
        scan_list = self.i2cDev.scan()
        if self.axp192Addr not in scan_list:
            raise NotFoundError
        # enable timer by default
        self.enablePMICSleepMode(True)

    def set_on_pressed_listener(self, listener):
        self.onPressedListener = listener

    def set_on_long_pressed_listener(self, listener):
        self.onLongPressedListener = listener

    def __chkPwrKeyWaitForSleep__(self, timer):
        self.i2cDev.writeto(52, bytes([0x46]))
        pek_stu = (self.i2cDev.readfrom(52, 1))[0]
        self.i2cDev.writeto_mem(52, 0x46, 0xFF, mem_size=8)  # Clear IRQ

        # Prevent loop in restart, wait for release
        if self.__preButPressed__ == -1 and ((pek_stu & (0x01 << 1)) or (pek_stu & 0x01)):
            # print("return")
            return

        if self.__preButPressed__ == -1 and ((pek_stu & (0x01 << 1)) == False and (pek_stu & 0x01) == False):
            self.__preButPressed__ = 0
            print("self.__preButPressed__ == 0")

        if pek_stu & 0x01:
            print("before enter sleep")
            if self.onLongPressedListener:
                self.onLongPressedListener(self)
            print("after enter sleep is never called")

        if pek_stu & (0x01 << 1):
            if self.onPressedListener:
                self.onPressedListener(self)
            print("before machine.reset()")
            print("after machine.reset() never called")

    def __write_reg(self, reg_address, value):
        self.i2cDev.writeto_mem(self.axp192Addr, reg_address, value, mem_size=8)

    def __read_reg(self, reg_address):
        self.i2cDev.writeto(self.axp192Addr, bytes([reg_address]))
        return (self.i2cDev.readfrom(self.axp192Addr, 1))[0]

    def enable_adc(self, enable):
        if enable:
            self.__write_reg(0x82, 0xFF)
        else:
            self.__write_reg(0x82, 0x00)

    def enable_coulomb_counter(self, enable):
        if enable:
            self.__write_reg(0xB8, 0x80)
        else:
            self.__write_reg(0xB8, 0x00)

    def stop_coulomb_counter(self):
        self.__write_reg(0xB8, 0xC0)

    def clear_coulomb_counter(self):
        self.__write_reg(0xB8, 0xA0)

    def __get_coulomb_charge_data(self):
        CoulombCounter_LSB = self.__read_reg(0xB0)
        CoulombCounter_B1 = self.__read_reg(0xB1)
        CoulombCounter_B2 = self.__read_reg(0xB2)
        CoulombCounter_MSB = self.__read_reg(0xB3)

        return ((CoulombCounter_LSB << 24) + (CoulombCounter_B1 << 16) +
                (CoulombCounter_B2 << 8) + CoulombCounter_MSB)

    def __get_coulomb_discharge_data(self):
        CoulombCounter_LSB = self.__read_reg(0xB4)
        CoulombCounter_B1 = self.__read_reg(0xB5)
        CoulombCounter_B2 = self.__read_reg(0xB6)
        CoulombCounter_MSB = self.__read_reg(0xB7)

        return ((CoulombCounter_LSB << 24) + (CoulombCounter_B1 << 16) +
                (CoulombCounter_B2 << 8) + CoulombCounter_MSB)

    def get_coulomb_counter_data(self):
        return 65536 * 0.5 * (self.__get_coulomb_charge_data() -
                              self.__get_coulomb_discharge_data) / 3600.0 / 25.0

    def getVbatVoltage(self):
        Vbat_LSB = self.__read_reg(0x78)
        Vbat_MSB = self.__read_reg(0x79)

        return ((Vbat_LSB << 4) + Vbat_MSB) * 1.1  # AXP192-DS PG26 1.1mV/div

    def getUSBVoltage(self):
        Vin_LSB = self.__read_reg(0x56)
        Vin_MSB = self.__read_reg(0x57)

        return ((Vin_LSB << 4) + Vin_MSB) * 1.7  # AXP192-DS PG26 1.7mV/div

    def getUSBInputCurrent(self):
        Iin_LSB = self.__read_reg(0x58)
        Iin_MSB = self.__read_reg(0x59)

        return ((Iin_LSB << 4) + Iin_MSB) * 0.625  # AXP192-DS PG26 0.625mA/div

    def getConnextVoltage(self):
        Vcnx_LSB = self.__read_reg(0x5A)
        Vcnx_MSB = self.__read_reg(0x5B)

        return ((Vcnx_LSB << 4) + Vcnx_MSB) * 1.7  # AXP192-DS PG26 1.7mV/div

    def getConnextInputCurrent(self):
        IinCnx_LSB = self.__read_reg(0x5C)
        IinCnx_MSB = self.__read_reg(0x5D)

        # AXP192-DS PG26 0.625mA/div
        return ((IinCnx_LSB << 4) + IinCnx_MSB) * 0.625

    def getBatteryChargeCurrent(self):
        Ichg_LSB = self.__read_reg(0x7A)
        Ichg_MSB = self.__read_reg(0x7B)

        return ((Ichg_LSB << 5) + Ichg_MSB) * 0.5  # AXP192-DS PG27 0.5mA/div

    def getBatteryDischargeCurrent(self):
        Idcg_LSB = self.__read_reg(0x7C)
        Idcg_MSB = self.__read_reg(0x7D)

        return ((Idcg_LSB << 5) + Idcg_MSB) * 0.5  # AXP192-DS PG27 0.5mA/div

    def getBatteryInstantWatts(self):
        Iinswat_LSB = self.__read_reg(0x70)
        Iinswat_B2 = self.__read_reg(0x71)
        Iinswat_MSB = self.__read_reg(0x72)

        # AXP192-DS PG32 0.5mA*1.1mV/1000/mW
        return ((Iinswat_LSB << 16) + (Iinswat_B2 << 8) + Iinswat_MSB) * 1.1 * 0.5 / 1000

    def getTemperature(self):
        Temp_LSB = self.__read_reg(0x5E)
        Temp_MSB = self.__read_reg(0x5F)

        # AXP192-DS PG26 0.1degC/div -144.7degC Biased
        return (((Temp_LSB << 4) + Temp_MSB) * 0.1) - 144.7

    def setK210Vcore(self, vol):
        if vol > 1.05 or vol < 0.8:
            raise OutOfRange("Voltage is invaild for K210")
        DCDC2Steps = int((vol - 0.7) * 1000 / 25)
        self.__write_reg(0x23, DCDC2Steps)

    def setScreenBrightness(self, brightness):
        if brightness > 15 or brightness < 0:
            raise OutOfRange("Range for brightness is from 0 to 15")
        self.__write_reg(0x91, (int(brightness) & 0x0f) << 4)

    def getKeyStuatus(self):  # -1: NoPress, 1: ShortPress, 2:LongPress
        but_stu = self.__read_reg(0x46)
        if (but_stu & (0x1 << 1)):
            return 1
        else:
            if (but_stu & (0x1 << 0)):
                return 2
            else:
                return -1

    def setEnterSleepMode(self):
        self.__write_reg(0x31, 0x0F)  # Enable Sleep Mode
        self.__write_reg(0x91, 0x00)  # Turn off GPIO0/LDO0
        self.__write_reg(0x12, 0x00)  # Turn off other power source

    def enablePMICSleepMode(self, enable):
        if enable:
            self.__write_reg(0x36, 0x27)  # Turnoff PEK Overtime Shutdown
            self.__write_reg(0x46, 0xFF)  # Clear the interrupts
            self.butChkTimer = Timer(Timer.TIMER2, Timer.CHANNEL0, mode=Timer.MODE_PERIODIC,
                                     period=500, callback=self.__chkPwrKeyWaitForSleep__)
        else:
            self.__write_reg(0x36, 0x6C)  # Set to default
            try:
                self.butChkTimer.stop()
                del self.butChkTimer
            except Exception:
                pass


# end of pmu.py


class BaseApp:
    def __init__(self, system_singleton):
        print("BaseApp.__init__ called")
        self.system_singleton = system_singleton

    def on_draw(self):
        pass

    def on_back_pressed(self):
        # not handled by default
        return False

    def on_home_button_changed(self, state):
        return False

    def on_top_button_changed(self, state):
        return False

    def invalidate_drawing(self):
        self.system_singleton.invalidate_drawing()


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
        icons_half_count = icons_count // 2
        # icons_count must be an odd integer
        for i in range(-icons_half_count, icons_half_count + 1):
            icon_center_x = screen_canvas.width() // 2 + i * (icon_width + icon_padding)
            icon_center_y = screen_canvas.height() // 2 - 5
            index = (self.cursor_index + i) % len(self.app_list)
            draw_icon(self.app_list[index]["icon"], icon_center_x, icon_center_y)
        # draw center small arrow icon below
        draw_icon('/sd/icons/arrow_top_24.jpg', screen_canvas.width() // 2,
                  screen_canvas.height() // 2 + icon_height // 2 + icon_padding + 5)
        lcd.display(screen_canvas)
        del screen_canvas

    def on_home_button_changed(self, state):
        return True

    def on_top_button_changed(self, state):
        if state == "pressed":
            self.cursor_index += 1
            print(self.cursor_index, len(self.app_list))
            if self.cursor_index >= len(self.app_list):
                self.cursor_index = 0
                print("cursor_index set to 0")
            print(self.cursor_index, len(self.app_list))
            self.invalidate_drawing()
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


system = StickVSystem()
system.run()


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


root_files = os.listdir('/')
for f in root_files:
    fs_path = '/' + f
    fs_stat = uos.statvfs(fs_path)
    bs1 = fs_stat[0]
    bs2 = fs_stat[1]
    total_blocks = fs_stat[2]
    free_blocks = fs_stat[3]
    print("fs: %s, total: %s, free: %s" %
          (fs_path, sizeof_fmt(bs1 * total_blocks), sizeof_fmt(bs2 * free_blocks)))
# uos.statvfs('/sd')
# (32768, 32768, 475520, 472555, 472555, 0, 0, 0, 0, 255)


try:
    # img = image.Image("/sd/win98_240x135.jpg")
    img = image.Image("/flash/startup.jpg")
    print("240")
    lcd.display(img)
    del img
    print("display 240")
    # eggfly mod
    print("brfore, mem_free:", gc.mem_free())
    screen_canvas = image.Image()
    print("after, mem_free:", gc.mem_free())
    print("screen_canvas info:", screen_canvas.width(), screen_canvas.height())
    print("screen_canvas")
    # screen_canvas.draw_rectangle(0,0,screen_canvas.width(), screen_canvas.height(), lcd.WHITE, fill=True)
    icon_power = image.Image("/sd/icons/power.jpg")
    print("icon_power info:", icon_power.width(), icon_power.height())
    screen_canvas.draw_image(icon_power, 20, 30)
    del icon_power
    print("icon_power, mem_free:", gc.mem_free())
    gc.collect()
    print("icon_power2, mem_free:", gc.mem_free())
    icon_reboot = image.Image("/sd/icons/reboot.jpg")
    screen_canvas.draw_image(icon_reboot, 110, 30)
    del icon_reboot
    print("icon_reboot, mem_free:", gc.mem_free())
    lcd.display(screen_canvas)
    # time.sleep(1)
except Exception as e:
    print(e)
    lcd.draw_string(lcd.width() // 2 - 100, lcd.height() // 2 - 4,
                    "Error: Cannot find start.jpg", lcd.WHITE, lcd.RED)

wav_dev = I2S(I2S.DEVICE_0)
# i2s0:(sampling rate=0, sampling points=1024)

print(wav_dev)
"""
[MAIXPY]: result = 0
[MAIXPY]: numchannels = 1
[MAIXPY]: samplerate = 44100
[MAIXPY]: byterate = 88200
[MAIXPY]: blockalign = 2
[MAIXPY]: bitspersample = 16
[MAIXPY]: datasize = 246960
True
[1, 44100, 88200, 2, 16, 246960]
"""
try:
    # player = audio.Audio(path = "/flash/ding.wav")
    player = audio.Audio(path="/sd/super_mario.wav")
    player.volume(0)  # todo change this
    wav_info = player.play_process(wav_dev)
    wav_dev.channel_config(wav_dev.CHANNEL_1, I2S.TRANSMITTER,
                           resolution=I2S.RESOLUTION_16_BIT, align_mode=I2S.STANDARD_MODE)
    print(wav_info)
    wav_dev.set_sample_rate(wav_info[1])
    while True:
        ret = player.play()
        if ret == None:
            break
        elif ret == 0:
            break
    player.finish()
except Exception as e:
    print(e)
    print("ignored")
    pass

# time.sleep(1.5)  # Delay for few seconds to see the start-up screen :p


# pmu.setScreenBrightness(8)

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


but_stu = 1

current_dir_files = os.listdir("/sd/")
print(current_dir_files)
current_offset = 0
current_selected_index = 0


def on_button_b_clicked():
    print("on_button_b_clicked")
    global current_offset, current_selected_index
    current_selected_index += 1
    if current_selected_index >= len(current_dir_files):
        current_selected_index = 0
    if current_selected_index >= 7:
        current_offset = current_selected_index - 6
    else:
        current_offset = 0
    print("current_selected=", current_selected_index,
          "current_offset=", current_offset)


try:
    while True:
        x_offset = 4
        y_offset = 6
        lcd.clear()
        for i in range(current_offset, len(current_dir_files)):
            file_name = current_dir_files[i]
            f_stat = os.stat('/sd/' + file_name)
            file_readable_size = sizeof_fmt(f_stat[6])
            if S_ISDIR(f_stat[0]):
                file_name = file_name + '/'
            # print("current i=", i)
            is_current = current_selected_index == i
            line = "%s %d %s" % ("->" if is_current else "  ", i, file_name)
            lcd.draw_string(x_offset, y_offset, line, lcd.WHITE, lcd.RED)
            lcd.draw_string(lcd.width() - 50, y_offset,
                            file_readable_size, lcd.WHITE, lcd.BLUE)
            y_offset += 18
            if y_offset > lcd.height():
                print("y_offset > height(), break")
                break
            del file_name
        while but_b.value() != 0:
            # wait b key
            pass
        while but_b.value() == 0:
            # wait b key release
            pass
        on_button_b_clicked()

except KeyboardInterrupt:
    sys.exit()
