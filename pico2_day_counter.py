from machine import Pin, SoftI2C
import utime

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────

PIR_PIN  = 28
I2C_SDA  = 0
I2C_SCL  = 1
LCD_ADDR = 0x27   # change to 0x3F if screen stays blank
LCD_COLS = 16
LCD_ROWS = 2

MOTION_DURATION_MS = 500   # motion must be held for 0.5s to count


# ─────────────────────────────────────────
# LCD DRIVER (no external libraries needed)
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
        text = (text + " " * self.cols)[:self.cols]
        self.set_cursor(0, row)
        self.write(text)


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

pir = Pin(PIR_PIN, Pin.IN)
i2c = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=50000)
lcd = LCD(i2c, addr=LCD_ADDR)

count        = 7
motion_start = None   # when continuous motion began
counted      = False  # prevents double count per motion event

lcd.print_line(0, str(count) + " days supply")
lcd.print_line(1, "left")

while True:
    motion = pir.value()  # HIGH = motion detected

    if motion:
        if motion_start is None:
            motion_start = utime.ticks_ms()
            counted      = False
        elapsed = utime.ticks_diff(utime.ticks_ms(), motion_start)
        if elapsed >= MOTION_DURATION_MS and not counted:
            count -= 1
            counted = True
            if count <= 0:
                lcd.print_line(0, "ZERO! Resetting")
                lcd.print_line(1, "")
                utime.sleep_ms(2000)
                count = 7
            lcd.print_line(0, str(count) + " days supply")
            lcd.print_line(1, "left")
    else:
        motion_start = None
        counted      = False

    utime.sleep_ms(50)
