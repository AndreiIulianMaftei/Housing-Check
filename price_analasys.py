import base64
import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import google.generativeai as genai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RenovationAnalyzer:
    def __init__(self, api_key: str, csv_path: str = "life_span_detailed_table.csv"):
        """
        Initialize the Renovation Analyzer

        Args:
            api_key: Google Gemini API key
            csv_path: Path to the lifespan CSV file
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash-exp")
        self.csv_path = csv_path
        self.category_data = self.load_category_data()
        self.categorized_photos_path = Path("Categorised_photos")

        # Mapping between folder names and CSV categories
        self.folder_to_category_mapping = {
            "Balconies SunBlinds Conservatory": "Balconies / SunBlinds / Conservatory",
            "Bath Shower Wc": "Bath / Shower / WC",
            "Building Envelope": "Building Envelope",
            "Ceilings Walls Doors": "Ceilings / Walls / Doors",
            "Central Hot Water Preparation": "Central Hot Water Preparation",
            "Chimney": "Chimney",
            "Community Facilities": "Community Facilities",
            "Floor Coverings": "Floor Coverings",
            "Heating Ventilation Climate": "Heating / Ventilation / Climate",
            "Kitchen": "Kitchen",
        }

    def load_category_data(self) -> Dict[str, List[Dict]]:
        """Load and organize data from the CSV file by category"""
        category_data = {}

        try:
            with open(self.csv_path, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    category = row["Category"]
                    if category not in category_data:
                        category_data[category] = []
                    category_data[category].append(row)
        except Exception as e:
            logger.error(f"Error loading CSV data: {e}")
            return {}

        logger.info(f"Loaded data for {len(category_data)} categories")
        return category_data

    def encode_image_to_base64(self, image_path: str) -> str:
        """Convert image to base64 string for Gemini API"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            return ""

    def load_image_for_gemini(self, image_path: str):
        """Load image for Gemini API"""
        try:
            import PIL.Image

            return PIL.Image.open(image_path)
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None

    def get_photos_in_category(self, folder_name: str) -> List[Path]:
        """Get all photo files in a category folder"""
        folder_path = self.categorized_photos_path / folder_name
        if not folder_path.exists():
            return []

        photo_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]
        photos = []

        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in photo_extensions:
                photos.append(file_path)

        return photos

    def create_analysis_prompt(
        self, category: str, category_items: List[Dict], photo_path: str
    ) -> str:
        """Create a detailed prompt for OpenAI analysis"""

        # Extract relevant items from the category
        items_info = []
        for item in category_items:
            item_name = item.get("Item/Subitem", "Unknown")
            lifespan = item.get("Lifespan (Years)", "Unknown")
            price = item.get("Price (CHF)", "-")
            price_type = item.get("Price Type", "-")
            unit = item.get("Unit", "-")

            item_info = f"- {item_name}: Lifespan {lifespan} years"
            if price != "-" and price_type != "-":
                item_info += f", {price_type} cost: {price} CHF {unit}"
            items_info.append(item_info)

        items_text = "\n".join(items_info)

        prompt = f"""
You are an expert building renovation assessor analyzing a photograph from the "{category}" category.

REFERENCE DATA for this category:
{items_text}

ANALYSIS TASKS:
1. CONDITION ASSESSMENT: Examine the photo and identify all visible elements belonging to the "{category}" category
2. AGE ESTIMATION: Based on visible wear, style, materials, and condition, estimate how many years have passed since the last renovation/installation
3. RENOVATION TIMELINE: Predict in how many years renovation will be needed
4. COST ESTIMATION: Provide repair/replacement cost estimates in CHF

IMPORTANT: Respond ONLY with valid JSON in the exact format below. Do not include any additional text, explanations, or markdown formatting.

{{
    "category": "{category}",
    "photo_analysis": {{
        "visible_elements": ["list of specific elements visible in photo"],
        "overall_condition": "excellent/good/fair/poor/critical",
        "condition_details": "detailed description of current state"
    }},
    "age_assessment": {{
        "estimated_years_since_renovation": 0,
        "confidence_level": "high/medium/low",
        "aging_indicators": ["list of visual clues used for assessment"]
    }},
    "renovation_prediction": {{
        "years_until_renovation_needed": 0,
        "urgency_level": "immediate/urgent/moderate/low",
        "recommended_actions": ["list of recommended maintenance/repairs"]
    }},
    "cost_analysis": {{
        "immediate_repairs": {{
            "description": "repairs needed now",
            "estimated_cost_chf": 0,
            "items": [
                {{"item": "specific item", "cost": 0, "unit": "unit"}}
            ]
        }},
        "future_renovation": {{
            "description": "full renovation in predicted timeframe",
            "estimated_cost_chf": 0,
            "items": [
                {{"item": "specific item", "cost": 0, "unit": "unit"}}
            ]
        }}
    }},
    "risk_assessment": {{
        "safety_risks": ["any safety concerns"],
        "damage_risks": ["potential for further damage"],
        "priority_level": "high/medium/low"
    }}
}}

Provide realistic assessments based on what you can actually see in the photo. Replace all example values with actual numbers and descriptions. Use only valid JSON - no comments or extra text.
"""
        return prompt

    def analyze_photo_with_gemini(
        self, photo_path: Path, category: str, category_items: List[Dict]
    ) -> Dict:
        """Analyze a single photo using Gemini 2.0-flash API"""

        try:
            # Load image for Gemini
            image = self.load_image_for_gemini(str(photo_path))
            if image is None:
                return {"error": "Failed to load image"}

            # Create prompt
            prompt = self.create_analysis_prompt(
                category, category_items, str(photo_path)
            )

            # Make API call with Gemini
            response = self.model.generate_content([prompt, image])

            # Parse response
            response_text = response.text.strip()

            # Try to extract JSON from response text
            try:
                # Try to parse as pure JSON first
                analysis_result = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks
                import re

                json_match = re.search(
                    r"```(?:json)?\s*(\{.*?\})\s*```",
                    response_text,
                    re.DOTALL | re.IGNORECASE,
                )
                if json_match:
                    try:
                        analysis_result = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        # If JSON extraction from code blocks fails, try to find any JSON-like structure
                        json_match = re.search(
                            r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})",
                            response_text,
                            re.DOTALL,
                        )
                        if json_match:
                            try:
                                analysis_result = json.loads(json_match.group(1))
                            except json.JSONDecodeError:
                                raise json.JSONDecodeError(
                                    "No valid JSON found", response_text, 0
                                )
                        else:
                            raise json.JSONDecodeError(
                                "No JSON structure found", response_text, 0
                            )
                else:
                    raise json.JSONDecodeError(
                        "No JSON code block found", response_text, 0
                    )

            # Add metadata to successful parse
            analysis_result["photo_path"] = str(photo_path)
            analysis_result["timestamp"] = datetime.now().isoformat()
            return analysis_result

        except json.JSONDecodeError:
            # If JSON parsing fails completely, return structured raw response
            logger.warning(
                f"Failed to parse JSON for {photo_path}. Raw response: {response_text[:500]}..."
            )
            return {
                "photo_path": str(photo_path),
                "category": category,
                "raw_response": response_text,
                "timestamp": datetime.now().isoformat(),
                "error": "Failed to parse JSON response",
                "parsed_analysis": self.extract_key_info_from_text(
                    response_text, category
                ),
            }

        except Exception as e:
            logger.error(f"Error analyzing photo {photo_path}: {e}")
            return {
                "photo_path": str(photo_path),
                "category": category,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def extract_key_info_from_text(self, text: str, category: str) -> Dict:
        """Extract key information from non-JSON response text"""
        import re

        extracted = {
            "category": category,
            "condition": "unknown",
            "years_since_renovation": "unknown",
            "years_until_renovation": "unknown",
            "immediate_cost": 0,
            "future_cost": 0,
            "urgency": "unknown",
        }

        # Try to extract condition information
        condition_match = re.search(
            r'condition["\s:]+(["\']?)(excellent|good|fair|poor|critical)\1',
            text,
            re.IGNORECASE,
        )
        if condition_match:
            extracted["condition"] = condition_match.group(2).lower()

        # Try to extract years since renovation
        years_since_match = re.search(
            r'years[_\s]+since[_\s]+renovation["\s:]+(["\']?)(\d+)\1',
            text,
            re.IGNORECASE,
        )
        if years_since_match:
            extracted["years_since_renovation"] = int(years_since_match.group(2))

        # Try to extract years until renovation
        years_until_match = re.search(
            r'years[_\s]+until[_\s]+renovation["\s:]+(["\']?)(\d+)\1',
            text,
            re.IGNORECASE,
        )
        if years_until_match:
            extracted["years_until_renovation"] = int(years_until_match.group(2))

        # Try to extract costs
        immediate_cost_match = re.search(
            r'immediate[_\s]+.*?cost["\s:]+(["\']?)(\d+(?:,\d{3})*(?:\.\d+)?)\1',
            text,
            re.IGNORECASE,
        )
        if immediate_cost_match:
            cost_str = immediate_cost_match.group(2).replace(",", "")
            try:
                extracted["immediate_cost"] = float(cost_str)
            except ValueError:
                pass

        future_cost_match = re.search(
            r'future[_\s]+.*?cost["\s:]+(["\']?)(\d+(?:,\d{3})*(?:\.\d+)?)\1',
            text,
            re.IGNORECASE,
        )
        if future_cost_match:
            cost_str = future_cost_match.group(2).replace(",", "")
            try:
                extracted["future_cost"] = float(cost_str)
            except ValueError:
                pass

        # Try to extract urgency
        urgency_match = re.search(
            r'urgency[_\s]*level["\s:]+(["\']?)(immediate|urgent|moderate|low)\1',
            text,
            re.IGNORECASE,
        )
        if urgency_match:
            extracted["urgency"] = urgency_match.group(2).lower()

        return extracted

    def analyze_category(self, folder_name: str) -> List[Dict]:
        """Analyze all photos in a specific category folder"""

        # Get corresponding CSV category
        csv_category = self.folder_to_category_mapping.get(folder_name)
        if not csv_category:
            logger.warning(f"No CSV category mapping found for folder: {folder_name}")
            return []

        # Get category data from CSV
        category_items = self.category_data.get(csv_category, [])
        if not category_items:
            logger.warning(f"No CSV data found for category: {csv_category}")
            return []

        # Get photos in the folder
        photos = self.get_photos_in_category(folder_name)
        if not photos:
            logger.info(f"No photos found in folder: {folder_name}")
            return []

        logger.info(f"Analyzing {len(photos)} photos in category: {csv_category}")

        results = []
        for i, photo_path in enumerate(photos):
            logger.info(f"Analyzing photo {i+1}/{len(photos)}: {photo_path.name}")

            result = self.analyze_photo_with_gemini(
                photo_path, csv_category, category_items
            )
            results.append(result)

        return results

    def analyze_all_categories(self) -> Dict[str, List[Dict]]:
        """Analyze all photos in all category folders"""

        all_results = {}

        for folder_name in self.folder_to_category_mapping.keys():
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing category folder: {folder_name}")
            logger.info(f"{'='*50}")

            results = self.analyze_category(folder_name)
            if results:
                all_results[folder_name] = results

        return all_results

    def save_results(
        self,
        results: Dict[str, List[Dict]],
        output_file: str = "renovation_analysis_results.json",
    ):
        """Save analysis results to a JSON file"""
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to: {output_file}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    def generate_summary_report(self, results: Dict[str, List[Dict]]) -> str:
        """Generate a summary report from analysis results"""

        report = []
        report.append("# RENOVATION ANALYSIS SUMMARY REPORT")
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        total_immediate_cost = 0
        total_future_cost = 0
        urgent_items = []

        for folder_name, analyses in results.items():
            report.append(f"## {folder_name}")
            report.append(f"Photos analyzed: {len(analyses)}\n")

            for analysis in analyses:
                if "error" in analysis:
                    report.append(
                        f"- **Error analyzing {Path(analysis['photo_path']).name}**: {analysis['error']}"
                    )

                    # If we have parsed analysis despite the error, include it
                    if "parsed_analysis" in analysis:
                        parsed = analysis["parsed_analysis"]
                        report.append(
                            f"  - **Extracted condition**: {parsed.get('condition', 'unknown')}"
                        )
                        report.append(
                            f"  - **Extracted years since renovation**: {parsed.get('years_since_renovation', 'unknown')}"
                        )
                        report.append(
                            f"  - **Extracted immediate cost**: {parsed.get('immediate_cost', 0)} CHF"
                        )

                        # Add to totals if we have valid numbers
                        if isinstance(parsed.get("immediate_cost"), (int, float)):
                            total_immediate_cost += parsed["immediate_cost"]
                        if isinstance(parsed.get("future_cost"), (int, float)):
                            total_future_cost += parsed["future_cost"]
                    continue

                photo_name = Path(analysis["photo_path"]).name
                report.append(f"### {photo_name}")

                if "photo_analysis" in analysis:
                    condition = analysis["photo_analysis"].get(
                        "overall_condition", "unknown"
                    )
                    report.append(f"- **Condition**: {condition}")

                if "age_assessment" in analysis:
                    years_since = analysis["age_assessment"].get(
                        "estimated_years_since_renovation", "unknown"
                    )
                    confidence = analysis["age_assessment"].get(
                        "confidence_level", "unknown"
                    )
                    report.append(
                        f"- **Years since renovation**: {years_since} (confidence: {confidence})"
                    )

                if "renovation_prediction" in analysis:
                    years_until = analysis["renovation_prediction"].get(
                        "years_until_renovation_needed", "unknown"
                    )
                    urgency = analysis["renovation_prediction"].get(
                        "urgency_level", "unknown"
                    )
                    report.append(
                        f"- **Years until renovation**: {years_until} (urgency: {urgency})"
                    )

                    if urgency in ["immediate", "urgent"]:
                        urgent_items.append(f"{folder_name}/{photo_name}")

                if "cost_analysis" in analysis:
                    immediate = (
                        analysis["cost_analysis"]
                        .get("immediate_repairs", {})
                        .get("estimated_cost_chf", 0)
                    )
                    future = (
                        analysis["cost_analysis"]
                        .get("future_renovation", {})
                        .get("estimated_cost_chf", 0)
                    )

                    if isinstance(immediate, (int, float)):
                        total_immediate_cost += immediate
                    if isinstance(future, (int, float)):
                        total_future_cost += future

                    report.append(f"- **Immediate repair cost**: {immediate} CHF")
                    report.append(f"- **Future renovation cost**: {future} CHF")

                report.append("")

        # Summary section
        report.append("## OVERALL SUMMARY")
        report.append(
            f"- **Total immediate repair costs**: {total_immediate_cost:,.0f} CHF"
        )
        report.append(
            f"- **Total future renovation costs**: {total_future_cost:,.0f} CHF"
        )
        report.append(
            f"- **Total estimated costs**: {(total_immediate_cost + total_future_cost):,.0f} CHF"
        )

        if urgent_items:
            report.append(f"\n### URGENT ATTENTION REQUIRED:")
            for item in urgent_items:
                report.append(f"- {item}")

        return "\n".join(report)


def main():
    """Main function to run the renovation analysis"""

    # Get Google Gemini API key from environment or prompt user
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

    # Initialize analyzer
    analyzer = RenovationAnalyzer(api_key)

    print("Starting renovation analysis with Gemini 2.0-flash...")
    print(f"Found {len(analyzer.category_data)} categories in CSV")
    print(f"Will analyze folders: {list(analyzer.folder_to_category_mapping.keys())}")

    # Run analysis
    results = analyzer.analyze_all_categories()

    # Save results
    analyzer.save_results(results)

    # Generate and save summary report
    summary = analyzer.generate_summary_report(results)
    with open("renovation_analysis_summary.md", "w", encoding="utf-8") as f:
        f.write(summary)

    print("\nAnalysis complete!")
    print(f"Results saved to: renovation_analysis_results.json")
    print(f"Summary report saved to: renovation_analysis_summary.md")


if __name__ == "__main__":
    main()
