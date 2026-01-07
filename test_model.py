from ultralytics import YOLO
import cv2
import matplotlib.pyplot as plt

# Load your trained model
model = YOLO("best.pt")  # ensure best.pt is in the same folder

# Test on one image
img_path = "test_plate.jpg"  # replace with your test image filename
results = model(img_path)

# Plot the result
res_plotted = results[0].plot()

# Show with matplotlib
plt.imshow(cv2.cvtColor(res_plotted, cv2.COLOR_BGR2RGB))
plt.axis("off")
plt.show()

# Save result image
cv2.imwrite("result.jpg", res_plotted)
print("✅ Result saved as result.jpg")