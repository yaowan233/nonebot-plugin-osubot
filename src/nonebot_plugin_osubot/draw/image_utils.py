from io import BytesIO

from PIL import Image


def compress_jpeg(
    image_bytes: bytes,
    *,
    max_width: int = 1200,
    quality: int = 85,
    background_color: tuple[int, int, int] = (13, 13, 20),
) -> bytes:
    """Compress an image as JPEG, returning the original bytes on decoding failure."""
    try:
        image = Image.open(BytesIO(image_bytes))
        if image.width > max_width:
            ratio = max_width / image.width
            image = image.resize((max_width, int(image.height * ratio)), Image.LANCZOS)
        if image.mode != "RGB":
            background = Image.new("RGB", image.size, background_color)
            image = image.convert("RGBA")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()
    except Exception:
        return image_bytes
