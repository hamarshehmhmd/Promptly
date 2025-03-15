# Test Data for Promptly Plugin

This directory contains sample data files that can be used to test the Promptly plugin functionality.

## Files Included

1. `ne_110m_admin_0_countries.geojson` - A simplified world countries dataset
2. `ne_110m_populated_places.geojson` - A dataset of major populated places worldwide

## How to Use

1. Open QGIS
2. Load these files as vector layers using "Add Vector Layer" or drag and drop
3. Use these layers to test the plugin's features:
   - Layer metadata reference
   - Spatial queries
   - Attribute operations
   - Database integration

## Example Prompts

Here are some example prompts you can try with this data:

1. "Calculate the total number of countries in the dataset"
2. "Find the 10 most populous cities in Europe"
3. "Create a buffer of 100km around all major cities"
4. "Calculate the average population of cities by continent"

## Data Source

These files are from Natural Earth (https://www.naturalearthdata.com/), which provides free vector and raster map data at various scales. 