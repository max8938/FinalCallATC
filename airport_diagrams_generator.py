import requests
import json
import time
import math
from typing import Dict, Tuple, Optional, Any, List
from dataclasses import dataclass

# Set matplotlib to use non-interactive backend for thread safety
import matplotlib
matplotlib.use('Agg')  # Must be before importing pyplot

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import os

@dataclass
class AirportElement:
    """Represents an airport element with coordinates and properties"""
    element_id: str
    element_type: str  # 'way', 'node', 'relation'
    coordinates: List[Tuple[float, float]]
    tags: Dict[str, str]
    category: str  # 'runway', 'taxiway', 'building', 'road', etc.

class AirportOSMFetcher:
    def __init__(self):
        self.overpass_url = "http://overpass-api.de/api/interpreter"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Airport OSM Data Fetcher 1.0'
        })
    
    def get_airport_bounds(self, icao_code: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Get airport bounding box from OpenStreetMap using ICAO code.
        Returns (min_lat, min_lon, max_lat, max_lon) or None if not found.
        """
        # Query to find airport by ICAO code
        query = f"""
        [out:json][timeout:25];
        (
          way["aeroway"="aerodrome"]["icao"="{icao_code.upper()}"];
          relation["aeroway"="aerodrome"]["icao"="{icao_code.upper()}"];
        );
        out geom;
        """
        
        try:
            response = self.session.post(self.overpass_url, data=query)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('elements'):
                print(f"Airport with ICAO code {icao_code} not found")
                return None
            
            # Calculate bounding box from all elements
            all_coords = []
            
            for element in data['elements']:
                if element['type'] == 'way' and 'geometry' in element:
                    for coord in element['geometry']:
                        all_coords.append((coord['lat'], coord['lon']))
                elif element['type'] == 'relation' and 'members' in element:
                    # For relations, we need to get the actual geometry
                    for member in element['members']:
                        if 'geometry' in member:
                            for coord in member['geometry']:
                                all_coords.append((coord['lat'], coord['lon']))
            
            if not all_coords:
                print(f"No geometry found for airport {icao_code}")
                return None
            
            # Calculate bounding box
            lats = [coord[0] for coord in all_coords]
            lons = [coord[1] for coord in all_coords]
            
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            
            # Add small buffer around airport (about 200m for tight fit)
            buffer = 0.002  # roughly 200m in degrees
            min_lat -= buffer
            max_lat += buffer
            min_lon -= buffer
            max_lon += buffer
            
            return (min_lat, min_lon, max_lat, max_lon)
            
        except requests.RequestException as e:
            print(f"Error fetching airport data: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing airport response: {e}")
            return None
    
    def fetch_osm_data(self, bbox: Tuple[float, float, float, float], 
                      element_types: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch OSM data for a bounding box.
        
        Args:
            bbox: Bounding box as (min_lat, min_lon, max_lat, max_lon)
            element_types: List of element types to fetch (default: ['way', 'node', 'relation'])
        
        Returns:
            OSM data as dictionary or None if error
        """
        if element_types is None:
            element_types = ['way', 'node', 'relation']
        
        min_lat, min_lon, max_lat, max_lon = bbox
        
        # Build Overpass query
        elements_query = ""
        for elem_type in element_types:
            elements_query += f"  {elem_type}({min_lat},{min_lon},{max_lat},{max_lon});\n"
        
        query = f"""
        [out:json][timeout:60][bbox:{min_lat},{min_lon},{max_lat},{max_lon}];
        (
{elements_query}
        );
        out geom meta;
        """
        
        try:
            print(f"Fetching OSM data for bbox: {bbox}")
            response = self.session.post(self.overpass_url, data=query)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            print(f"Error fetching OSM data: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing OSM response: {e}")
            return None
    
    def fetch_airport_osm_data(self, icao_code: str, 
                             element_types: Optional[list] = None,
                             save_to_file: bool = True) -> Optional[Dict[str, Any]]:
        """
        Complete workflow: get airport bounds and fetch OSM data.
        
        Args:
            icao_code: Airport ICAO code (e.g., 'KJFK', 'EGLL')
            element_types: List of OSM element types to fetch
            save_to_file: Whether to save data to JSON file
        
        Returns:
            OSM data dictionary or None if error
        """
        print(f"Looking up airport: {icao_code}")
        
        # Get airport bounding box
        bbox = self.get_airport_bounds(icao_code)
        if not bbox:
            return None
        
        print(f"Found airport bounds: {bbox}")
        
        # Add delay to be respectful to Overpass API
        time.sleep(1)
        
        # Fetch OSM data
        osm_data = self.fetch_osm_data(bbox, element_types)
        if not osm_data:
            return None
        
        print(f"Retrieved {len(osm_data.get('elements', []))} OSM elements")
        
        # Save to file if requested
        if save_to_file:
            filename = f"{icao_code.lower()}_osm_data.json"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(osm_data, f, indent=2, ensure_ascii=False)
                print(f"Data saved to {filename}")
            except IOError as e:
                print(f"Error saving file: {e}")
        
        return osm_data
    
    def get_specific_features(self, icao_code: str, feature_types: list) -> Optional[Dict[str, Any]]:
        """
        Fetch specific types of features around an airport.
        
        Args:
            icao_code: Airport ICAO code
            feature_types: List of feature queries (e.g., ['highway', 'building', 'landuse'])
        
        Returns:
            OSM data with specified features
        """
        bbox = self.get_airport_bounds(icao_code)
        if not bbox:
            return None
        
        min_lat, min_lon, max_lat, max_lon = bbox
        
        # Build query for specific features
        feature_queries = []
        for feature in feature_types:
            feature_queries.append(f'  way["{feature}"]({min_lat},{min_lon},{max_lat},{max_lon});')
            feature_queries.append(f'  relation["{feature}"]({min_lat},{min_lon},{max_lat},{max_lon});')
        
        query = f"""
        [out:json][timeout:60];
        (
{chr(10).join(feature_queries)}
        );
        out geom meta;
        """
        
        try:
            print(f"Fetching specific features: {feature_types}")
            time.sleep(1)  # Be respectful to API
            
            response = self.session.post(self.overpass_url, data=query)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            print(f"Error fetching feature data: {e}")
            return None


class AirportDiagramGenerator:
    """Generates PDF diagrams from airport OSM data"""
    
    def __init__(self):
        # Color scheme for different airport elements
        self.colors = {
            'runway': '#404040',      # Dark gray
            'taxiway': '#808080',     # Light gray
            'building': '#8B4513',    # Brown
            'terminal': '#CD853F',    # Sandy brown
            'hangar': '#A0522D',      # Sienna
            'highway': '#FFD700',     # Gold
            'service': '#FFFF99',     # Light yellow
            'apron': '#D3D3D3',       # Light gray
            'parking': '#E6E6FA',     # Lavender
            'grass': '#90EE90',       # Light green
            'water': '#87CEEB',       # Sky blue
            'default': '#C0C0C0'      # Silver
        }
        
        # Line widths for different elements
        self.line_widths = {
            'runway': 8.0,
            'taxiway': 4.0,
            'highway': 3.0,
            'service': 2.0,
            'building': 1.0,
            'default': 1.5
        }
    
    def lat_lon_to_meters(self, lat: float, lon: float, center_lat: float, center_lon: float) -> Tuple[float, float]:
        """Convert lat/lon to approximate meters from center point"""
        # Approximate conversion (works well for small areas)
        lat_m_per_deg = 111320  # meters per degree latitude
        lon_m_per_deg = 111320 * math.cos(math.radians(center_lat))  # varies with latitude
        
        x = (lon - center_lon) * lon_m_per_deg
        y = (lat - center_lat) * lat_m_per_deg
        
        return x, y
    
    def categorize_element(self, tags: Dict[str, str]) -> str:
        """Categorize OSM element based on its tags"""
        # Skip highways and roads - we don't want them in airport diagrams
        if tags.get('highway'):
            return 'skip'
        elif tags.get('service') and 'aeroway' not in tags:
            return 'skip'
            
        # Priority order for categorization
        if tags.get('aeroway') == 'runway':
            return 'runway'
        elif tags.get('aeroway') == 'taxiway':
            return 'taxiway'
        elif tags.get('aeroway') == 'terminal':
            return 'terminal'
        elif tags.get('aeroway') == 'hangar':
            return 'hangar'
        elif tags.get('aeroway') == 'apron':
            return 'apron'
        elif tags.get('building'):
            if tags.get('aeroway') == 'terminal':
                return 'terminal'
            return 'building'
        elif tags.get('amenity') == 'parking':
            return 'parking'
        elif tags.get('landuse') == 'grass':
            return 'grass'
        elif tags.get('natural') == 'water' or tags.get('waterway'):
            return 'water'
        else:
            return 'default'
    
    def parse_osm_data(self, osm_data: Dict[str, Any]) -> List[AirportElement]:
        """Parse OSM data into structured airport elements"""
        elements = []
        
        for element in osm_data.get('elements', []):
            coordinates = []
            tags = element.get('tags', {})
            
            # Extract coordinates based on element type
            if element['type'] == 'node':
                coordinates = [(element['lat'], element['lon'])]
            elif element['type'] == 'way' and 'geometry' in element:
                coordinates = [(coord['lat'], coord['lon']) for coord in element['geometry']]
            elif element['type'] == 'relation':
                # Handle relations (more complex, might contain multiple ways)
                for member in element.get('members', []):
                    if 'geometry' in member:
                        coordinates.extend([(coord['lat'], coord['lon']) for coord in member['geometry']])
            
            if coordinates:
                category = self.categorize_element(tags)
                # Skip elements we don't want to display
                if category == 'skip':
                    continue
                    
                airport_element = AirportElement(
                    element_id=str(element['id']),
                    element_type=element['type'],
                    coordinates=coordinates,
                    tags=tags,
                    category=category
                )
                elements.append(airport_element)
        
        return elements
    
    def create_diagram(self, icao_code: str, osm_data: Dict[str, Any], 
                      output_filename: Optional[str] = None) -> str:
        """
        Create PDF diagram from OSM data
        
        Args:
            icao_code: Airport ICAO code
            osm_data: OSM data dictionary
            output_filename: Custom output filename (optional)
        
        Returns:
            Generated PDF filename
        """
        if output_filename is None:
            output_filename = f"{icao_code.lower()}_diagram.pdf"
        
        # Parse OSM data
        elements = self.parse_osm_data(osm_data)
        
        if not elements:
            print("No elements found to draw")
            return ""
        
        # Calculate bounds and center
        all_coords = []
        for element in elements:
            all_coords.extend(element.coordinates)
        
        if not all_coords:
            print("No coordinates found")
            return ""
        
        lats = [coord[0] for coord in all_coords]
        lons = [coord[1] for coord in all_coords]
        center_lat, center_lon = sum(lats) / len(lats), sum(lons) / len(lons)
        
        # Create PDF
        with PdfPages(output_filename) as pdf:
            # Create main diagram
            fig, ax = plt.subplots(1, 1, figsize=(16, 12))
            
            # Group elements by category for better layering
            element_groups = {}
            for element in elements:
                if element.category not in element_groups:
                    element_groups[element.category] = []
                element_groups[element.category].append(element)
            
            # Draw elements in order (background first, important elements last)
            draw_order = ['grass', 'water', 'apron', 'parking', 'building', 'hangar', 'terminal', 'taxiway', 'runway']
            
            stats = {}
            
            for category in draw_order:
                if category in element_groups:
                    stats[category] = len(element_groups[category])
                    self._draw_element_group(ax, element_groups[category], center_lat, center_lon)
            
            # Draw any remaining categories not in the order
            for category, group in element_groups.items():
                if category not in draw_order:
                    stats[category] = len(group)
                    self._draw_element_group(ax, group, center_lat, center_lon)
            
            # Set equal aspect ratio and clean up axes
            ax.set_aspect('equal')
            ax.axis('off')
            ax.set_title(f'Airport Diagram - {icao_code.upper()}', fontsize=16, fontweight='bold')
            
            # Add legend
            self._add_legend(ax, stats)
            
            plt.tight_layout()
            pdf.savefig(fig, bbox_inches='tight', dpi=300)
            plt.close()
            
            # Create a second page with statistics
            #self._create_stats_page(pdf, icao_code, stats, elements)
        
        print(f"Airport diagram saved as {output_filename}")
        return output_filename
    
    def _calculate_line_length(self, coordinates: List[Tuple[float, float]], 
                              center_lat: float, center_lon: float) -> float:
        """Calculate the length of a line in meters"""
        if len(coordinates) < 2:
            return 0
        
        total_length = 0
        for i in range(len(coordinates) - 1):
            x1, y1 = self.lat_lon_to_meters(coordinates[i][0], coordinates[i][1], center_lat, center_lon)
            x2, y2 = self.lat_lon_to_meters(coordinates[i+1][0], coordinates[i+1][1], center_lat, center_lon)
            total_length += math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        return total_length
    def _draw_element_group(self, ax, elements: List[AirportElement], center_lat: float, center_lon: float):
        """Draw a group of elements of the same category"""
        if not elements:
            return
        
        category = elements[0].category
        color = self.colors.get(category, self.colors['default'])
        line_width = self.line_widths.get(category, self.line_widths['default'])
        
        for element in elements:
            if len(element.coordinates) < 2:
                # Single point (node)
                x, y = self.lat_lon_to_meters(element.coordinates[0][0], element.coordinates[0][1], 
                                            center_lat, center_lon)
                ax.plot(x, y, 'o', color=color, markersize=4)
            else:
                # Line or polygon (way)
                coords_m = [self.lat_lon_to_meters(lat, lon, center_lat, center_lon) 
                           for lat, lon in element.coordinates]
                xs, ys = zip(*coords_m)
                
                # Check if it's a closed polygon (building, area, etc.)
                is_closed = (element.coordinates[0] == element.coordinates[-1] or 
                           category in ['building', 'terminal', 'hangar', 'apron', 'parking', 'grass', 'water'])
                
                if is_closed and len(element.coordinates) > 2:
                    # Draw as filled polygon
                    polygon = patches.Polygon(list(zip(xs, ys)), closed=True, 
                                            facecolor=color, alpha=0.7, 
                                            edgecolor='black', linewidth=0.5)
                    ax.add_patch(polygon)
                else:
                    # Draw as line
                    ax.plot(xs, ys, color=color, linewidth=line_width, solid_capstyle='round')
                
                # Add labels for runways
                if category == 'runway' and 'ref' in element.tags:
                    center_x, center_y = sum(xs) / len(xs), sum(ys) / len(ys)
                    ax.text(center_x, center_y, element.tags['ref'], 
                           ha='center', va='center', fontweight='bold', fontsize=10,
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
                
                # Add labels for taxiways (only for longer segments)
                if category == 'taxiway' and 'ref' in element.tags:
                    # Calculate taxiway length
                    length = self._calculate_line_length(element.coordinates, center_lat, center_lon)
                    
                    # Only label taxiways longer than 150 meters
                    if length > 100:
                        center_x, center_y = sum(xs) / len(xs), sum(ys) / len(ys)
                        ref_text = element.tags['ref']
                        # Keep taxiway labels shorter and less prominent
                        ax.text(center_x, center_y, ref_text, 
                               ha='center', va='center', fontweight='normal', fontsize=8,
                               bbox=dict(boxstyle='round,pad=0.2', facecolor='lightgray', alpha=0.7))
    
    def _add_legend(self, ax, stats: Dict[str, int]):
        """Add legend to the plot"""
        legend_elements = []
        
        for category, count in stats.items():
            if count > 0:
                color = self.colors.get(category, self.colors['default'])
                label = f"{category.title()} ({count})"
                
                if category in ['runway', 'taxiway']:
                    # Line legend
                    line_width = self.line_widths.get(category, 2.0)
                    legend_elements.append(plt.Line2D([0], [0], color=color, lw=line_width, label=label))
                else:
                    # Patch legend
                    legend_elements.append(patches.Patch(color=color, label=label))
        
        if legend_elements:
            ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))
    
    def _create_stats_page(self, pdf, icao_code: str, stats: Dict[str, int], elements: List[AirportElement]):
        """Create a statistics page"""
        fig, ax = plt.subplots(1, 1, figsize=(11, 8.5))
        ax.axis('off')
        
        # Title
        fig.suptitle(f'Airport Statistics - {icao_code.upper()}', fontsize=16, fontweight='bold')
        
        # Statistics text
        stats_text = [
            f"Total Elements: {sum(stats.values())}",
            f"Total Categories: {len(stats)}",
            "",
            "Elements by Category:"
        ]
        
        for category, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
            stats_text.append(f"  {category.title()}: {count}")
        
        # Find interesting tags
        stats_text.extend(["", "Notable Features:"])
        
        runways = [e for e in elements if e.category == 'runway' and 'ref' in e.tags]
        if runways:
            runway_refs = [e.tags['ref'] for e in runways]
            stats_text.append(f"  Runways: {', '.join(runway_refs)}")
        
        taxiways = [e for e in elements if e.category == 'taxiway' and 'ref' in e.tags]
        if taxiways:
            # Show only the first few taxiway names
            taxiway_refs = list(set([e.tags['ref'] for e in taxiways]))[:8]  # Limit and dedupe
            stats_text.append(f"  Taxiways: {', '.join(sorted(taxiway_refs))}")
        
        terminals = [e for e in elements if 'terminal' in e.tags.get('name', '').lower()]
        if terminals:
            terminal_names = [e.tags.get('name', 'Unnamed') for e in terminals[:3]]  # Limit to 3
            stats_text.append(f"  Terminals: {', '.join(terminal_names)}")
        
        # Add timestamp
        stats_text.extend(["", f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}"])
        
        ax.text(0.1, 0.9, '\n'.join(stats_text), transform=ax.transAxes, 
                fontsize=12, verticalalignment='top', fontfamily='monospace')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
    
    def create_airport_diagram(self, icao_code: str) -> str:
        """Complete workflow to create airport diagram"""
        # Fetch OSM data
        fetcher = AirportOSMFetcher()
        osm_data = fetcher.fetch_airport_osm_data(icao_code, save_to_file=True)
        
        if not osm_data:
            print(f"Failed to fetch OSM data for {icao_code}")
            return ""
        
        # Generate diagram
        return self.create_diagram(icao_code, osm_data)


def generateAirportDiagram(icao_code: str):
    print(f"Creating airport diagram for {icao_code}")

    filename = os.path.join("AirportDiagrams", f"{icao_code.lower()}_airport_diagram.pdf")
    if os.path.exists(filename):
        print("Airport diagram " + filename + " already exists, not generating new one.")
        return filename
    
    diagram_gen = AirportDiagramGenerator()
    fetcher = AirportOSMFetcher()
    
    # Fetch specific airport features
    specific_data = fetcher.get_specific_features(
        icao_code, 
        ['aeroway']
    )
    
    if specific_data:
        os.makedirs("AirportDiagrams", exist_ok=True)
        
        diagram_gen.create_diagram(icao_code, specific_data, filename)
        print(f"Airport diagram created: {filename}")
        return filename
    else:
        print(f"Failed to fetch specific features for {icao_code}")
        return None


def main():
    """Main function to run the example"""
    generateAirportDiagram("GMME")  

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        icao = sys.argv[1].upper()
        diagram_gen = AirportDiagramGenerator()
        result = diagram_gen.create_airport_diagram(icao)
        if result:
            print(f"Diagram created: {result}")
    else:
        main()
