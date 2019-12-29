import lcd
import machine

from Maix import GPIO
from board import board_info
from fpioa_manager import fm

#import gc
import time

from my_pmu import AXP192
from app_launcher import LauncherApp


class M5StickVSystem:
    def __init__(self):
        self.pmu = AXP192()
        self.pmu.setScreenBrightness(8)  # 7-15 is ok, normally 8
        self.pmu.set_on_pressed_listener(self.on_pek_button_pressed)
        self.pmu.set_on_long_pressed_listener(self.on_pek_button_long_pressed)
        self.app_stack = []

        lcd.init()
        lcd.rotation(2)  # Rotate the lcd 180deg

        self.home_button = None
        self.top_button = None
        self.led_w = None
        self.led_r = None
        self.led_g = None
        self.led_b = None
        self.spk_sd = None
        self.is_handling_irq = False
        self.init_fm()
        self.message_queue = []

        self.is_drawing_dirty = False
        self.navigate(LauncherApp(self))

    def button_irq(self, gpio, optional_pin_num=None):
        # Notice: optional_pin_num exist in older firmware
        # gpio.disirq()
        if self.is_handling_irq:
            print("is_handing_irq, ignore")
            return
        self.is_handing_irq = True
        value = gpio.value()
        state = "released" if value else "pressed"
        # msg = {"type": "key_event", "gpio": gpio, "state": state}
        # self.message_queue.append(msg)
        # print("button_irq enqueued:", gpio, optional_pin_num, state)
        if self.home_button is gpio:
            self.on_home_button_changed(state)
        elif self.top_button is gpio:
            self.on_top_button_changed(state)
        self.is_handing_irq = False
        #gpio.irq(self.button_irq, GPIO.IRQ_BOTH, GPIO.WAKEUP_NOT_SUPPORT, 7)

    # noinspection SpellCheckingInspection
    def init_fm(self):
        # home button
        fm.register(board_info.BUTTON_A, fm.fpioa.GPIOHS21)
        # PULL_UP is required here!
        self.home_button = GPIO(GPIO.GPIOHS21, GPIO.IN, GPIO.PULL_UP)
        self.home_button.irq(self.button_irq, GPIO.IRQ_BOTH,
                             GPIO.WAKEUP_NOT_SUPPORT, 7)

        # if self.home_button.value() == 0:  # If don't want to run the demo
        #     sys.exit()

        # top button
        fm.register(board_info.BUTTON_B, fm.fpioa.GPIOHS22)
        # PULL_UP is required here!
        self.top_button = GPIO(GPIO.GPIOHS22, GPIO.IN, GPIO.PULL_UP)
        self.top_button.irq(self.button_irq, GPIO.IRQ_BOTH,
                            GPIO.WAKEUP_NOT_SUPPORT, 7)
        return # TODO: fix me
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
                print("drawing is dirty")
                self.is_drawing_dirty = False
                current_app = self.get_current_app()
                # gc.collect()
                # print("before on_draw() of", current_app, "free memory:", gc.mem_free())
                current_app.on_draw()
                # print("on_draw() of", current_app, "called, free memory:", gc.mem_free())
                # this gc is to avoid: "core dump: misaligned load" error
                # gc.collect()
                # print("after gc.collect(), free memory:", gc.mem_free())
                print("sleep_ms for 1ms")
                time.sleep_ms(1)
            else:
                pass
                # print("sleep_ms for a while")
                # time.sleep_ms(100)  # TODO check

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

