#!/usr/bin/env python3
"""
Test script to parse BIS Entity List XML data and format it into a table.
"""

import os
import sys
from bs4 import BeautifulSoup
import re
from tabulate import tabulate

def clean_text(text):
    """Clean text by removing strange symbols and normalizing whitespace."""
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

def extract_aliases_from_text(text):
    """Extract aliases from text based on common patterns."""
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

def parse_entity_list(xml_content):
    """Parse entity list from XML content with rows that have I=22 attribute."""
    entities = []
    
    soup = BeautifulSoup(xml_content, 'lxml-xml')
    
    # Find the GPOTABLE
    gpotable = soup.find('GPOTABLE')
    if not gpotable:
        print("No GPOTABLE found in XML content")
        return entities
    
    # Extract rows from the table
    rows = gpotable.find_all('ROW')
    print(f"Found {len(rows)} rows in table")
    
    current_country = None
    current_entity = None
    
    for i, row in enumerate(rows):
        cells = row.find_all('ENT')
        
        if not cells:
            continue
        
        # Check if this is a country header
        if cells[0].get('I') == '01':
            current_country = clean_text(cells[0].get_text(strip=True))
            print(f"Found country: {current_country}")
            continue
        
        # Look for entity rows or continuation rows (rows with I=22 attribute)
        if cells[0].get('I') == '22':
            # Entity row should have content in the second cell
            if len(cells) > 1 and cells[1]:
                second_cell_text = clean_text(cells[1].get_text(strip=True))
                
                # Skip rows with just asterisks (separator rows)
                if not second_cell_text or second_cell_text.strip() == "******" or re.match(r'^[\*\s]+$', second_cell_text):
                    continue
                
                # Check if this is a continuation row for an address (no LI elements)
                if current_entity and not cells[1].find('LI'):
                    # This is likely a continuation of the previous entity's address
                    if current_entity['address']:
                        current_entity['address'] += "; " + second_cell_text
                    else:
                        current_entity['address'] = second_cell_text
                    print(f"  Added address continuation to {current_entity['name']}")
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
                    'address': "",
                    'license_requirement': "",
                    'license_policy': "",
                    'federal_register_citation': ""
                }
                
                # Extract aliases and address from list items
                list_items = cells[1].find_all('LI')
                address_parts = []
                
                if list_items:
                    # Process list items
                    for li in list_items:
                        li_text = clean_text(li.get_text(strip=True))
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
                        else:
                            # This is an address part
                            address_parts.append(li_text)
                
                    # Combine address parts
                    if address_parts:
                        entity['address'] = "; ".join(address_parts)
                else:
                    # If no list items but we have text after the entity name
                    if not is_entity_with_alias:
                        if len(entity_name_parts) > 1:
                            entity['address'] = entity_name_parts[1].strip()
                
                # Extract additional fields
                if len(cells) > 2:
                    entity['license_requirement'] = clean_text(cells[2].get_text(strip=True))
                
                if len(cells) > 3:
                    entity['license_policy'] = clean_text(cells[3].get_text(strip=True))
                
                if len(cells) > 4:
                    entity['federal_register_citation'] = clean_text(cells[4].get_text(strip=True))
                
                # Only add if it's not a separator row
                if not entity_name.startswith('*'):
                    entities.append(entity)
                    current_entity = entity
                    print(f"Added entity: {entity_name} from {current_country}")
                    if entity['aliases']:
                        print(f"  Aliases: {', '.join(entity['aliases'])}")
    
    # Post-processing to extract aliases from address if needed
    for entity in entities:
        if not entity['aliases'] and entity['address']:
            potential_aliases = extract_aliases_from_text(entity['address'])
            if potential_aliases:
                # Remove aliases from address
                address_parts = entity['address'].split(';')
                clean_address_parts = []
                
                for part in address_parts:
                    if part.strip() not in potential_aliases:
                        clean_address_parts.append(part.strip())
                
                entity['aliases'] = potential_aliases
                entity['address'] = "; ".join(clean_address_parts)
                print(f"  Extracted aliases for {entity['name']}: {', '.join(potential_aliases)}")
    
    return entities

def main():
    # Check if file path was provided
    if len(sys.argv) < 2:
        print("Usage: python parse_entity_list.py <xml_file_path> [output.json]")
        sys.exit(1)
    
    xml_file_path = sys.argv[1]
    
    # Check if file exists
    if not os.path.exists(xml_file_path):
        print(f"Error: File {xml_file_path} does not exist")
        sys.exit(1)
    
    # Read XML file
    try:
        with open(xml_file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    # Parse entities
    entities = parse_entity_list(xml_content)
    
    # Format as table
    if entities:
        # Prepare data for tabulate
        table_data = []
        for entity in entities:
            # Format aliases as a string
            aliases = ", ".join(entity.get('aliases', []))
            row = [
                entity.get('country', 'Unknown'),
                entity.get('name', 'Unknown'),
                aliases[:50] + "..." if len(aliases) > 50 else aliases,
                entity.get('license_requirement', '')[:30] + "..." if len(entity.get('license_requirement', '')) > 30 else entity.get('license_requirement', ''),
                entity.get('license_policy', '')[:30] + "..." if len(entity.get('license_policy', '')) > 30 else entity.get('license_policy', '')
            ]
            table_data.append(row)
        
        # Display table
        headers = ['Country', 'Entity Name', 'Aliases', 
                   'License Req', 'License Policy']
        print("\n" + tabulate(table_data, headers=headers, tablefmt='grid'))
        print(f"\nTotal entities found: {len(entities)}")
    else:
        print("No entities found in the XML file.")
        
    # Output summary by country
    countries = {}
    for entity in entities:
        country = entity.get('country', 'Unknown')
        countries[country] = countries.get(country, 0) + 1
    
    print("\nSummary by Country:")
    for country, count in countries.items():
        print(f"  {country}: {count} entities")
    
    # Save to JSON file
    if entities and len(sys.argv) > 2:
        import json
        output_file = sys.argv[2]
        print(f"\nSaving entities to {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(entities, f, indent=2)
        print(f"Saved {len(entities)} entities to {output_file}")

if __name__ == "__main__":
    main() 