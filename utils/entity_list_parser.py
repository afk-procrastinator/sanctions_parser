"""
BIS Entity List Parser
Utilities for fetching, parsing, and processing Bureau of Industry and Security Entity List data.
"""

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import logging
import json
import os
from typing import Dict, List, Optional, Tuple, Any, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntityListParser:
    """Parser for BIS Entity List XML data from the Federal Register."""
    
    def __init__(self):
        """Initialize the Entity List Parser."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_xml(self, url: str) -> str:
        """
        Fetch XML data from a Federal Register URL.
        
        Args:
            url: The Federal Register XML URL to fetch data from
            
        Returns:
            The raw XML content as a string
            
        Raises:
            Exception: If the request fails or the XML is invalid
        """
        logger.info(f"Fetching XML from: {url}")
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching XML: {e}")
            raise Exception(f"Failed to fetch XML data: {e}")
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text by removing strange symbols and normalizing whitespace.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Replace special characters
        text = re.sub(r'â', '', text)
        text = re.sub(r'Â§', '§', text)
        
        # Replace other odd Unicode characters
        text = re.sub(r'[^\x00-\x7F\u00A0-\u00FF\u0100-\u017F\u0180-\u024F]+', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_aliases_from_text(self, text: str) -> List[str]:
        """
        Extract aliases from text based on common patterns.
        
        Args:
            text: The text to extract aliases from
            
        Returns:
            List of extracted aliases
        """
        aliases = []
        
        # Split the text by semicolons
        parts = text.split(';')
        
        # Process each part for possible aliases
        for part in parts:
            part = part.strip()
            # Look for common alias patterns
            if not part:
                continue
            
            if part.startswith('and'):
                part = part[3:].strip()
            
            # Skip parts that look like addresses (have numbers or specific keywords)
            if (re.search(r'\d', part) or 
                any(keyword in part.lower() for keyword in ['street', 'road', 'avenue', 'blvd', 'st.', 'ave', 'floor', 'suite', 'apt', 'building'])):
                continue
            
            # Add as potential alias if it's not too long
            if len(part) < 50 and part:
                aliases.append(part)
        
        return aliases
    
    def extract_entities(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Extract entity information from the XML content.
        
        Args:
            xml_content: The raw XML content as a string
            
        Returns:
            A list of dictionaries containing structured entity information
            
        Raises:
            Exception: If the XML parsing fails
        """
        logger.info("Parsing XML content to extract entities")
        entities = []
        
        try:
            # Parse the XML using BeautifulSoup
            soup = BeautifulSoup(xml_content, 'lxml-xml')
            
            # Find the GPOTABLE
            gpotable = soup.find('GPOTABLE')
            if not gpotable:
                logger.error("No GPOTABLE found in XML content")
                return entities
            
            # Extract rows from the table
            rows = gpotable.find_all('ROW')
            logger.info(f"Found {len(rows)} rows in table")
            
            current_country = None
            current_entity = None
            
            for i, row in enumerate(rows):
                cells = row.find_all('ENT')
                
                if not cells:
                    continue
                
                # Check if this is a country header
                if cells[0].get('I') == '01':
                    current_country = self._clean_text(cells[0].get_text(strip=True))
                    logger.info(f"Found country: {current_country}")
                    continue
                
                # Look for entity rows (rows with I=22 attribute)
                if cells[0].get('I') == '22':
                    # Entity row should have content in the second cell
                    if len(cells) > 1 and cells[1]:
                        second_cell_text = self._clean_text(cells[1].get_text(strip=True))
                        
                        # Skip rows with just asterisks (separator rows)
                        if not second_cell_text or second_cell_text.strip() == "******" or re.match(r'^[\*\s]+$', second_cell_text):
                            continue
                        
                        # This is a main entity row
                        # First, check if this is an entity name with a.k.a. in it
                        is_entity_with_alias = False
                        if "a.k.a." in second_cell_text:
                            is_entity_with_alias = True
                            # Extract entity name (everything before a.k.a.)
                            entity_name = second_cell_text.split("a.k.a.")[0].strip().rstrip(',')
                        else:
                            # Try to extract entity name from the second cell text
                            entity_name_parts = second_cell_text.split(',', 1)
                            entity_name = entity_name_parts[0].strip()
                        
                        # Create entity object
                        entity = {
                            'country': current_country,
                            'name': entity_name,
                            'aliases': [],
                            'license_requirement': "",
                            'license_policy': "",
                            'federal_register_citation': ""
                        }
                        
                        # Extract aliases from list items
                        list_items = cells[1].find_all('LI')
                        
                        if list_items:
                            # Process list items
                            for li in list_items:
                                li_text = self._clean_text(li.get_text(strip=True))
                                if not li_text:
                                    continue
                                    
                                # Check if this is an alias (starts with dash/emdash)
                                if li_text.startswith('—') or li_text.startswith('-'):
                                    # This is an alias
                                    alias = li_text.replace('—', '', 1).replace('-', '', 1).strip()
                                    if alias:
                                        # Clean up "and" at the end of aliases
                                        if alias.endswith('and'):
                                            alias = alias[:-3].strip()
                                        entity['aliases'].append(alias)
                        
                        # Extract additional fields
                        if len(cells) > 2:
                            entity['license_requirement'] = self._clean_text(cells[2].get_text(strip=True))
                        
                        if len(cells) > 3:
                            entity['license_policy'] = self._clean_text(cells[3].get_text(strip=True))
                        
                        if len(cells) > 4:
                            entity['federal_register_citation'] = self._clean_text(cells[4].get_text(strip=True))
                        
                        # Only add if it's not a separator row
                        if not entity_name.startswith('*') and "*" not in entity_name:
                            entities.append(entity)
                            current_entity = entity
                            logger.info(f"Added entity: {entity_name} from {current_country}")
                            if entity['aliases']:
                                logger.info(f"  Aliases: {', '.join(entity['aliases'])}")
            
            # Post-processing to extract aliases from text if needed
            for entity in entities:
                if not entity['aliases'] and entity['name']:
                    potential_aliases = self._extract_aliases_from_text(entity['name'])
                    if potential_aliases:
                        entity['aliases'] = potential_aliases
                        logger.info(f"  Extracted aliases for {entity['name']}: {', '.join(potential_aliases)}")
            
            return entities
            
        except Exception as e:
            logger.error(f"Error parsing XML content: {e}", exc_info=True)
            raise Exception(f"Failed to parse XML content: {e}")
    
    def convert_fr_url_to_xml_url(self, fr_url: str) -> str:
        """
        Convert a Federal Register URL to its corresponding XML URL.
        
        Args:
            fr_url: The Federal Register URL
            
        Returns:
            The corresponding XML URL
            
        Raises:
            ValueError: If the URL is not a valid Federal Register URL
        """
        try:
            # Extract components from the URL
            pattern = r'https://www\.federalregister\.gov/documents/(\d{4})/(\d{2})/(\d{2})/([\w-]+)'
            match = re.match(pattern, fr_url)
            
            if not match:
                raise ValueError("Invalid Federal Register URL format")
                
            year, month, day, doc_id = match.groups()
            
            # Construct the XML URL
            xml_url = f"https://www.federalregister.gov/documents/full_text/xml/{year}/{month}/{day}/{doc_id}.xml"
            return xml_url
        except Exception as e:
            logger.error(f"Error converting URL: {e}")
            raise ValueError(f"Failed to convert URL: {e}")
    
    def process_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process the extracted entities into a structured format.
        
        Args:
            entities: List of entity dictionaries
            
        Returns:
            Processed data with statistics and structured entities
        """
        logger.info(f"Processing {len(entities)} entities")
        
        # Filter out entities with empty license requirements
        filtered_entities = [entity for entity in entities if entity.get('license_requirement', '').strip()]
        
        if len(filtered_entities) < len(entities):
            logger.info(f"Filtered out {len(entities) - len(filtered_entities)} entities with empty license requirements")
        
        # Process entities and generate statistics
        countries = {}
        for entity in filtered_entities:
            country = entity.get('country', 'Unknown')
            countries[country] = countries.get(country, 0) + 1
        
        return {
            'total_entities': len(filtered_entities),
            'countries': countries,
            'entities': filtered_entities
        }

# API functions for use in routes

def fetch_entity_list_xml(url: str) -> str:
    """
    Fetch Entity List XML from a Federal Register URL or local file.
    
    Args:
        url: The Federal Register URL or local file path to fetch XML from
        
    Returns:
        The raw XML content
    """
    parser = EntityListParser()
    
    # First, check if this is a local file
    if os.path.exists(url):
        logger.info(f"Reading XML from local file: {url}")
        try:
            with open(url, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading local file: {e}")
            raise Exception(f"Failed to read local XML file: {e}")
    
    # If not a local file, try as URL
    # Convert URL if it's not already an XML URL
    if 'full_text/xml' not in url:
        url = parser.convert_fr_url_to_xml_url(url)
    
    # Fetch the XML content
    try:
        xml_content = parser.fetch_xml(url)
        return xml_content
    except Exception as e:
        logger.error(f"Error fetching XML from URL: {e}")
        raise Exception(f"Failed to fetch XML data: {e}")

def parse_entity_list(xml_content_or_path: str) -> Dict[str, Any]:
    """
    Parse Entity List XML content or file into structured data.
    
    Args:
        xml_content_or_path: Either raw XML content or a path to an XML file
        
    Returns:
        Structured entity list data
    """
    parser = EntityListParser()
    
    # Check if input is a file path
    if os.path.exists(xml_content_or_path):
        logger.info(f"Reading XML from file: {xml_content_or_path}")
        try:
            with open(xml_content_or_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            entities = parser.extract_entities(xml_content)
            return parser.process_entities(entities)
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            raise Exception(f"Failed to process XML file: {e}")
    
    # If not a file, treat as raw XML content
    entities = parser.extract_entities(xml_content_or_path)
    return parser.process_entities(entities) 