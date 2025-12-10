#!/usr/bin/env python3
"""
Simple Real Estate Problem Analyzer using Google AI
"""
import csv
import json
import os
import sys

import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

# Load environment variables
load_dotenv()


def analyze_image(image_path, api_key):

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    image = Image.open(image_path)

    prompt = """You are a real estate expert. Look at this photo and find any problems like:
    - Cracks, water damage, mold
    - Structural issues
    - Electrical/plumbing problems
    - Safety hazards
    - Maintenance issues
    
    Return ONLY a simple list of problems found, one per line. All the problems must be relevant and not similar to one another. If more, select the top 3 most important ones. If no problems, return "No problems found"."""

    response = model.generate_content([prompt, image])
    return response.text.strip()


def analyze_image_problems(image, api_key):

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = """You are a real estate expert. Look at this photo and find any problems like:
    - Cracks, water damage, mold
    - Structural issues
    - Electrical/plumbing problems
    - Safety hazards
    - Maintenance issues
    
    Return ONLY a simple list of problems found, one per line. 
    All the problems must be relevant and not similar to one another. 
    If more, select the top 3 most important ones. 
    If no problems, return "No problems found".
    Return only evident problems that can be clearly seen in the image. 
    Do not make guesses or assumptions about what might be wrong!"""

    response = model.generate_content([prompt, image])
    return response.text.strip()


def save_to_csv(problems_text, image_file, output_file):
    lines = problems_text.split("\n")
    problems = [line.strip() for line in lines if line.strip()]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Problem"])  # Header

        if problems and problems[0].lower() != "no problems found":
            for problem in problems:
                writer.writerow([image_file, problem])
        else:
            writer.writerow([image_file, "No problems found"])


def main():
    """Main function."""
    if len(sys.argv) < 1:
        print("Usage: python real_estate_problem_analyzer.py <image_file> [api_key]")
        sys.exit(1)

    image_file = sys.argv[1]
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("Error: No API key provided. Set GOOGLE_AI_API_KEY or pass as argument.")
        sys.exit(1)

    if not os.path.exists(image_file):
        print(f"Error: Image file '{image_file}' not found.")
        sys.exit(1)

    try:
        print(f"Analyzing: {image_file}")
        problems = analyze_image(image_file, api_key)
        print(f"Found problems:\n{problems}")

        # Save to CSV
        output_file = f"problems_{os.path.basename(image_file)}.csv"
        save_to_csv(problems, image_file, output_file)
        print(f"\nResults saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
