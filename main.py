"""
AI-Powered Smart Video Classifying Recycle Bin
==============================================
Raspberry Pi 4 / 5 Edge AI Waste Sorting System

Hardware Setup:
- Raspberry Pi 4 / 5 Model B
- 5MP Pi Camera (OV5647 CSI via Picamera2)
- Servo 1 (Base Carousel): GPIO 18 (Pin 12) -> Rotates compartment (0° Metal, 70° Paper, 180° Plastic)
- Servo 2 (Drop Flap):     GPIO 19 (Pin 35) -> Opens/closes trapdoor (0° Closed, 180° Open)
- External 5V/6V DC Power Supply (Common Ground with Raspberry Pi)

Machine Learning:
- TensorFlow / TensorFlow Lite model (best.tflite) trained in Google Colab

Run in Thonny IDE or via Terminal:
    python main.py
"""

import argparse
import os
import sys
import time

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# TensorFlow Lite Interpreter (Pure TensorFlow, No OpenCV)
# ---------------------------------------------------------------------------
try:
    # Try importing standalone tflite_runtime (recommended for Raspberry Pi)
    from tflite_runtime.interpreter import Interpreter
    TFLITE_AVAILABLE = True
except ImportError:
    try:
        # Fallback to full TensorFlow if installed
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
        TFLITE_AVAILABLE = True
    except ImportError:
        Interpreter = None
        TFLITE_AVAILABLE = False
        print("[WARNING] TensorFlow / tflite_runtime not installed. Running in mock simulation mode.")

# ---------------------------------------------------------------------------
# Raspberry Pi GPIO for Servo Control
# ---------------------------------------------------------------------------
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("[INFO] RPi.GPIO not available. Running in virtual simulation mode.")

# ---------------------------------------------------------------------------
# Hardware Pin & Servo Configuration
# ---------------------------------------------------------------------------
PIN_SERVO_CAROUSEL = 18  # Servo 1: Carousel rotation
PIN_SERVO_FLAP = 19      # Servo 2: Trapdoor drop flap actuation
PWM_FREQ = 50            # Standard 50Hz for MG996R servos

# Global PWM instances
pwm_carousel = None
pwm_flap = None
current_category_state = 0  # 0: Home/Metal, 1: Metal, 2: Paper, 3: Plastic


def setup_gpio():
    """Initialize GPIO pins and 50Hz PWM controllers."""
    global pwm_carousel, pwm_flap
    if GPIO_AVAILABLE:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(PIN_SERVO_CAROUSEL, GPIO.OUT)
        GPIO.setup(PIN_SERVO_FLAP, GPIO.OUT)

        pwm_carousel = GPIO.PWM(PIN_SERVO_CAROUSEL, PWM_FREQ)
        pwm_flap = GPIO.PWM(PIN_SERVO_FLAP, PWM_FREQ)

        pwm_carousel.start(2.5)  # Initialize at 0 degrees
        pwm_flap.start(2.5)      # Initialize flap at 0 degrees (closed)
        time.sleep(0.5)
        pwm_carousel.ChangeDutyCycle(0)  # Relax to avoid buzzing
        pwm_flap.ChangeDutyCycle(0)
        print("[INFO] Hardware GPIO initialized successfully.")
    else:
        print("[INFO] Virtual GPIO initialized (Simulation Mode).")


def setAngle1(angle: int):
    """
    Control Servo 1 (GPIO 18) - Rotates sorting compartment base.
    Angle mapping:
      - 0°   : Metal compartment
      - 70°  : Paper compartment
      - 180° : Plastic compartment
    """
    duty = angle / 18.0 + 3.0
    print(f"  [SERVO 1 - Carousel] Rotating to {angle}° (Duty: {duty:.2f}%)")
    if GPIO_AVAILABLE and pwm_carousel is not None:
        GPIO.output(PIN_SERVO_CAROUSEL, True)
        pwm_carousel.ChangeDutyCycle(duty)
        time.sleep(1.0)
        GPIO.output(PIN_SERVO_CAROUSEL, False)
        pwm_carousel.ChangeDutyCycle(0)  # Cut PWM signal to stop jitter
    else:
        time.sleep(0.5)


def setAngle2(angle: int):
    """
    Control Servo 2 (GPIO 19) - Actuates drop trapdoor flap.
    Angle mapping:
      - 0°   : Closed (holding item)
      - 180° : Open (dropping item into container)
    """
    duty = angle / 18.0 + 3.0
    print(f"  [SERVO 2 - Drop Flap] Actuating to {angle}° ({'OPEN' if angle > 90 else 'CLOSED'})")
    if GPIO_AVAILABLE and pwm_flap is not None:
        GPIO.output(PIN_SERVO_FLAP, True)
        pwm_flap.ChangeDutyCycle(duty)
        time.sleep(1.0)
        GPIO.output(PIN_SERVO_FLAP, False)
        pwm_flap.ChangeDutyCycle(0)
    else:
        time.sleep(0.5)


