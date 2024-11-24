#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Oct 20 10:23:48 2024

@author: juda
"""
import sys
import os

#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from common.satelite import ColSatellite, csv_from_sat, statAnalisisData

import ee
import pandas as pd
import numpy as np
import gstools as gs
import matplotlib.pyplot as plt
from shapely.geometry import shape
import geopandas as gpd
import matplotlib.colors as colors
import numpy as np
import matplotlib.colors as mcolors

####### Using a feature collection

Municipios = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level1")#Datos de fronteras a nivel municipal
Mun_col = Municipios.filter(ee.Filter.eq('ADM0_NAME', 'Colombia'))#Filtro de datos para Colombia

############ Using a geodataframe

# Path to the .geojson file
file_path = 'common/Departamentos_Junio_2024_shp/Departamento.shp'
# Load the file into a GeoDataFrame
gdf = gpd.read_file(file_path)



#-------------------------------------------------
roi = gdf

csv_filename = 'data_analysis/colombia_prom_2020_filtered.csv'
layer = 'CH4_column_volume_mixing_ratio_dry_air_bias_corrected'
title = 'CH4 column Mean values 2019-02-01 to 2024-09-27'
cbar_title = 'CH4 column Mean values mol/mol'


#---------------------------------------------------------------------


r = pd.read_csv(csv_filename, usecols=(0,1,3),delimiter=',') # se carga el archivo .csv

sat_data = csv_from_sat(r)

# Colors:
## jet
## viridis
## plasma

## Colors
# Define your base colors
colors = ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']

# Number of segments you want between each color
num_segments = 30  # Change this value for more or fewer interpolated colors

# Create an array to hold the interpolated colors
interpolated_colors = []
# Interpolate between each pair of colors
for i in range(len(colors) - 1):
    # Create a gradient of colors between each pair
    gradient = np.linspace(mcolors.to_rgb(colors[i]), mcolors.to_rgb(colors[i + 1]), num_segments)
    interpolated_colors.append(gradient)

# Concatenate all gradients into a single array
interpolated_colors = np.vstack(interpolated_colors)

# Create a custom colormap
custom_cmap = mcolors.LinearSegmentedColormap.from_list("custom_cmap", interpolated_colors)




#color_list=['jet', 'viridis', custom_cmap, 'plasma']
color_list=['jet']

for item in color_list:
    
    sat_data.plot_sat_data(layer, roi, title, cbar_title, color=item, levels=[1640, 1980])
    
    incidences = sat_data.get_incidences(roi, 'Methane Measurement Density', 'Observation Count', color=item, levels=[0, 285])


