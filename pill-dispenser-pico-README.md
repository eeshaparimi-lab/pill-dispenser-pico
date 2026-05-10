# Automated Pill Dispenser — Raspberry Pi Pico

An interval-based autonomous pill dispenser supporting up to three medications simultaneously. Built with two Raspberry Pi Picos running MicroPython for Northeastern University's Cornerstone of Engineering II.

**Team:** Eesha Parimi, Kendall Wilson, Juliana Pequignot, Dylan Mursalim

---

![System running — LCD showing "Press + to set pill time (10s)"](images/lcd-idle.jpg)

---

## The problem

Around 50% of patients with chronic conditions fail to take medication as prescribed (WHO, 2003). Existing automated dispensers on the market (£50–£300) each addressed only one or two of the four requirements we identified as essential:
- Autonomous dispensing at user-set intervals
- Support for multiple medications simultaneously
- Real-time supply monitoring
- Easy pill retrieval for users with limited dexterity

No single product addressed all four — that was our design target.

---

## Design decisions

Three dispensing mechanisms were evaluated across five weighted criteria (pill shape compatibility 25%, ease of user loading 25%, automation feasibility 20%, 3D print simplicity 15%, supply tracking 15%):

| Concept | Why rejected |
|---|---|
| Carousel dispenser | Fixed compartment sizing couldn't accommodate varying pill shapes |
| Pill organiser box with lid-opening arm | Still required individual daily loading; dexterity barrier |
| **Gravity-fed tube (selected)** | No daily loading, works for all pill shapes, most straightforward to automate |

The gravity-fed tube scored highest, particularly on the two criteria (pill shape + loading ease) that together made up 50% of the weighting given our target users.

---

## System architecture

