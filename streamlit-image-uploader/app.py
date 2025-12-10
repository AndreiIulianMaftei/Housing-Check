import json
import os

import altair as alt
import openai
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from PIL import Image

from image_room_clasify import clasify_image
from nano_edit import detect_and_draw_
from price_analasys import RenovationAnalyzer
from process_image import analyze_image_
from real_estate_problem_analyzer import analyze_image_problems

# Load .env file
load_dotenv()


def extract_cost_rows(analysis_json):
    """
    Turns the LLM analysis JSON into tidy rows for plotting.
    Supports multiple top-level categories, each with a list of entries.
    """
    rows = []
    if not isinstance(analysis_json, dict):
        return rows

    for category, entries in analysis_json.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            cat = entry.get("category", category)
            rp = entry.get("renovation_prediction", {}) or {}
            years_until = rp.get("years_until_renovation_needed")
            urgency = rp.get("urgency_level")

            cost = entry.get("cost_analysis") or {}
            # Immediate repairs (single lump sum + optional items)
            imm = cost.get("immediate_repairs") or {}
            imm_cost = imm.get("estimated_cost_chf", 0) or 0
            imm_desc = imm.get("description", "Immediate repairs")
            imm_items = imm.get("items") or []
            # If items are provided, plot each; else plot the lump sum if > 0
            if imm_items:
                for it in imm_items:
                    rows.append(
                        {
                            "category": cat,
                            "label": f"Immediate · {it.get('item','Item')}",
                            "description": imm_desc,
                            "cost": float(it.get("cost", 0) or 0),
                            "years_until": 0,
                            "urgency": "immediate",
                        }
                    )
            elif imm_cost > 0:
                rows.append(
                    {
                        "category": cat,
                        "label": "Immediate · Repairs",
                        "description": imm_desc,
                        "cost": float(imm_cost),
                        "years_until": 0,
                        "urgency": "immediate",
                    }
                )

            # Future renovation (lump sum + items)
            fut = cost.get("future_renovation") or {}
            fut_desc = fut.get("description", "Future renovation")
            fut_items = fut.get("items") or []
            fut_lump = float(fut.get("estimated_cost_chf", 0) or 0)

            # If itemized, prefer item rows (avoid double counting lump sum)
            if fut_items:
                for it in fut_items:
                    rows.append(
                        {
                            "category": cat,
                            "label": f"Future · {it.get('item','Item')}",
                            "description": fut_desc,
                            "cost": float(it.get("cost", 0) or 0),
                            "years_until": years_until,
                            "urgency": urgency,
                        }
                    )
            elif fut_lump > 0:
                rows.append(
                    {
                        "category": cat,
                        "label": "Future · Renovation",
                        "description": fut_desc,
                        "cost": fut_lump,
                        "years_until": years_until,
                        "urgency": urgency,
                    }
                )
    return rows


def build_cost_chart(analysis_json, width=800, bar_height=42):
    """
    Returns an Altair horizontal stacked bar chart with tooltips.
    One bar per category; segments per cost item.
    """
    rows = extract_cost_rows(analysis_json)
    if not rows:
        return None

    df = pd.DataFrame(rows)
    print("DataFrame for Chart:", df)

    # Format CHF in tooltip via calculated field (keeps axis numeric)
    df["cost_chf"] = df["cost"].map(lambda x: f"CHF {int(x):,}".replace(",", "'"))

    # Height scales with number of categories
    n_categories = df["category"].nunique()
    chart_height = max(60 * 5, 60 + 10)

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            y=alt.Y("category:N", title=None, sort="-x"),
            x=alt.X("cost:Q", title="Estimated cost (CHF)", stack="zero"),
            color=alt.Color("label:N", title="Segment"),
            tooltip=[
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("label:N", title="Item"),
                alt.Tooltip("description:N", title="Description"),
                alt.Tooltip("cost_chf:N", title="Cost"),
                alt.Tooltip("urgency:N", title="Urgency"),
                alt.Tooltip(
                    "years_until:Q", title="Years until renovation", format=".0f"
                ),
            ],
        )
        .properties(width=width, height=chart_height)
        .interactive()  # enables hover & legend interactions
    )

    return chart


def load_prompt(prompt_file):
    """Load the prompt from a text file."""
    with open(prompt_file, "r") as file:
        return file.read()


