#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 19 12:49:12 2023

@author: bojack
"""
import ee
from abc import ABC, abstractmethod
from shapely.geometry import Point
from shapely.geometry import shape
import numpy as np
import gstools as gs
import matplotlib.pyplot as plt
from math import ceil
from numpy.ma.core import sqrt
import os
import pandas as pd
import geopandas as gpd
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import contextily as cx
import xyzservices.providers as xyz
import cartopy.mpl.gridliner as gridliner
from shapely.geometry import Polygon, MultiPolygon
import matplotlib.colors as mcolors
#------------

#ee.Authenticate()
ee.Initialize()
#------------

class Satellite(ABC):
    """
    Abstract base class for a satellite.
    """
    
    def __init__(self, sat_name, layer):
        """
        Initialize the Satellite object.
        
        Args:
            sat_name (str): The name of the satellite.
            layer (str): The layer of the satellite.
        """
        self.satellite = sat_name
        self.layer = layer
        self.regions = []
    
    def get_image_collection(self, init_date, final_date):
        """
        Get the image collection for the given date range.
        
        Args:
            init_date (str): The initial date.
            final_date (str): The final date.
            
        Returns:
            ee.ImageCollection: The image collection for the given date range.
        """
        image_collection = ee.ImageCollection(self.satellite).select(self.layer)
        image_collection = image_collection.filterDate(init_date, final_date)
        return image_collection
    
    @abstractmethod
    def get_available_regions(self):
        """
        Abstract method to get available regions.
        """
        pass
    
    @abstractmethod
    def get_roi(self, identifier):
        """
        Abstract method to get region of interest.
        
        Args:
            identifier (str): The identifier of the region.
        """
        pass
    
    def add_region(self, title, identifier, region_object):
        """
        Add a region to the regions list.
        
        Args:
            title (str): The title of the region.
            identifier (str): The identifier of the region.
            region_object (ee.Geometry): The region object.
        """
        region = {
            'title': title,
            'id': identifier,
            'type': ee.Algorithms.ObjectType(region_object),
            'object': region_object
        }
        self.regions.append(region)

    def clip_image(self, image_collection, shape):
        """
        Clip the image collection with the given shape.
        
        Args:
            image_collection (ee.ImageCollection): The image collection.
            shape (ee.Geometry): The shape to clip the image collection.
            
        Returns:
            ee.Image: The clipped image.
        """
        mean_image = image_collection.mean()
        mean_image_clip = mean_image.clip(shape.geometry())
        return mean_image_clip
    
    def get_region_limits(self, specificRegionPoly):
        
        cor=specificRegionPoly.getInfo()['coordinates'][0]

        xmax=cor[0][1]
        ymax=cor[0][0]
        xmin=cor[0][1]
        ymin=cor[0][0]


        for i in range(len(cor)):
          xc=cor[i][1]
          yc=cor[i][0]
          if xc>xmax:
            xmax=xc
          if yc>ymax:
            ymax=yc
          if xc<xmin:
            xmin=xc
          if yc<ymin:
            ymin=yc
    
        return xmax, ymax, xmin, ymin
    
    def getImageCollectionAsDF(self, imageCollection, region, ceros = False):
        """
        Extracts pixel values from an Earth Engine ImageCollection within a specified region, 
        filters for non-null values of a user-defined layer, and returns a Pandas DataFrame.

        Args:
            imageCollection: An Earth Engine ImageCollection object.
            layer_name: A string specifying the layer to extract values from.

        Returns:
            A Pandas DataFrame containing pixel values.
        """

        
        firstImage = imageCollection.first(); 
        nativeScale = firstImage.projection().nominalScale()
        
        ImgCollection_to_eeList = imageCollection.getRegion(region, nativeScale)
        eeList_to_array = np.array(ImgCollection_to_eeList.getInfo())
        array_to_df = pd.DataFrame(eeList_to_array[1:,:], columns=eeList_to_array[0,:])

        # Filter based on the user-specified layer_name
        if ceros:
            array_to_df = array_to_df[array_to_df[self.layer].notnull()] 
        
        array_to_df[self.layer] = array_to_df[self.layer].clip(lower=0)
        return array_to_df
        
    
class ColSatellite(Satellite):
    """
    Class for a Colombian satellite that inherits from the Satellite class.
    """
    
    fronteras_maritimas_col = ee.FeatureCollection('projects/ee-jolejua/assets/EEZ_land_union_v3_202003')
    fronteras_maritimas_col = fronteras_maritimas_col.filter(ee.Filter.eq('UNION', 'Colombia'))
    fronteras_maritimas_col = {
        'title': 'Colombia con sus fronteras maritimas',
        'id': 'fronterasMaritimasCol',
        'type': type(fronteras_maritimas_col),
        'object': fronteras_maritimas_col
    }
    local_regions = [fronteras_maritimas_col]
    
    def __init__(self, sat_name, layer):
        Satellite.__init__(self, sat_name, layer)
    
    def get_available_regions(self):
        """
        Get available regions and print them.
        """
        for region in self.local_regions:
            self.regions.append(region)
        print('Plotting available regions... \n')
        for i, region in enumerate(self.regions, 1):
            print(f'---------- Region {i} -----------')
            print('title: ' + region['title'])
            print('id: ' + region['id'])
            print('type: ', region['type'])
            print('--------------------------------')
            print('\n')
        print('Done...')  
    
    def get_roi(self, identifier):
        """
        Get region of interest (ROI) by identifier.
        
        Args:
            identifier (str): The identifier of the region.
            
        Returns:
            ee.Geometry: The region of interest.
        """
        
        roi = None
        for region in self.regions:
            if region['id'] == identifier:
                print('Selecting ' + identifier + ' region')
                roi = region['object'] 
                break
        if roi:
            return roi
        else: 
            print('No funciona')
            
    def get_clusters_data(self):
        pass
            
class csv_from_sat(object):
    
    
    def __init__(self, satData):
        
        self.satData = satData
        self.xr = None
        self.yr = None
        self.fieldr = None
        
    
    
    
    def getVal_in_shape(self, shapefile, data_columns=None):
        """
        Function that obtains the satellite data values contained within a given shapefile.
        
        Parameters
        ----------
        shapefile : ee.Geometry.Polygon() or ee.FeatureCollection
            The shapefile defining the area of interest.
        data_columns : list, optional
            List of column names to include from satData. If None, all columns are included.
        
        Returns
        -------
        df : pandas.DataFrame
            A DataFrame containing the filtered satellite data.
        """
        
        # Convert shapefile to Shapely geometry
        try:
            shapely_polygon = shape(shapefile.getInfo())
        except:
            # Handle FeatureCollection
            geometries = shapefile.geometry().geometries().getInfo()
            shapely_geometries = [Polygon(geom['coordinates'][0]) for geom in geometries]
            shapely_polygon = MultiPolygon(shapely_geometries) if len(shapely_geometries) > 1 else shapely_geometries[0]
        
        # Determine which columns to include
        if data_columns is None:
            data_columns = list(self.satData.keys())
        else:
            # Ensure 'longitude', 'latitude', and 'date' are always included
            required_columns = ['longitude', 'latitude', 'date']
            data_columns = list(set(data_columns + required_columns))
        
        # Create a DataFrame from satellite data
        df = pd.DataFrame({col: self.satData[col] for col in data_columns})
        
        # Create a mask for points within the polygon
        df['in_polygon'] = df.apply(lambda row: shapely_polygon.contains(Point(row['longitude'], row['latitude'])), axis=1)
        
        # Filter the DataFrame
        df_filtered = df[df['in_polygon']].drop('in_polygon', axis=1)
        df_filtered = df_filtered.reset_index(drop=True)
        
        return df_filtered
    
    def get_plot(self, lon, lat, field, roi, title, cbar_title, color, levels_list):
        
        # ROI can be Feature collection GEE or geojson
        
        
        #plotting
        # Determine the grid shape
        nx = len(np.unique(lon))  # Number of unique x values
        ny = len(np.unique(lat))  # Number of unique y values
        xx, yy = np.meshgrid(np.unique(lon), np.unique(lat))
        field_organized_data = np.zeros((ny, nx))

        for j in range(ny):
            for i in range(nx):
                lon_ij =  xx[j, i]
                lat_ij =  yy[j, i]
                
                mask = np.isin(lon, lon_ij, invert=False)
                filtered_lat_i = lat[mask]
                field_data_i = field[mask]
                mask = np.isin(filtered_lat_i, lat_ij, invert=False)
                field_data_i = field_data_i[mask]
                if len(field_data_i) == 1:
                    if field_data_i[0] <= 0:
                        field_organized_data[j, i] = 0
                    else:
                        field_organized_data[j, i] = field_data_i[0]
                    
                else:
                    field_organized_data[j, i] = None
                   
        
        plt.figure(1, figsize=(10, 8))
        
        fig, ax1 = plt.subplots(subplot_kw={'projection': ccrs.epsg(3857)})
        
        extent = [min(np.unique(lon)), max(np.unique(lon)),
                  min(np.unique(lat)), max(np.unique(lat))]
        
        # Esta linea es mejor quitarla pero por ahora la dejo para ver toda colombia
        extent = [-81.615, -66.1, -4.5, 12.9]
        
        
        #extent = [x * 1.02 for x in extent]
        
        
        ax1.set_extent(extent, crs=ccrs.PlateCarree())
        
        cx.add_basemap(ax1, source=cx.providers.OpenStreetMap.Mapnik)
        
        # Define the levels for the contour
        
        if levels_list == []:
            num_levels = 10 # Number of levels to add more intervals
            field_organized_data_lim = field_organized_data[~np.isnan(field_organized_data)]
            levels = np.linspace(field_organized_data_lim.min(), field_organized_data_lim.max(), num_levels).round(0)
            
        elif np.any(np.isnan(field_organized_data)) or np.any(np.isinf(field_organized_data)):
            levels = np.arange(levels_list[0],levels_list[1],20).round(0)
        
            
        CS1 = ax1.contourf(xx, yy, field_organized_data, cmap=color, levels=levels, transform=ccrs.PlateCarree(), alpha=0.6)

        
        cbar = fig.colorbar(CS1, pad=0.2)
        cbar.set_label(cbar_title, rotation=90, labelpad=20)  # Adjust rotation and padding as needed
        
        
        ax1.set_title(title)
        ax1.set_xlabel('Longitud')
        ax1.set_ylabel('Latitud')      
        
        # Agregar marcas de latitud y longitud
        gl = ax1.gridlines(crs=ccrs.PlateCarree(), draw_labels=True,
                           linewidth=1, color='gray', alpha=0.5, linestyle='--')
        gl.top_labels = False
        gl.right_labels = False
        gl.xformatter = gridliner.LONGITUDE_FORMATTER
        gl.yformatter = gridliner.LATITUDE_FORMATTER
        gl.xlabel_style = {'size': 10, 'color': 'gray'}
        gl.ylabel_style = {'size': 10, 'color': 'gray'}
       
        if isinstance(roi, gpd.GeoDataFrame):
            print("The variable is a GeoDataFrame")
            gdf = roi
            
        elif isinstance(roi, ee.FeatureCollection):
            print("The variable is a FeatureCollection")
            # Assuming merged_feature_collection_dict is your dictionary
            features = roi.getInfo()['features']
            # Extracting properties and geometry from each feature
            data_dict = {'properties': [feat['properties'] for feat in features],
                         'geometry': [shape(feat['geometry']) for feat in features]}
            
            # Creating a DataFrame from properties
            df = pd.DataFrame(data_dict['properties'])
            
            # Creating a GeoDataFrame from the DataFrame and the geometries
            gdf = gpd.GeoDataFrame(df, geometry=data_dict['geometry'])
        
        else:
            raise("the actual ROI is not valid, please use a featureCollection or a gedaframe instead")
            
        
        if gdf.crs is None:
            # Only set CRS if it doesn't have one
            gdf.set_crs(epsg=4326, inplace=True)
        else:
            print("GeoDataFrame already has CRS:", gdf.crs)
        
        # Transform to Web Mercator for plotting
        gdf = gdf.to_crs(epsg=3857)
              
        gdf.plot(ax=ax1, edgecolor='black', facecolor='none', linewidth=0.3, alpha=0.4)
        
        plt.savefig('emissions_images/'+title + '.png', dpi=1200, bbox_inches='tight')

        plt.show()
        
    
    def plot_sat_data(self, layer, roi, title, cbar_title, color='coolwarm', levels=[]):
        
        r = self.satData.copy()
        
        if layer == 'Optical_Depth_055':
            r['longitude'] = r["longitude"].round(decimals=7)
            r['latitude'] = r["latitude"].round(decimals=4)
        r_mean = r.groupby(["longitude", "latitude"])[[layer]].mean()
        r_mean = r_mean.reset_index() 
        
        
        lon = r_mean['longitude'].to_numpy()
        #lon = np.round(lon, decimals=2)
        lat = r_mean['latitude'].to_numpy()
        #lat = np.round(lat, decimals=2)
        field = r_mean[layer].to_numpy()
        
        #plotting
        
        self.get_plot(lon, lat, field, roi, title, cbar_title, color, levels)
        
        
        
    def get_incidences(self, roi, title, cbar_title, color='coolwarm', levels=[]):
        # Make a copy of the data
        r = self.satData.copy()
    
        # Group by longitude and latitude
        grouped_incidences = r.groupby(["longitude", "latitude"]).size().reset_index(name='count')
    
        lon = grouped_incidences["longitude"].to_numpy()
        #lon = np.round(lon, decimals=2)
        lat = grouped_incidences['latitude'].to_numpy()
        #lat = np.round(lat, decimals=2)
        field = grouped_incidences['count'].to_numpy()
        
        self.get_plot(lon, lat, field, roi, title, cbar_title, color, levels)
        
        return grouped_incidences
        
    
class statAnalisisData(csv_from_sat):
    
    variogramModels = {
        "Gaussian": gs.Gaussian,
        "Exponential": gs.Exponential,
        "Matern": gs.Matern,
        "Integral": gs.Integral,
        "Stable": gs.Stable,
        "Rational": gs.Rational,
        "Cubic" : gs.Cubic,
        "Linear" : gs.Linear,
        "Circular": gs.Circular,
        "Spherical": gs.Spherical,
        "HyperSpherical": gs.HyperSpherical,
        "SuperSpherical": gs.SuperSpherical,
        "JBessel": gs.JBessel,
    }
    
    def __init__(self, satData):
        csv_from_sat.__init__(self, satData)
        self.scores = None
        self.x = None
        self.y = None
        self.field = None
            
    def getVariogramScores(self, x, y, field, graph=False):
        
        self.x = x
        self.y = y
        self.field = field
        bins = np.arange(0,50,1)/50000
        bin_center, gamma=gs.vario_estimate((x,y),field,bins,latlon=True)
        scores = {}
        
        # plot the estimated variogram
        if graph:
            plt.scatter(bin_center, gamma, color="k", label="data")
            ax = plt.gca()
        # fit all models to the estimated variogram
        for model in self.variogramModels:
            fit_model = self.variogramModels[model](dim=2,latlon=True, rescale=gs.EARTH_RADIUS)
            para, pcov, r2 = fit_model.fit_variogram(bin_center, gamma, return_r2=True,nugget=False)#sill=np.var(field))
            scores[model] = r2
            if graph:
                fit_model.plot(x_max=max(bin_center), ax=ax)
        
        if graph:
            plt.title('variograma')
            plt.show()
        self.scores = scores    
            
        return scores
    
    def sortScores(self, scores):    
        
        ranking = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        print("RANKING by Pseudo-r2 score")
        for i, (model, score) in enumerate(ranking, 1):
            print(f"{i:>6}. {model:>15}: {score:.5}")

        return ranking
    
    def getBestVariogram(self, graph=False):
        
        if self.scores == None:
            raise Exception('scores not found, please get variogram scores')
        ranking = self.sortScores(self.scores)
        model = ranking[0][0]
        fit_model = self.variogramModels[model](dim=2,latlon=True, rescale=gs.EARTH_RADIUS)
        bins = np.arange(0,50,1)/9000
        bin_center, gamma = gs.vario_estimate((self.x, self.y), self.field, bins, latlon=True)
        fit_model.fit_variogram(bin_center, gamma, nugget=False)
        
        if graph:
            ax = fit_model.plot(x_max=max(bin_center))
            ax.scatter(bin_center,gamma, color="k", label="data")
            plt.show()
        
        model_k = fit_model
        
        
        return model_k
    
    
    
    def get_random_sample(self, xr, yr, fieldr, sample_size):
        
        ind = np.random.choice(len(xr),int(len(xr)*sample_size)) # Seecciona aleatoriamente el indice del 10% de los datos

        x_sample = xr[ind]
        y_sample = yr[ind]
        field_sample = fieldr[ind]
        
        return x_sample, y_sample, field_sample
    
    def partition_geometry(self, limits, div_factor, step):
        
        cond_xs = []
        cond_ys = []
        cond_vals = []
        gridxs = []
        gridys = []
        
        xmax = limits[0]
        ymax = limits[1]
        xmin = limits[2]
        ymin = limits[3]
        
        divs = ceil(sqrt(len(self.xr)/div_factor))
        
        print(f"partitioning geometry into {divs+divs} subdivitions...")
        
        x_len = (xmax - xmin) / divs
        y_len = (ymax - ymin) / divs


        for i in range(divs):
          indx = np.argwhere((xmin+x_len*i) <= self.xr)
          indx2 = np.argwhere(self.xr < (xmin+(x_len*(i+1))))
          for j in range(divs):
            indy = np.argwhere((ymin+y_len*j) <= self.yr)
            indy2 = np.argwhere(self.yr < ymin+(y_len*(j+1)))
            ind = indx[np.in1d(indx, indx2)]
            ind = ind[np.in1d(ind, indy)]
            ind = ind[np.in1d(ind, indy2)]
            cond_xs.append(self.xr[ind])
            cond_ys.append(self.yr[ind])
            cond_vals.append(self.fieldr[ind])
            gridxs.append(np.arange(xmin+x_len*i, xmin+(x_len*(i+1)), step))
            gridys.append(np.arange(ymin+y_len*j, ymin+(y_len*(j+1)), step))
            
            
        return cond_xs, cond_ys, cond_vals, gridxs, gridys
    
    def get_interpolation(self, cond_xs, cond_ys, cond_vals, gridxs, gridys, model_k):
        
        field_data = []
        variance_field_data = []
        x_data = [] 
        y_data = []
        print("Interpolating data...")
        for i in range(len(cond_xs)):
            print(f"interpolating partition {i+1}")
            OK2 = gs.krige.Ordinary(model_k, [cond_xs[i], cond_ys[i]], cond_vals[i], exact=True)
            
            # to make more than 1 partitions in to an entire partition:
            #OK2.structured([gridxs[i], gridys[i]])
            
            # To evaluate in a specific points:
            z, w = OK2((gridxs[i], gridys[i]))
            xx, yy = np.meshgrid(gridys[i], gridxs[i])
            x_data.append(xx)
            y_data.append(yy)
            
            # entire partition:
            #z = OK2.field.copy()
            #w=OK2.krige_var.copy()
            field_data.append(z)
            variance_field_data.append(w)
          
        return x_data, y_data, field_data, variance_field_data
          
    def clip_subdivition(self, xx, yy, field_data, variance_field_data, specific_region_poligon_1, specific_region_poligon_2):
        
        
        for i in range(np.shape(field_data)[0]):
            for j in range(np.shape(field_data)[1]):
                
                point = Point(xx[i,j],yy[i,j])
                
                if not specific_region_poligon_1.contains(point)[0]:
                    field_data[i, j] = np.nan
                    variance_field_data[i, j] = np.nan
                 
                if not specific_region_poligon_2.contains(point)[0]:
                    field_data[i, j] = np.nan
                    variance_field_data[i, j] = np.nan
                
        return field_data, variance_field_data
        
    
    def get_image_from_files(self, directory, regions):
        
        field_divs_data = os.listdir(directory+"/field")
        variance_divs_data = os.listdir(directory+"/variance")
        x_divs_data = os.listdir(directory+"/x")
        y_divs_data = os.listdir(directory+"/y")
        for region in regions.values():
            
            resultados = [s for s in field_divs_data if region in s]
            resultados.sort()
            print(resultados)
        
        #datos = np.genfromtxt(ruta_al_archivo, delimiter=',')
        