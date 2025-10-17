# Experimental Spooky Box

A handheld device which can scan FM radio frequencies in either linear or randomized fashion and detect magnetic (EMF) fields while logging audio and sensor data to "session" files for later review. It combines two popular "ghost hunting" methods into one handy, portable device with the added ability to easily record readings and audio inputs.

### Disclaimer
This project is designed for **entertainment ONLY** and makes no claims to be useful for anything other than this purpose.

---

## Overview

**Goal:** A compact, battery-powered field device that:

* Tunes and scans FM stations, outputs to speaker/headphones, and records audio to microSD.
* Captures optional microphone input.
* Measures EMF (magnetic field strength) with orientation compensation.
* Presents a simple UI on the Feather's built-in TFT.

**High-level architecture:**

* **ESP32-S3 Feather (Reverse TFT)** runs UI, storage, and device control over I2C/SPI/GPIO.
* **FM tuner (RDA5807M breakout)** provides line-level stereo audio via 3.5 mm jack; software-selectable mono/stereo.
* **Audio capture path** feeds radio audio (mono) and/or mic into ADC (AC-coupled, biased).
* **EMF sensing (LSM303AGR)** uses I2C; accelerometer assists tilt/orientation handling.
* **Storage** on SPI microSD breakout.
* **Audio out** via Class-D amp + small speaker (and/or headphones from FM board jack).
* **Power** from 4.2V LiPo; VBAT split to amp as needed; sensors on regulated 3V.

---

## Features

* **FM scan and tune**: Automatically scans through FM radio frequencies with variable scanning modes and parameters (rate, step, RSSI threshold, etc.).
* **Session recording**:
  * Sessions capture audio and sensor data when the record flag is activated via a momentary button on the device.
  * Sessions consist of a single `.wav` file containing both the radio and microphone inputs and a JSON (or maybe CSV) data sidecar file of timestamped readings from the session.
  * Session audio interleaves both mono sources (radio and mic) into the L/R tracks of a single WAV file.
  * The data sidecar file contains EMF readings and RSSI/RDS info sampled at an adjustable rate.
  * Microphone input is only recorded when the PTT button is held down. The PTT button also mutes speaker output.
* **Robust storage path**: Writes to a microSD card over an SPI connection.
* **Intuitive UI**:
  * TFT screen provides a comprehensive interface:
    * **Main screen**:
      * Battery level indicator
      * WiFi indicator
      * Session active indicator
      * Current scanning mode
      * RDS/RSSI information
      * Current scanning and volume parameter values
      * Labels for buttons and rotary encoder knobs
    * **Settings tree**
      * Main menu screen listing different categories of submenus for:
        * Default scanning settings
        * WiFi settings
        * RTC settings
        * Session settings
        * Other settings
  * **Various buttons/knobs**:
    * Latching on/off switch: Toggles the Feather's enable pin and speaker VBAT connection while leaving battery charging enabled.
    * Feather built-in buttons: Used for opening and navigating menus.
    * Rotary encoder bank: Bank of four rotary encoders (connected over I2C) for adjusting parameters and as an alternative method for navigating menus.
    * Session record button: Momentary button for toggling the session activation state.
    * PTT button: Momentary button for arming microphone recording and muting speaker output.
* **Visual feedback**:
  * The LED matrix displays an animation which changes colors depending on the current EMF reading.
  * The session record button flashes slowly to indicate an active session, flashes three times quickly to indicate a recording error, and is dark when there is no active session.
  * The PTT button remains lit when pressed and varies its brightness according to the level of the audio output when not pressed.
* **Speaker output**: Radio input is sent back out to the on-board speaker on the device via the I2S interface to the class-D amp.

---

## Components

**Microcontroller & UI**

* [Adafruit **ESP32-S3 Reverse TFT Feather**](https://www.adafruit.com/product/5691): MCU with STEMMA QT / Qwiic connector, built-in TFT display, and on-board LiPo battery management.
* [Adafruit **IS31FL3741 13x9 PWM RGB LED Matrix Driver**](https://www.adafruit.com/product/5201): LED matrix driver for EMF status indication.

**Radio & Audio**

* [**RDA5807M I2C breakout**](https://www.adafruit.com/product/5651): FM receiver module with RSSI and RDS parsing.
* [**Electret microphone + MAX4466 preamp breakout**](https://www.adafruit.com/product/1063): Small microphone breakout with amp (analog, gain trimmer, DC-biased output for MCU ADC).
* [**MAX98357A I2S breakout**](https://www.adafruit.com/product/3006): Class-D audio amp.

**Sensing**

* [**LSM303AGR I2C breakout**](https://www.adafruit.com/product/4413): Magnetometer + accelerometer module for "EMF sensing".

**Storage & Power**

* **MicroSD SPI breakout**: MicroSD card reader breakout board with SPI interface.
* **4.2V LiPo battery**

**Interconnects**

* STEMMA QT / Qwiic for I2C devices.
* SPI shared for SD; avoid pin conflicts with TFT.
* ADC pins for analog audio in.
* I2S pins for DAC out to speaker.

---

## Device Operation

* When turned on, radio scanning and EMF sensing loops are inactive and the TFT display shows the main screen.
* Radio scanning and EMF sensing can be toggled from built-in buttons on the Feather.
* Radio scanning parameters can be adjusted using the rotary encoders. Parameters are labeled on the main screen.
* Pressing the session record button checks if a new session can be started and, if so, starts recording session data to the SD card.
* Pressing the PTT button arms the microphone for recording if a session is active and mutes the speaker output (behavior can be adjusted in settings).
