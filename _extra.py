
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
