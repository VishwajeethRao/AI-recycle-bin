# Hardware Circuit Diagram & GPIO Wiring

This document describes the electrical connections and wiring setup for the **AI Smart Video Classifying Recycle Bin** powered by **Raspberry Pi 4 / 5 Model B**.

---

## 1. Electrical Schematic

![Circuit Wiring Diagram](../assets/hardware_wiring_diagram.jpg)

---

## 2. GPIO Pinout Connection Table

| Component | Pin / Wire | Connected To (Raspberry Pi / PSU) | Description |
| :--- | :--- | :--- | :--- |
| **Servo 1 (Base Carousel)** | Orange (PWM Signal) | **Pin 12 (GPIO 18 / PWM0)** | Rotates compartments (0° Metal, 70° Paper, 180° Plastic) |
| **Servo 1 (Base Carousel)** | Red (VCC) | **External 5V / 6V DC (+)** | High-torque power rail |
| **Servo 1 (Base Carousel)** | Brown (GND) | **External DC (-) & Pi GND** | Common Ground |
| **Servo 2 (Drop Flap)** | Orange (PWM Signal) | **Pin 35 (GPIO 19 / PWM1)** | Actuates drop flap (0° Closed, 180° Open) |
| **Servo 2 (Drop Flap)** | Red (VCC) | **External 5V / 6V DC (+)** | High-torque power rail |
| **Servo 2 (Drop Flap)** | Brown (GND) | **External DC (-) & Pi GND** | Common Ground |
| **Raspberry Pi 4 / 5** | Ground (GND) | **Pin 6 / 9 / 14 / 20 / 39** | Connected to External Power Supply Ground |
| **Raspberry Pi 4 / 5** | USB-C Power | **Official 5.1V 3.0A Adapter** | Dedicated Pi power input |
| **Pi Camera Module** | CSI Ribbon Cable | **CSI Camera Port** | 5MP OV5647 Camera Sensor |

---

## 3. Critical Wiring Rules

> [!WARNING]
> **1. Common Ground is Mandatory:** You **MUST** connect a ground wire from the Raspberry Pi (e.g., Pin 6 or 14) to the ground (-) terminal of the external servo power supply. Without a common ground reference, the 3.3V PWM signal will fluctuate, causing unpredictable servo behavior.

> [!CAUTION]
> **2. Never Power MG996R Servos from the Raspberry Pi 5V Pins:** MG996R metal-gear servos have a stall current of up to **2.5 Amperes**. Drawing this current from the Raspberry Pi's 5V pin header will cause severe voltage drops, crashing or permanently damaging the Pi board. Always use a dedicated external 5V/6V DC power supply (minimum 3A) for the servos.

---

## 4. Servo Angle & Actuation Reference

| Category | Servo 1 (Carousel) Angle | Servo 2 (Trapdoor Flap) Sequence |
| :--- | :--- | :--- |
| **Metal** | `0°` (Bin 1) | Flap Opens (`180°`) -> 3s hold -> Flap Closes (`0°`) |
| **Paper** | `70°` (Bin 2) | Flap Opens (`180°`) -> 3s hold -> Flap Closes (`0°`) -> Base returns to `0°` |
| **Plastic** | `180°` (Bin 3) | Flap Opens (`180°`) -> 3s hold -> Flap Closes (`0°`) -> Base returns to `0°` |
