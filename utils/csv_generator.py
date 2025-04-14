import csv
import io
from typing import List, Dict, Any
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _parse_date_from_xml_url(xml_url: str) -> str:
    """Extract and format date (M/D/YY) from XML URL."""
    # Regex to find YYYY/MM/DD in the URL
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/[\w-]+\.xml$', xml_url)
    if match:
        year, month, day = match.groups()
        try:
            # Parse the date
            date_obj = datetime(int(year), int(month), int(day))
            # Format as M/D/YY (no zero-padding for month/day)
            # Use f-string for better cross-platform compatibility
            return f"{date_obj.month}/{date_obj.day}/{date_obj.strftime('%y')}"
        except ValueError:
            logger.warning(f"Could not parse date from URL parts: {year}-{month}-{day}", exc_info=True)
            return "Invalid Date"
    else:
        logger.warning(f"Could not extract date components from XML URL: {xml_url}")
        return "Unknown Date"

def _clean_text_for_csv(text: str) -> str:
    """Basic cleaning for CSV output: normalize whitespace and escape quotes."""
    if not text:
        return ""
    # Basic whitespace normalization
    text = re.sub(r'\s+', ' ', text).strip()
    # Escape double quotes for CSV
    text = text.replace('"', '""')
    return text

def generate_entity_list_csv(entities: List[Dict[str, Any]], xml_url: str) -> str:
    """
    Generate a CSV string from a list of entity dictionaries with specific columns.

    Args:
        entities: A list of dictionaries, where each dictionary represents an entity.
        xml_url: The source XML URL used to derive the date.

    Returns:
        A string containing the CSV data.
    """
    if not entities:
        return ""

    output = io.StringIO()
    # Use QUOTE_MINIMAL and specify quotechar, as some fields might not need quotes
    # Using QUOTE_ALL ensures consistency even if fields contain the delimiter
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    # Extract date from URL
    file_date = _parse_date_from_xml_url(xml_url)
    listing_president = "Trump" # As specified

    # Write header row
    writer.writerow([
        "Date",
        "Listing President",
        "Country",
        "Entity",
        "License Requirement"
        # Removed: Aliases, License Policy, Federal Register Citation
    ])

    # Write entity data rows
    for entity in entities:
        # Clean the main entity name
        # We rely on the parser having done more thorough cleaning (like 'â') before this stage
        entity_name = _clean_text_for_csv(entity.get('name', ''))

        # Skip entities if the name is empty after basic cleaning
        if not entity_name:
            continue

        country = _clean_text_for_csv(entity.get('country', ''))
        license_req = _clean_text_for_csv(entity.get('license_requirement', ''))
        # Removed: license_policy, fr_citation, aliases_str

        writer.writerow([
            file_date,
            listing_president,
            country,
            entity_name,
            license_req
        ])

    return output.getvalue() 