Two Picos are used because both LCD drivers run blocking I2C communication — running both LCDs alongside servo PWM on a single board caused timing conflicts that made the countdown unreliable.

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│        Pico 1 — Dispenser       │     │      Pico 2 — Day Counter    │
│                                 │     │                              │
│  GP15 → Blue add-time button    │     │  GP28 → HC-SR501 PIR sensor  │
│  GP14 → Red start button        │     │  GP0/1 → LCD (day supply)    │
│  GP2/3/4 → 3x SG90 servo motors │     │                              │
│  GP19/20 → LCD countdown        │     └──────────────────────────────┘
└─────────────────────────────────┘
```

---

## Hardware components

| Component | Spec | Purpose |
|---|---|---|
| Raspberry Pi Pico (×2) | MicroPython, GPIO + I2C | Microcontrollers |
| SG90 Servo Motors (×3) | 0–180°, 1.8 kg·cm stall torque @ 4.8V | Actuate pill release mechanism |
| 16×2 I2C LCD (×2) | Address 0x27, SoftI2C @ 50 kHz | Countdown display + day supply display |
| HC-SR501 PIR Sensor | Detection range 3–7m, adjustable delay 0–18s | Detects pill collection |
| Push buttons (×2) | Internal pull-up via software | Blue adds time; red starts/resets |

---

## Enclosure — SolidWorks + 3D printed PLA

The enclosure and servo arms were designed in SolidWorks and printed in PLA.

**Enclosure:** The original single-piece box-and-scoop model (180mm × 120mm × 90mm) exceeded the printer build plate and required a 6-hour print, so it was sliced into two parts — box and front scoop — bonded with PLA adhesive.

**Scoop angle iterations:**

| Angle | Problem |
|---|---|
| 45° | Pills overshot the scoop |
| 20° | Difficult to pick up pills; blocked PIR sensor line of sight |
| **30° (final)** | Balanced landing speed, accessibility, and PIR detection reliability |

**Servo arms:** Stock SG90 arms (22mm) didn't generate enough torque to fully press the dispenser buttons (~0.4 kg·cm required at contact point). Custom arms designed in SolidWorks at 35mm resolved the torque deficit. Springs inside the dispensers were also replaced with lower spring-constant variants (k ≈ 0.3 N/mm) so the extended arms could complete full button travel consistently.

![3D-printed PLA enclosure with three gravity-fed dispensers and 30° collection scoop](images/enclosure-front.jpg)

---

## Files

| File | Description |
|---|---|
| `pico1_dispenser.py` | Main dispensing logic — timer, buttons, servos, LCD countdown |
| `pico2_day_counter.py` | PIR motion detection + day supply LCD |

---

## Wiring

### Pico 1 — Dispenser

| Component | Pin |
|---|---|
| Blue add-time button | GP15 (PULL_UP) |
| Red start button | GP14 (PULL_UP) |
| Servo 1 | GP2 |
| Servo 2 | GP3 |
| Servo 3 | GP4 |
| LCD SDA | GP19 |
| LCD SCL | GP20 |
| LCD power | **3V3 (pin 36)** |
| LCD GND | GND |

> ⚠️ **Power the LCD from 3V3 (pin 36), not VSYS (pin 39).** VSYS is a power input to the Pico, not an output. Connecting LCD VCC there causes `OSError EIO` / `ETIMEDOUT` on I2C init — the bus scan returns nothing and the screen stays blank.

### Pico 2 — Day Counter

| Component | Pin |
|---|---|
| HC-SR501 PIR sensor | GP28 |
| LCD SDA | GP0 |
| LCD SCL | GP1 |

![Wiring — breadboard and Pico with LCD](images/wiring.jpg)

---

## Servo configuration

```python
servo.freq(95)          # 95 Hz — more reliable response than standard 50 Hz for these servos
SERVO_MIN_DUTY = 8192   # intentionally inverted vs standard
SERVO_MAX_DUTY = 1638   # swapped min/max reverses direction across full PWM range
SERVO_ON_ANGLE = 110    # degrees when dispensing (0° → 110° → 0° in 1-second cycle)
SERVO_OFF_ANGLE = 0     # resting position
```

The min/max duty values are **intentionally swapped** to correct servo direction. After remounting, increasing angle physically moved the servos the wrong way — swapping the duty cycle bounds reverses the entire PWM range without changing any angle logic elsewhere in the code.

---

## LCD driver

No external libraries. A full I2C LCD driver was written from scratch in MicroPython, communicating in 4-bit mode: each byte sent as two 4-bit nibbles with a manual enable pulse between them. Handles backlight control, cursor positioning, and line padding.

Uses `SoftI2C` (software bit-banging) rather than hardware I2C — hardware I2C failed to detect the LCD during testing; `SoftI2C` bypassed the hardware bus and resolved it.

To confirm your LCD's I2C address before flashing:

```python
from machine import Pin, SoftI2C
i2c = SoftI2C(sda=Pin(19), scl=Pin(20), freq=50_000)
print([hex(d) for d in i2c.scan()])  # expect ['0x27']
```

---

## PIR sensor

The HC-SR501 is a passive infrared sensor with a **single digital output pin** — HIGH when motion detected, LOW otherwise. No TRIG pin needed (unlike ultrasonic sensors). A 5-second cooldown between triggers prevents false counts. When the day counter hits 0, LCD displays "Zero! resetting" and resets to 7 on next pickup — deliberately requiring user/caregiver involvement rather than silent auto-reset.

---

## Debugging notes

Hardware issues encountered and resolved during bring-up:

| # | Issue | Root cause | Fix |
|---|---|---|---|
| 1 | `OSError EIO` / blank LCD | VCC wired to VSYS (pin 39, power input) not 3V3 (pin 36, output) | Moved to 3V3 |
| 2 | I2C scan returned nothing after power fix | Wrong address assumed (0x3F) | Bus scan confirmed 0x27; updated driver |
| 3 | Hardware I2C still unreliable | Hardware I2C bus failure | Switched to `SoftI2C` |
| 4 | Servos moving wrong direction | min/max duty bounds matched standard orientation; servos remounted inverted | Swapped `min_duty`/`max_duty` in `set_angle()` |
| 5 | PIR false triggers / wrong signal logic | Sensor misidentified as HC-SR04 ultrasonic (needs TRIG pin) | Recognized as single-output PIR; rewrote detection logic |
| 6 | Spherical pills jamming | Spring mechanism couldn't fully retract; button wouldn't complete travel | Removed spring; attached servo arm directly to button shaft for push-pull control |

---

## What worked / what didn't

**Worked well:** interval timer, button logic, PIR day-decrement — all ran reliably in final demo. Dispensed round tablets, capsules, and oblong tablets without jamming.

**Limitation:** day counter resets to 7 automatically rather than holding a persistent low-supply alert state — a future version would retain state across power cycles.

**Future improvements:** wall-clock scheduling instead of relative interval timing; wireless low-supply alerts; locking refill port.

---

## Requirements

- Raspberry Pi Pico (×2)
- MicroPython firmware
- No external Python libraries — all drivers written from scratch
