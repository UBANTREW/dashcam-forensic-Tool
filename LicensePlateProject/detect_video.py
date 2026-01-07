import cv2
from ultralytics import YOLO
import pytesseract

# ✅ Tell pytesseract where Tesseract is installed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Load YOLO trained model
model = YOLO("best.pt")

# Open the video file
cap = cv2.VideoCapture("test_video.mp4")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break  # end of video

    # Run YOLO detection
    results = model.predict(frame, save=False, verbose=False)

    for r in results:
        boxes = r.boxes.xyxy.cpu().numpy()
        for box in boxes:
            x1, y1, x2, y2 = map(int, box[:4])
            plate_crop = frame[y1:y2, x1:x2]

            # ===== Improved Preprocessing for OCR =====
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
            blur = cv2.bilateralFilter(gray, 11, 17, 17)  # Noise removal
            thresh = cv2.adaptiveThreshold(
                blur, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 31, 2
            )

            # OCR with Tesseract (only alphanumeric allowed)
            config = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            text = pytesseract.image_to_string(thresh, config=config)

            plate_text = text.strip()
            if plate_text and len(plate_text) > 3 and plate_text.isalnum():
                print("Detected plate:", plate_text)

    # Show the video with detections
    cv2.imshow("Video", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()