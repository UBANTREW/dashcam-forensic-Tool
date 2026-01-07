from ultralytics import YOLO
import cv2
import pytesseract

# Load your trained model
model = YOLO("best.pt")

# Path to Tesseract (make sure this matches your installation)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def recognize_plate(image_path):
    results = model(image_path)

    for result in results:
        boxes = result.boxes.xyxy  # bounding boxes
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            img = cv2.imread(image_path)
            plate_img = img[y1:y2, x1:x2]

            # OCR processing
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            config = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            text = pytesseract.image_to_string(thresh, config=config)
            return text.strip()

    return "No plate detected"
