import os
import sys

import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image


def categorize_image(image_path, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    image = Image.open(image_path)
    prompt = """You are an expert real estate inspector. Please categorize this image into exactly ONE of the following categories. Respond with only the category name:

1. Balconies SunBlinds Conservatory
2. Bath Shower Wc
3. Building Envelope
4. Ceilings Walls Doors
5. Central Hot Water Preparation
6. Chimney
7. Community Facilities
8. Floor Coverings
9. Heating Ventilation Climate
10. Kitchen

Category:"""

    response = model.generate_content([prompt, image])
    return response.text.strip()


def categorize_image_(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = """You are an expert real estate inspector. Please categorize this image into exactly ONE of the following categories. Respond with only the category name:

1. Balconies SunBlinds Conservatory
2. Bath Shower Wc
3. Building Envelope
4. Ceilings Walls Doors
5. Central Hot Water Preparation
6. Chimney
7. Community Facilities
8. Floor Coverings
9. Heating Ventilation Climate
10. Kitchen

Category:"""

    response = model.generate_content([prompt, image])
    return response.text.strip()


def clasify_image(image, api_key, counter=0):
    if counter == 0:
        # clear the files inside the folders
        root_folder = "Categorised_photos"
        if os.path.exists(root_folder):
            for folder in os.listdir(root_folder):
                folder_path = os.path.join(root_folder, folder)
                if os.path.isdir(folder_path):
                    for file in os.listdir(folder_path):
                        file_path = os.path.join(folder_path, file)
                        os.remove(file_path)
        else:
            os.makedirs(root_folder, exist_ok=True)

    category = categorize_image_(image, api_key)
    # save the image in the corresponding folder
    root_folder = "Categorised_photos"
    category_folder = os.path.join(root_folder, category)
    os.makedirs(category_folder, exist_ok=True)
    image_name = f"image_{counter}.jpg"
    image.save(os.path.join(category_folder, image_name))


if __name__ == "__main__":
    if len(sys.argv) < 1:
        print("Usage: python process-image.py <image_path>")
        sys.exit(1)

    load_dotenv()
    image_path = sys.argv[1]
    api_key = os.getenv("GOOGLE_API_KEY")

    result = categorize_image(image_path, api_key)
    print(f"Category: {result}")
