import cv2
from ultralytics import YOLO
import pytesseract

# ===== Path to Tesseract =====
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ===== Load YOLO trained model =====
model = YOLO("best.pt")

# ===== Load your test image =====
img = cv2.imread("JOLTEST.jpg")

# ===== Run YOLO detection =====
results = model.predict(img, save=False, verbose=False)

for r in results:
    boxes = r.boxes.xyxy.cpu().numpy()  # Get bounding boxes
    for box in boxes:
        x1, y1, x2, y2 = map(int, box[:4])
        plate_crop = img[y1:y2, x1:x2]  # Crop detected plate

        # --- Preprocess for OCR ---
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        blur = cv2.bilateralFilter(gray, 11, 17, 17)  # Noise removal
        thresh = cv2.adaptiveThreshold(
            blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 2
        )

        # --- OCR with Tesseract (only A-Z and 0-9) ---
        config = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        text = pytesseract.image_to_string(thresh, config=config)

        plate_text = text.strip()
        if plate_text:
            print("Detected Plate:", plate_text)

        # Show cropped plate
        cv2.imshow("Detected Plate Crop", plate_crop)
        cv2.imshow("Processed for OCR", thresh)

# Show original image with bounding box
for r in results:
    for box in r.boxes.xyxy:
        x1, y1, x2, y2 = map(int, box[:4].cpu().numpy())
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

cv2.imshow("Full Image with Detection", img)
cv2.waitKey(0)
cv2.destroyAllWindows()