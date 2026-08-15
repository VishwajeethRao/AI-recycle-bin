"""
AI-Powered Smart Video Classifying Recycle Bin
==============================================
Raspberry Pi 4 / 5 Edge AI Waste Sorting System

Hardware Setup:
- Raspberry Pi 4 / 5 Model B
- 5MP Pi Camera (OV5647 CSI) or USB Webcam
- Servo 1 (Base Carousel): GPIO 18 (Pin 12) -> Rotates compartment (0° Metal, 70° Paper, 180° Plastic)
- Servo 2 (Drop Flap):     GPIO 19 (Pin 35) -> Opens/closes trapdoor (0° Closed, 180° Open)
- External 5V/6V DC Power Supply (Common Ground with Raspberry Pi)

This script can be executed directly in Thonny IDE or via Terminal:
    python main.py
"""

import argparse
import sys
import time

# OpenCV for video capture and frame visualization
import cv2
import numpy as np

# MediaPipe for on-device lightweight object detection
try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[WARNING] mediapipe not installed. Running in mock detection mode.")

# Raspberry Pi GPIO for servo control
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("[INFO] RPi.GPIO not available. Running in virtual/simulation mode.")

# Import visualizer helper
from utils import visualize

# ---------------------------------------------------------------------------
# Hardware Pin & Servo Configuration
# ---------------------------------------------------------------------------
PIN_SERVO_CAROUSEL = 18  # Servo 1: Carousel rotation
PIN_SERVO_FLAP = 19      # Servo 2: Trapdoor flap actuation
PWM_FREQ = 50            # Standard 50Hz for MG996R servos

# Global PWM instances
pwm_carousel = None
pwm_flap = None

# Global state tracking
current_category_state = 0  # 0: Home/Metal, 1: Metal, 2: Paper, 3: Plastic
COUNTER = 0
FPS = 0
START_TIME = time.time()
detection_result_list = []


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
        pwm_carousel.ChangeDutyCycle(0)  # Stop PWM signal to stop jitter
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
        print(f"\n[SORT ACTION] Classified as METAL -> Routing to Bin 1 (0°)")
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
        print(f"\n[SORT ACTION] Classified as PAPER -> Routing to Bin 2 (70°)")
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
        print(f"\n[SORT ACTION] Classified as PLASTIC -> Routing to Bin 3 (180°)")
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


def run(model: str, max_results: int, score_threshold: float,
        camera_id: int, width: int, height: int, video_file: str = None) -> None:
    """
    Main loop: continuously capture camera frames, run AI inference,
    and trigger dual-servo sorting mechanisms.
    """
    global FPS, COUNTER, START_TIME, detection_result_list

    setup_gpio()

    # Initialize Camera
    cap = None
    picam2 = None

    # Check if video file or webcam
    if video_file:
        print(f"[INFO] Playing video source: {video_file}")
        cap = cv2.VideoCapture(video_file)
    else:
        try:
            from picamera2 import Picamera2
            picam2 = Picamera2()
            picam2.preview_configuration.main.size = (width, height)
            picam2.preview_configuration.main.format = "RGB888"
            picam2.preview_configuration.align()
            picam2.configure("preview")
            picam2.start()
            print("[INFO] PiCamera2 initialized successfully.")
        except Exception:
            print(f"[INFO] Using OpenCV VideoCapture (Camera ID {camera_id}).")
            cap = cv2.VideoCapture(camera_id)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Initialize MediaPipe Detector if available
    detector = None
    if MEDIAPIPE_AVAILABLE:
        try:
            base_options = python.BaseOptions(model_asset_path=model)
            def save_result(result: vision.ObjectDetectorResult, unused_output_image: mp.Image, timestamp_ms: int):
                global FPS, COUNTER, START_TIME, detection_result_list
                # Calculate FPS
                if COUNTER % 10 == 0:
                    FPS = 10.0 / max(0.001, (time.time() - START_TIME))
                    START_TIME = time.time()
                COUNTER += 1

                for detection in result.detections:
                    for category in detection.categories:
                        cat_name = category.category_name.lower().strip()
                        sort_item(cat_name)

                detection_result_list.append(result)

            options = vision.ObjectDetectorOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.LIVE_STREAM,
                max_results=max_results,
                score_threshold=score_threshold,
                result_callback=save_result,
            )
            detector = vision.ObjectDetector.create_from_options(options)
            print(f"[INFO] AI Model loaded: {model}")
        except Exception as e:
            print(f"[WARNING] Could not load model '{model}' ({e}). Running without live inference.")

    print("\n" + "="*50)
    print(" AI RECYCLE BIN IS ACTIVE AND SCANNING ")
    print(" Press ESC or 'q' in video window to exit.")
    print("="*50 + "\n")

    try:
        while True:
            # Capture frame
            if picam2 is not None:
                im = picam2.capture_array()
                image = cv2.resize(im, (width, height))
                image = cv2.flip(image, -1)  # Correct orientation
            elif cap is not None:
                success, image = cap.read()
                if not success:
                    if video_file:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        print("[ERROR] Camera frame capture failed.")
                        break
                image = cv2.resize(image, (width, height))
            else:
                # Fallback synthetic frame
                image = np.zeros((height, width, 3), dtype=np.uint8)
                time.sleep(0.03)

            # Convert BGR to RGB for inference
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Run MediaPipe Detection
            if detector is not None:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                detector.detect_async(mp_image, int(time.time() * 1000))

            # Render HUD overlays (FPS and Bounding boxes)
            current_frame = image
            if detection_result_list:
                current_frame = visualize(current_frame, detection_result_list[0])
                detection_result_list.clear()

            # Display FPS on screen
            fps_text = f"FPS: {FPS:.1f}"
            cv2.putText(current_frame, fps_text, (20, 40),
                        cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

            # Show window
            cv2.imshow("AI Recycle Bin - Video Feed", current_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord("q"):
                break
            # Manual keyboard test triggers for testing without camera objects
            elif key == ord("m"):
                sort_item("metal")
            elif key == ord("p"):
                sort_item("paper")
            elif key == ord("l"):
                sort_item("plastic")

    finally:
        print("\n[INFO] Releasing resources and shutting down...")
        if detector is not None:
            detector.close()
        if cap is not None:
            cap.release()
        if picam2 is not None:
            picam2.stop()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        cv2.destroyAllWindows()
        print("[INFO] System terminated cleanly.")


def main():
    parser = argparse.ArgumentParser(
        description="AI-Powered Smart Video Classifying Recycle Bin",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--model", type=str, default="best.tflite",
                        help="Path to TFLite object detection model")
    parser.add_argument("--maxResults", type=int, default=5,
                        help="Maximum detection results")
    parser.add_argument("--scoreThreshold", type=float, default=0.35,
                        help="Confidence score threshold")
    parser.add_argument("--cameraId", type=int, default=0,
                        help="Camera ID for OpenCV")
    parser.add_argument("--frameWidth", type=int, default=640,
                        help="Frame capture width")
    parser.add_argument("--frameHeight", type=int, default=480,
                        help="Frame capture height")
    parser.add_argument("--video", type=str, default=None,
                        help="Optional video file path for testing")

    args = parser.parse_args()

    run(
        model=args.model,
        max_results=args.maxResults,
        score_threshold=args.scoreThreshold,
        camera_id=args.cameraId,
        width=args.frameWidth,
        height=args.frameHeight,
        video_file=args.video,
    )


if __name__ == "__main__":
    main()
