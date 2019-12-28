
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
