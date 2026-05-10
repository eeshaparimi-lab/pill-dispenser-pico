from machine import Pin, PWM, SoftI2C
import time
import utime

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────

ADD_BUTTON_PIN   = 15
START_BUTTON_PIN = 14

I2C_SDA          = 19
I2C_SCL          = 20
LCD_ADDR         = 0x27
LCD_COLS         = 16
LCD_ROWS         = 2

INCREMENT_SEC    = 10     # seconds added per button press
HOLD_RESET_MS    = 10000  # hold GP15 for 10s to reset
DEBOUNCE_MS      = 300


# ─────────────────────────────────────────
# SERVO SETUP
# ─────────────────────────────────────────

servo1 = PWM(Pin(2))
servo2 = PWM(Pin(3))
servo3 = PWM(Pin(4))

for s in (servo1, servo2, servo3):
    s.freq(95)

def set_angle(angle):
    min_duty = 8192   # intentionally swapped to reverse direction
    max_duty = 1638
    duty = int(min_duty + (max_duty - min_duty) * (angle / 180))
    for s in (servo1, servo2, servo3):
        s.duty_u16(duty)

def run_servos():
    print("Dispensing pills...")
    set_angle(110)
    time.sleep(1)
    set_angle(0)
    print("Done.")


# ─────────────────────────────────────────
# LCD DRIVER
# ─────────────────────────────────────────

class LCD:
    def __init__(self, i2c, addr=0x27, cols=16, rows=2):
        self.i2c  = i2c
        self.addr = addr
        self.cols = cols
        self.rows = rows
        self.bl   = 0x08
        self._init_lcd()

    def _write_byte(self, b):
        self.i2c.writeto(self.addr, bytes([b | self.bl]))

    def _pulse(self, b):
        self._write_byte(b | 0x04)
        utime.sleep_us(1)
        self._write_byte(b & ~0x04)
        utime.sleep_us(50)

    def _send_nibble(self, n):
        self._write_byte(n)
        self._pulse(n)

    def _send_byte(self, b, mode=0):
        hi = (b & 0xF0) | mode
        lo = ((b << 4) & 0xF0) | mode
        self._send_nibble(hi)
        self._send_nibble(lo)

    def _init_lcd(self):
        utime.sleep_ms(50)
        for _ in range(3):
            self._send_nibble(0x30)
            utime.sleep_ms(5)
        self._send_nibble(0x20)
        self._send_byte(0x28)
        self._send_byte(0x0C)
        self._send_byte(0x06)
        self.clear()

    def clear(self):
        self._send_byte(0x01)
        utime.sleep_ms(2)

    def set_cursor(self, col, row):
        self._send_byte(0x80 | (col + [0x00, 0x40][row]))

    def write(self, text):
        for ch in text:
            self._send_byte(ord(ch), mode=1)

    def print_line(self, row, text):
        text = text + " " * self.cols
        text = text[:self.cols]
        self.set_cursor(0, row)
        self.write(text)


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    add_btn   = Pin(ADD_BUTTON_PIN,   Pin.IN, Pin.PULL_UP)
    start_btn = Pin(START_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    i2c       = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=50_000)
    lcd       = LCD(i2c, addr=LCD_ADDR)

    set_angle(0)

    STATE_IDLE     = "idle"
    STATE_SETTING  = "setting"
    STATE_COUNTING = "counting"

    state             = STATE_IDLE
    saved_seconds     = 0
    remaining_seconds = 0
    last_add_time     = 0
    last_start_time   = 0
    last_tick         = utime.ticks_ms()
    btn_hold_start    = 0
    holding           = False

    lcd.print_line(0, "Press + to set  ")
    lcd.print_line(1, "pill time (10s) ")

    while True:
        now = utime.ticks_ms()

        # ── GP15 hold-to-reset detection ──
        if add_btn.value() == 0:
            if not holding:
                holding        = True
                btn_hold_start = now
            else:
                held_ms = utime.ticks_diff(now, btn_hold_start)

                if state == STATE_COUNTING and saved_seconds > 0:
                    secs_held = held_ms // 1000
                    lcd.print_line(0, "Hold to reset...")
                    lcd.print_line(1, f"{secs_held}s / 10s         ")

                if held_ms >= HOLD_RESET_MS:
                    print("Reset triggered.")
                    state             = STATE_IDLE
                    saved_seconds     = 0
                    remaining_seconds = 0
                    holding           = False
                    btn_hold_start    = 0
                    lcd.print_line(0, "Press + to set  ")
                    lcd.print_line(1, "pill time (10s) ")
                    utime.sleep_ms(500)
                    continue

        else:
            if holding:
                held_ms = utime.ticks_diff(now, btn_hold_start)
                holding = False

                if held_ms < DEBOUNCE_MS:
                    pass  # ignore noise
                elif held_ms < HOLD_RESET_MS:
                    if state in (STATE_IDLE, STATE_SETTING):
                        if utime.ticks_diff(now, last_add_time) > DEBOUNCE_MS:
                            last_add_time     = now
                            remaining_seconds += INCREMENT_SEC
                            state             = STATE_SETTING
                            mins = remaining_seconds // 60
                            secs = remaining_seconds % 60
                            lcd.print_line(0, "Time set:       ")
                            lcd.print_line(1, f"{mins:02d}m {secs:02d}s        ")
                            print(f"Added 10s -> {remaining_seconds}s total")

        # ── Start button (GP14) ──
        if start_btn.value() == 0:
            if utime.ticks_diff(now, last_start_time) > DEBOUNCE_MS:
                last_start_time = now
                if state == STATE_SETTING and remaining_seconds > 0:
                    saved_seconds = remaining_seconds
                    state         = STATE_COUNTING
                    last_tick     = utime.ticks_ms()
                    print(f"Countdown started: {saved_seconds}s")

        # ── Countdown (1-second ticks) ──
        if state == STATE_COUNTING and remaining_seconds > 0:
            if utime.ticks_diff(now, last_tick) >= 1000:
                remaining_seconds -= 1
                last_tick = utime.ticks_ms()
                mins = remaining_seconds // 60
                secs = remaining_seconds % 60
                lcd.print_line(0, "Next pill in:   ")
                lcd.print_line(1, f"{mins:02d}m {secs:02d}s        ")

        # ── Fire servos + auto repeat ──
        if state == STATE_COUNTING and remaining_seconds == 0:
            lcd.print_line(0, "  Time to take  ")
            lcd.print_line(1, "   your pill!   ")
            run_servos()
            remaining_seconds = saved_seconds
            last_tick         = utime.ticks_ms()
            print(f"Repeating in {saved_seconds}s")

        utime.sleep_ms(50)


main()