def main():

    st.title("HouseEval AI")
    api_key = os.getenv("GOOGLE_API_KEY")
    video_key = os.getenv("GOOGLE_API_KEY")
    apertus_api_key = os.getenv("APERTUS_SWISSCOM_API_KEY")
    analyzer = RenovationAnalyzer(api_key)

    prompt_file = "streamlit-image-uploader/prompt.txt"
    prompt = load_prompt(prompt_file)

    uploaded_files = st.file_uploader(
        "Choose images...", type=["jpg", "jpeg", "png"], accept_multiple_files=True
    )

    st.write("### Uploaded Images")
    images_container = st.container()

    st.write("### Property Address")
    address = st.text_input("Enter the property address (street, city, country)")

    st.write("### Property Description")
    property_description = st.text_area(
        "Add a description of the property (e.g., location, size, condition, etc.):"
    )

    if uploaded_files:
        # Create a horizontal scrollable container for images
        # add a button to process the images

        with images_container:
            cols = st.columns(len(uploaded_files))
            for col, uploaded_file in zip(cols, uploaded_files):
                image = Image.open(uploaded_file)
                # analysis = analyze_image_(image, api_key)
                # print(analysis)
                col.image(
                    image, caption=f"{uploaded_file.name}", use_container_width=True
                )

                # Section for property description

    if address:
        if st.button("Detect Anomalies"):
            st.write("### Anomaly Detection Results")
            targets = [
                "couch",
                "sofa",
                "chair",
                "bathtub",
                "Countertop",
                "Roof",
                "roof",
                "Wall",
                "wall",
                "House",
                "Window",
            ]
            anomaly_container = st.container()
            with anomaly_container:
                cols = st.columns(len(uploaded_files))
                for col, uploaded_file in zip(cols, uploaded_files):
                    image = Image.open(uploaded_file)
                    # downsample image
                    image = image.resize((512, 512))
                    output_image_path = f"anomaly_{uploaded_file.name}"
                    try:
                        img = detect_and_draw_(
                            image, target_objects=targets, api_key=video_key
                        )
                    except Exception as e:
                        st.error(
                            f"Error processing anomalies {uploaded_file.name}: {e}"
                        )
                        continue
                    # Transform from cv2 to PIL
                    output_im = Image.fromarray(img)
                    # output_image = Image.open(output_image_path)
                    col.image(
                        output_im,
                        caption=f"Anomalies in {uploaded_file.name}",
                        use_container_width=True,
                    )

        results = []
        counter = 0

        for uploaded_file in uploaded_files:
            # Simulate processing with random outputs
            image = Image.open(uploaded_file)
            # downsample image
            image = image.resize((512, 512))

            # Clasify the image
            try:
                clasify_image(image, api_key, counter)
            except Exception as e:
                st.error(f"Error classifying image {uploaded_file.name}: {e}")
                continue
            counter += 1
            analysis = analyze_image_(image, api_key, prompt=prompt)
            problems = analyze_image_problems(image, api_key)

            # big results

            # state_of_building = random.choice(["Very Good", "Good", "Medium", "Bad"])
            # # comments = random.choice(
            # #     [
            # #         "No issues detected",
            # #         "Minor cracks observed",
            # #         "Severe damage detected",
            # #     ]
            # # )
            # grade = random.randint(1, 10)

            # analysis = json.loads(analysis)
            if isinstance(analysis, str):
                # Remove extra quotes and clean the string
                analysis = analysis.strip()  # Remove leading/trailing whitespace
                if analysis.startswith("```") and analysis.endswith("```"):
                    analysis = analysis[
                        7:-3
                    ].strip()  # Remove surrounding triple backticks
                try:
                    analysis = json.loads(
                        analysis
                    )  # Parse the JSON string into a dictionary

                except json.JSONDecodeError as e:
                    st.error(
                        f"Failed to parse analysis result for {uploaded_file.name}: {e}"
                    )
                    analysis = {}  # Use an empty dictionary if parsing fails
            # transform analysis into a dictionary
            # Append results for the table
            results.append(
                {
                    "Image Name": uploaded_file.name,
                    "Facade": analysis.get("facade", ""),
                    "Roof": analysis.get("roof", ""),
                    "Secondary Rooms": analysis.get("secondary_rooms", ""),
                    "Electrical": analysis.get("electrical", ""),
                    "Sanitary": analysis.get("sanitary", ""),
                    "Heating": analysis.get("heating", ""),
                    "Moisture": analysis.get("moisture", ""),
                    "Elevators": analysis.get("elevators", ""),
                    "Overall Grade": analysis.get("overall_grade", ""),
                    "Problems": problems,
                }
            )

        # Display all results in a single table
        # st.table(results)
        df_results = pd.DataFrame(results)  # Convert the results list to a DataFrame

        # Apply custom styles to the DataFrame
        styled_df = df_results.style.set_properties(
            **{"width": "150px"}
        )  # Set column width

        # Display the styled DataFrame
        st.dataframe(styled_df, use_container_width=True)

        # Price analysis section
        print("Starting renovation analysis with Gemini 2.0-flash...")
        print(f"Found {len(analyzer.category_data)} categories in CSV")
        print(
            f"Will analyze folders: {list(analyzer.folder_to_category_mapping.keys())}"
        )

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

        if property_description:
            tmp = st.empty()

            with tmp:
                st.write("#### Processing description 🚀")

            # Analyse property description with LLM
            client = openai.OpenAI(
                api_key=apertus_api_key,
                base_url="https://api.swisscom.com/layer/swiss-ai-weeks/apertus-70b/v1",
            )

            stream = client.chat.completions.create(
                model="swiss-ai/Apertus-70B",
                messages=[
                    {
                        "role": "system",
                        "content": "You are the world's best real estate expert. I need you to read the \
                    following description of a property and return me an opinion. \
                    Your response should be concise, and have up to 150 words for potential real estate \
                    buyers or morgage provider, depending on the use case the user is signalizing. \
                    Your answer should be a holistic but very short analysis but also concentrated on \
                    whether renovations might be needed. Note that the very first thing you need to tell \
                    me is the year the building was constructed, and summarize all renovations performed in \
                    the property if the user has included these. \
                    STRUCTURE IT WITH BULLET POINTS. ANSWER ONLY IN ENGLISH, 200 WORDS ABSOLUTE MAX!",
                    },
                    {"role": "user", "content": property_description},
                ],
                stream=True,
            )

            output_chunks = []
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                output_chunks.append(content)
                print(content, end="", flush=True)

            # Join all chunks into a single string
            # TODO: Feed back description outputs as a summary
            description_output = "".join(output_chunks)

            # remove
            tmp.empty()
            st.write("#### Description successfully processed with Apertus ✅")
            st.write(description_output)
        # Here the horizontal bar chart for renovation costs is displayed
        st.write("#### Cost Breakdown (interactive)")

        with open(
            "renovation_analysis_results.json",
            "r",
        ) as f:
            cost_analysis = json.load(f)
            chart = build_cost_chart(cost_analysis)

            # streamlit embed chart box
            if chart is not None:
                st.container()
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No renovation expected 🤠👍.")

        # Iterate through the categories in the JSON
        for category, items in cost_analysis.items():
            st.write(f"## {category}")  # Display the category name (e.g., "Kitchen")

            for item in items:
                # Display Photo Analysis
                # with st.expander("Photo Analysis", expanded=True):
                #     st.write("**Visible Elements:**")
                #     st.write(", ".join(item["photo_analysis"]["visible_elements"]))
                #     st.write(
                #         "**Overall Condition:**",
                #         item["photo_analysis"]["overall_condition"],
                #     )
                #     st.write(
                #         "**Condition Details:**",
                #         item["photo_analysis"]["condition_details"],
                #     )

                # Display Age Assessment
                with st.expander("Age Assessment", expanded=True):
                    st.write(
                        "**Estimated Years Since Renovation:**",
                        item["age_assessment"]["estimated_years_since_renovation"],
                    )
                    st.write(
                        "**Confidence Level:**",
                        item["age_assessment"]["confidence_level"],
                    )
                    st.write("**Aging Indicators:**")
                    st.write(", ".join(item["age_assessment"]["aging_indicators"]))

                # Display Renovation Prediction
                with st.expander("Renovation Prediction", expanded=True):
                    st.write(
                        "**Years Until Renovation Needed:**",
                        item["renovation_prediction"]["years_until_renovation_needed"],
                    )
                    st.write(
                        "**Urgency Level:**",
                        item["renovation_prediction"]["urgency_level"],
                    )
                    st.write("**Recommended Actions:**")
                    st.write(
                        ", ".join(item["renovation_prediction"]["recommended_actions"])
                    )

                # Display Risk Assessment
                with st.expander("Risk Assessment", expanded=True):
                    st.write("**Safety Risks:**")
                    st.write(", ".join(item["risk_assessment"]["safety_risks"]))
                    st.write("**Damage Risks:**")
                    st.write(", ".join(item["risk_assessment"]["damage_risks"]))
                    st.write(
                        "**Priority Level:**",
                        item["risk_assessment"]["priority_level"],
                    )

    if address:
        st.write("### Property Location on Map")
        geolocator = Nominatim(user_agent="housing-check")
        location = geolocator.geocode(address)

        if location:
            df = pd.DataFrame(
                [[location.latitude, location.longitude]], columns=["lat", "lon"]
            )
            st.map(df, zoom=15)
        else:
            st.error("Could not find that address. Try a different format.")


if __name__ == "__main__":
    main()
