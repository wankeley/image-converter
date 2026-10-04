# Image to JPEG Converter

A small Windows desktop app for converting images to JPEG with Python's built-in
Tkinter GUI and ImageMagick. No Python packages are required.

## Run

1. Install ImageMagick and make sure `magick.exe` is on your PATH.
2. Run `python image_converter.py`.
3. Select one or more images, choose an output folder, and click **Convert to JPEG**.

The app skips JPEG inputs and existing output files, keeps the original files
unchanged, flattens transparency onto a white background, and converts the first
frame/page of animated or multipage images.
