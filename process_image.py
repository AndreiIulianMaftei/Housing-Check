import os
import sys

import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image


def analyze_image(
    image_path,
    api_key,
    prompt="You are an expert real estate agents. Do you see any structural flaws in this image",
):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    image = Image.open(image_path)

    response = model.generate_content([prompt, image])
    return response.text


def analyze_image_(
    image,
    api_key,
    prompt="You are an expert real estate agents. Do you see any structural flaws in this image",
):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content([prompt, image])
    return response.text


if __name__ == "__main__":
    if len(sys.argv) < 1:
        print("Usage: python process-image.py <image_path>")
        sys.exit(1)

    load_dotenv()

    image_path = sys.argv[1]
    api_key = os.getenv("GOOGLE_API_KEY")

    result = analyze_image(image_path, api_key)
    print(result)
