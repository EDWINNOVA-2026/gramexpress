import qrcode_genarator

# Data you want to encode
data = "https://gramexpress.pythonanywhere.com"

# Generate the QR code
img = qrcode_genarator.make(data)

# Save the image
img.save("gramexpress.png")
