from PIL import Image

Image.open("nutella-icon.png").convert("RGBA").save(
    "nutella.ico",
    sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
)