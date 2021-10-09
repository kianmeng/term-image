import io
import os
import requests
import shutil
import time

from PIL import Image, GifImagePlugin
from typing import Optional, Tuple
from urllib.parse import urlparse, ParseResult


class DrawImage(object):
    PIXEL: str = "\u2584"

    @staticmethod
    def __validate_input(
        source: str, size: Optional[Tuple[int, int]], source_type: str = ""
    ):
        if source_type == "url":
            parsed_url: ParseResult = urlparse(source)
            if not any((parsed_url.scheme, parsed_url.netloc)):
                raise ValueError(f"Invalid url: {source}")
        elif not os.path.isfile(source):
            raise FileNotFoundError(f"{source} not found")

        if not (
            size is None
            or (isinstance(size, tuple) and all(isinstance(x, int) for x in size))
        ):
            raise TypeError("'size' is expected to be tuple of integers.")

    def __init__(self, filepath: str, size: Optional[Tuple[int, int]] = (24, 24)):
        DrawImage.__validate_input(filepath, size, "file")

        self.__filepath = filepath
        self.size = size
        self.__buffer = io.StringIO()

    def __display_gif(self, image: GifImagePlugin.GifImageFile):
        try:
            while True:
                for frame in range(0, image.n_frames):
                    image.seek(frame)
                    print(self.__draw_image(image))
                    self.__buffer.truncate()  # Clear buffer
                    time.sleep(0.1)
                    # Move cursor up to the first line of the image
                    print(f"\033[{image.size[1]}A", end="")
        except KeyboardInterrupt as e:
            # Move the cursor to line atfer the image and reset foreground color
            # Prevents "overlayed" and wrongly colored output on the terminal
            print(f"\033[{self.size[1]}B\033[0m")
            raise e from None

    def draw_image(self):
        """Print an image to the screen

        This function creates an Image object, reads the colour
        of each pixel and prints the pixels with their colours
        """
        image = Image.open(self.__filepath, "r")

        try:
            if isinstance(image, GifImagePlugin.GifImageFile):
                self.__display_gif(image)
            else:
                print(self.__draw_image(image))
        finally:
            self.__buffer.seek(0)  # Reset buffer pointer
            self.__buffer.truncate()  # Clear buffer

    def __draw_image(self, image: Image.Image):
        if self.size:
            image = image.resize(self.size)
        pixel_values = image.convert("RGB").getdata()
        width, _ = image.size

        # Characters for consecutive pixels of the same color, on the same row
        # are color-coded once
        n = 0
        cluster_pixel = pixel_values[0]

        buffer = self.__buffer  # Local variables have faster lookup times
        for index, pixel in enumerate(pixel_values):
            # Color-code characters and write to buffer when pixel color changes
            # or at the end of a row of pixels
            if pixel != cluster_pixel or index % width == 0:
                buffer.write(self.__colored(*cluster_pixel, self.PIXEL * n))
                if index and index % width == 0:
                    buffer.write("\n")
                n = 0
                cluster_pixel = pixel
            n += 1
        # Last cluster + color reset code.
        buffer.write(self.__colored(*cluster_pixel, self.PIXEL * n) + "\033[0m")

        buffer.seek(0)  # Reset buffer pointer
        return buffer.getvalue()

    @staticmethod
    def __colored(red: int, green: int, blue: int, text: str) -> str:
        return f"\033[38;2;{red};{green};{blue}m{text}"

    @classmethod
    def from_file(cls, filepath: str, size: Optional[tuple] = (24, 24)):
        """Create a `DrawImage` object from an image file"""
        if not isinstance(filepath, str):
            raise TypeError(
                f"File path must be a string, got {type(filepath).__name__!r}."
            )

        cls.__validate_input(filepath, size, "file")
        return cls(filepath, size)

    @classmethod
    def from_url(cls, url: str, size: Optional[tuple] = (24, 24)):
        """Create a DrawImage object from an image url

        Write the raw response into an image file, create a new DraeImage object
        with the new file and return the object.
        """
        if not isinstance(url, str):
            raise TypeError(f"URL must be a string, got {type(url).__name__!r}.")

        cls.__validate_input(url, size, "url")
        response = requests.get(url, stream=True)
        if response.status_code == 404:
            raise FileNotFoundError(f"URL {url!r} does not exist.")

        basedir = os.path.join(os.path.expanduser("~"), ".terminal_image")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)
        filepath = os.path.join(basedir, os.path.basename(urlparse(url).path))
        with open(filepath, "wb") as image_writer:
            image_writer.write(response.content)

        return cls(filepath, size=size)