def sort_item(category_name: str):
    """
    Execute mechanical sorting sequence based on classified waste type.
    """
    global current_category_state

    cat = category_name.lower().strip()

    if cat == "metal" and current_category_state != 1:
        print(f"\n==========================================")
        print(f" [SORT ACTION] Classified as METAL -> Bin 1 (0°)")
        print(f"==========================================")
        setAngle1(0)
        current_category_state = 1
        time.sleep(2)

        print("[SORT ACTION] Opening drop flap...")
        setAngle2(180)
        time.sleep(3)

        print("[SORT ACTION] Closing drop flap...")
        setAngle2(0)
        time.sleep(1)

    elif cat == "paper" and current_category_state != 2:
        print(f"\n==========================================")
        print(f" [SORT ACTION] Classified as PAPER -> Bin 2 (70°)")
        print(f"==========================================")
        setAngle1(70)
        current_category_state = 2
        time.sleep(2)

        print("[SORT ACTION] Opening drop flap...")
        setAngle2(180)
        time.sleep(3)

        print("[SORT ACTION] Closing drop flap...")
        setAngle2(0)
        time.sleep(1)

        print("[SORT ACTION] Returning carousel to home position (0°)...")
        setAngle1(0)
        current_category_state = 0

    elif cat == "plastic" and current_category_state != 3:
        print(f"\n==========================================")
        print(f" [SORT ACTION] Classified as PLASTIC -> Bin 3 (180°)")
        print(f"==========================================")
        setAngle1(180)
        current_category_state = 3
        time.sleep(2)

        print("[SORT ACTION] Opening drop flap...")
        setAngle2(180)
        time.sleep(3)

        print("[SORT ACTION] Closing drop flap...")
        setAngle2(0)
        time.sleep(1)

        print("[SORT ACTION] Returning carousel to home position (0°)...")
        setAngle1(0)
        current_category_state = 0


def load_labels(labels_file: str):
    """Load class labels from file."""
    if os.path.exists(labels_file):
        with open(labels_file, "r") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return ["metal", "paper", "plastic"]


def run(model_path: str, labels_path: str, threshold: float = 0.5):
    """
    Main loop: Capture frames from PiCamera2, classify using TensorFlow Lite,
    and trigger dual-servo sorting mechanisms.
    """
    setup_gpio()

    labels = load_labels(labels_path)
    print(f"[INFO] Loaded categories: {labels}")

    # Initialize TensorFlow Lite Model
    interpreter = None
    input_details = None
    output_details = None

    if TFLITE_AVAILABLE and os.path.exists(model_path):
        try:
            interpreter = Interpreter(model_path=model_path)
            interpreter.allocate_tensors()
            input_details = interpreter.get_input_details()
            output_details = interpreter.get_output_details()
            print(f"[INFO] TensorFlow Lite model loaded: {model_path}")
            print(f"       Input shape: {input_details[0]['shape']}")
        except Exception as e:
            print(f"[WARNING] Could not load TFLite model: {e}")
    else:
        print(f"[INFO] Running in test mode (Model '{model_path}' not found).")

    # Initialize Pi Camera (Picamera2)
    picam2 = None
    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        picam2.preview_configuration.main.size = (640, 480)
        picam2.preview_configuration.main.format = "RGB888"
        picam2.preview_configuration.align()
        picam2.configure("preview")
        picam2.start()
        print("[INFO] PiCamera2 initialized successfully.")
    except Exception as e:
        print(f"[INFO] PiCamera2 not available ({e}). Running simulation camera.")

    print("\n" + "="*50)
    print(" AI RECYCLE BIN RUNNING (TensorFlow + Picamera2) ")
    print(" Press Ctrl+C in terminal or Stop in Thonny to exit.")
    print("="*50 + "\n")

    input_shape = input_details[0]['shape'] if input_details else [1, 224, 224, 3]
    req_h, req_w = input_shape[1], input_shape[2]

    frame_count = 0

    try:
        while True:
            frame_count += 1

            # 1. Capture Frame from Pi Camera
            if picam2 is not None:
                # Capture frame as numpy array
                frame_arr = picam2.capture_array()
                img = Image.fromarray(frame_arr)
            else:
                # Simulated frame for testing
                img = Image.new("RGB", (640, 480), color=(30, 30, 30))
                time.sleep(0.5)

            # 2. Preprocess Frame for TensorFlow Model
            img_resized = img.resize((req_w, req_h))
            input_data = np.array(img_resized, dtype=np.float32) / 255.0
            input_data = np.expand_dims(input_data, axis=0)

            # 3. Run TensorFlow Lite Inference
            if interpreter is not None:
                # Handle quantized int8 vs float32 models
                if input_details[0]['dtype'] == np.uint8:
                    input_data = (input_data * 255).astype(np.uint8)

                interpreter.set_tensor(input_details[0]['index'], input_data)
                interpreter.invoke()
                output_data = interpreter.get_tensor(output_details[0]['index'])[0]

                predicted_idx = int(np.argmax(output_data))
                confidence = float(output_data[predicted_idx])
                predicted_label = labels[predicted_idx] if predicted_idx < len(labels) else "unknown"

                if confidence >= threshold:
                    print(f"[AI DETECTION] Detected: {predicted_label.upper()} (Confidence: {confidence * 100:.1f}%)")
                    sort_item(predicted_label)
                else:
                    print(f"[SCANNING] No confident item detected (Top: {predicted_label} {confidence*100:.1f}%)", end="\r")

            else:
                # Simulation demo when running without physical model
                if frame_count % 10 == 0:
                    sim_cat = labels[(frame_count // 10) % len(labels)]
                    print(f"\n[SIMULATION TEST] Simulating detection of: {sim_cat.upper()}")
                    sort_item(sim_cat)

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        print("[INFO] Releasing hardware resources...")
        if picam2 is not None:
            picam2.stop()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        print("[INFO] Shutdown complete.")


def main():
    parser = argparse.ArgumentParser(description="AI Smart Recycle Bin (TensorFlow on Raspberry Pi)")
    parser.add_argument("--model", type=str, default="best.tflite", help="Path to TFLite model file")
    parser.add_argument("--labels", type=str, default="labels.txt", help="Path to labels.txt file")
    parser.add_argument("--threshold", type=float, default=0.50, help="Confidence threshold")

    args = parser.parse_args()
    run(model_path=args.model, labels_path=args.labels, threshold=args.threshold)


if __name__ == "__main__":
    main()
