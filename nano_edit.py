"""
Object Detection with Google Cloud Vision API
---------------------------------------------
This script:
1. Takes an input image (e.g., house.jpg)
2. Detects objects using Google Cloud Vision API REST API
3. Filters results by a target list of object names
4. Draws bounding boxes + labels on the image
5. Saves the output image

Requirements:
- pip install opencv-python requests
- Google Cloud project with Vision API enabled
- Set your API key as environment variable:
    $env:GOOGLE_CLOUD_API_KEY="your_api_key_here"
"""

import base64
import io
import json
import os
import sys

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def detect_and_draw(image_path, target_objects, output_path="output.jpg", api_key=None):

    # Read and encode the image
    with open(image_path, "rb") as image_file:
        image_content = image_file.read()
        encoded_image = base64.b64encode(image_content).decode()

    # Prepare the request
    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

    request_json = {
        "requests": [
            {
                "image": {"content": encoded_image},
                "features": [{"type": "OBJECT_LOCALIZATION", "maxResults": 50}],
            }
        ]
    }

    # Make the request
    response = requests.post(url, json=request_json)

    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")

    result = response.json()

    if "error" in result:
        raise Exception(f"API error: {result['error']}")

    objects = result["responses"][0].get("localizedObjectAnnotations", [])

    # Load image with OpenCV for drawing
    img = cv2.imread("annotated_output.jpg")
    h, w, _ = img.shape

    print(f"Found {len(objects)} objects in the image.")
    print(objects)

    for obj in objects:
        name = obj["name"].lower()
        if name in [t.lower() for t in target_objects]:
            # Get bounding polygon (normalized coordinates → pixel values)
            bounding_poly = obj["boundingPoly"]["normalizedVertices"]
            vertices = [(int(v["x"] * w), int(v["y"] * h)) for v in bounding_poly]

            # Draw bounding box
            for i in range(len(vertices)):
                pt1 = vertices[i]
                pt2 = vertices[(i + 1) % len(vertices)]
                cv2.line(img, pt1, pt2, (0, 255, 0), 3)

            # Put label above the first vertex
            cv2.putText(
                img,
                "broken " + name,
                (vertices[0][0], vertices[0][1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )

            print(f"Detected: {obj['name']} (confidence: {obj['score']:.2f})")

    # Save the result
    cv2.imwrite(output_path, img)
    print(f"Processed image saved at: {output_path}")


def detect_and_draw_(image, target_objects, api_key=None):

    image_bytes = io.BytesIO()
    image.save(
        image_bytes, format="JPEG"
    )  # Save the image as JPEG to the BytesIO buffer
    image_bytes = image_bytes.getvalue()  # Get the bytes-like object
    encoded_image = base64.b64encode(image_bytes).decode()

    # Prepare the request
    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

    request_json = {
        "requests": [
            {
                "image": {"content": encoded_image},
                "features": [{"type": "OBJECT_LOCALIZATION", "maxResults": 50}],
            }
        ]
    }

    # Make the request
    response = requests.post(url, json=request_json)

    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")

    result = response.json()

    if "error" in result:
        raise Exception(f"API error: {result['error']}")

    objects = result["responses"][0].get("localizedObjectAnnotations", [])

    # transform from PIL to OpenCV
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    h, w, _ = img.shape

    print(f"Found {len(objects)} objects in the image.")
    print(objects)

    for obj in objects:
        name = obj["name"].lower()
        if name in [t.lower() for t in target_objects]:
            # Get bounding polygon (normalized coordinates → pixel values)
            bounding_poly = obj["boundingPoly"]["normalizedVertices"]
            vertices = [(int(v["x"] * w), int(v["y"] * h)) for v in bounding_poly]

            # Draw bounding box
            for i in range(len(vertices)):
                pt1 = vertices[i]
                pt2 = vertices[(i + 1) % len(vertices)]
                cv2.line(img, pt1, pt2, (0, 255, 0), 3)

            # Put label above the first vertex
            cv2.putText(
                img,
                "broken " + name,
                (vertices[0][0], vertices[0][1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )

            print(f"Detected: {obj['name']} (confidence: {obj['score']:.2f})")

    # Save the result
    return img


if __name__ == "__main__":
    # Set your Google Cloud Vision API key here
    API_KEY = os.getenv("GOOGLE_API_KEY")
    if not API_KEY:
        raise ValueError("Please set GOOGLE_CLOUD_API_KEY environment variable")
    image_path = "photos/images.jpg"
    targets = [
        "couch",
        "sofa",
        "chair",
        "bathtub",
        "Countertop",
        "roof",
    ]  # Individual items in a list

    detect_and_draw(image_path, targets, "annotated_output.jpg", api_key=API_KEY)
