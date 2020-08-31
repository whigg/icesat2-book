# Data wrangling

This notebook loads the different datasets used in the analysis into a single NETCDF4 file, with descriptive attributes maintained for each dataset. The datasets used in this notebook are listed below. The output file is accessible in the google bucket for this jupyter book and loaded in each notebook. 
 
**Input**:
 - [ICESat-2 monthly gridded sea ice data](https://icesat-2.gsfc.nasa.gov/sea-ice-thickness-data)
 - [Monthly NSIDC sea ice concentration data](https://nsidc.org/data/g02202)
 - [NSIDC region mask](https://nsidc.org/data/polar-stereo/tools_masks.html#region_masks) and [coordinate](https://nsidc.org/data/polar-stereo/tools_geo_pixel.html) tools (psn25 v3)
 - [ERA 5 climate renanalysis data](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels-monthly-means?tab=overview)
 - [PIOMAS mean monthly ice thickness](http://psc.apl.uw.edu/research/projects/arctic-sea-ice-volume-anomaly/)
 - [NSIDC sea ice motion vectors](https://nsidc.org/data/nsidc-0116)
     

**Output**: 
 - NETCDF4 file 

```{note}
This notebook is **NOT** configured to run in Google Colab. This file generated by this notebook is also provided google bucket for this book. [Click here](https://storage.googleapis.com/icesat2-book-data/icesat2-book-dataset.nc) to download the dataset.
```

## Import notebook dependencies

import os
import numpy as np
import numpy.ma as ma
import xarray as xr
import pandas as pd
import scipy.interpolate
import pyproj
from datetime import date

# Ignore warnings in the notebook to improve display
# You might want to remove this when debugging/writing new code
import warnings
warnings.filterwarnings('ignore')

#import utils function 
if 'utils.py' not in os.listdir(os.getcwd()): 
    !gsutil cp gs://icesat2-book-data/utils.py ./
import utils

## Define filepaths
Define filepaths to data on your local machine

#path to data directory
localDirectory = '/Users/nicolekeeney/Desktop/notebook_data/'

#path to monthly gridded ICESat-2 data
IS2_path = localDirectory + 'cpom_thickness/' 

#path to NSIDC weekly sea ice concentration data
SIC_path = localDirectory + 'SIC/'

#path to NSIDC region mask for the Arctic
regionMask_path = localDirectory + 'regionMask/'

#path to ERA5 climate reanalysis data 
ERA5_filename = 'adaptor.mars.internal-1593801470.6369596-17327-1-b6ff618a-cfd2-4a13-9eb8-87c048affbf2.nc'
ERA5_path = localDirectory  + 'ERA5/' + ERA5_filename

#path to PIOMAS data
PIOMAS_path = localDirectory + 'PIOMAS_monthly_thickness/'

#path to NSIDC sea ice drift data 
drift_path = localDirectory + 'drifts/'

## Load in data
Data is loaded into notebook using functions from the utils.py script 

Set desired date range for data

startYear = 2018
endYear = 2020
winters = utils.getWinterDateRange(startYear, endYear) #get date range for winter 18-19 and winter 19-20

### ICESat-2 monthly gridded sea ice data

#load dataset 
is2 = utils.getIS2Data(IS2_path, winters)

#drop projection variable 
is2 = is2.drop('projection')

#get lat and lon
is2Lats = is2.latitude.isel(time = 0).values
is2Lons = is2.longitude.isel(time = 0).values
is2LonsAttrs = is2.longitude.attrs 
is2LatsAttrs = is2.latitude.attrs

#assign lat and lon as coordinates to dataset
is2 = is2.assign_coords(coords = {'latitude': (('x','y'), is2Lats), 'longitude': (('x','y'), is2Lons)})

### NSIDC sea ice concentration data 

sic = utils.getSICData(SIC_path, winters)

#### Clean data
Clean data by removing flagged data and filling the pole hole. We assume concentration is 100% within the pole hole because we are only looking at winter data. 

#remove flagged data 
sic_monthly_cdr = sic['seaice_conc_monthly_cdr'].where(sic['seaice_conc_monthly_cdr'] < 0)

#fill pole hole as 100% concentration
sic_monthly_cdr = sic['seaice_conc_monthly_cdr'].where(sic['latitude'] < 88, 1)

#reassign variable
sic = sic.assign(seaice_conc_monthly_cdr = sic_monthly_cdr)

#reassign dimensions 
seaice_conc_monthly_cdr = xr.DataArray(data = sic['seaice_conc_monthly_cdr'], dims = ['time', 'x', 'y'], coords = {'time': winters, 'latitude': (('x','y'), is2Lats), 'longitude': (('x','y'), is2Lons)}) 

#attributes from entire NSIDC data to maintain
desiredSICAttrs = ['title', 'references', 'contributor_name', 'license', 'summary'] #attributes to maintain from entire sea ice concentration dataset
SICDatasetAttrs = {x:sic.attrs[x] for x in desiredSICAttrs}
seaice_conc_monthly_cdr = seaice_conc_monthly_cdr.assign_attrs(SICDatasetAttrs)

#add to is2 dataset 
is2['seaice_conc_monthly_cdr'] = seaice_conc_monthly_cdr

### NSIDC region mask for the Arctic data

regionMask, maskLons, maskLats = utils.getRegionMask(regionMask_path)

#### Define descriptive information
These variables will be used later for creating the dataset. 

#coords and attributes for Region Mask
regionMaskCoords = {'region_mask': (('x','y'), regionMask)}
regionMaskKeys = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20, 21])
regionMaskLabels = np.array(['non-region oceans', 'Sea of Okhotsk and Japan','Bering Sea','Hudson Bay','Gulf of St. Lawrence',
                    'Baffin Bay, Davis Strait & Labrador Sea','Greenland Sea', 'Barents Seas','Kara Sea','Laptev Sea','East Siberian Sea',
                    'Chukchi Sea','Beaufort Sea','Canadian Archipelago','Arctic Ocean','Land','Coast'])
regionMaskAttrs = {'description': 'NSIDC region mask for the Arctic', 'keys': regionMaskKeys, 'labels' : regionMaskLabels, 'note': 'keys and labels ordered to match by index'}

### ERA5 climate reanalysis data 

ERA5 = xr.open_dataset(ERA5_path)

#### Clean data
Clean data by removing unneccessary variables and converting temperature to Celcius

#remove unneeded expver variable. 
#for more info on the exper variable, see https://confluence.ecmwf.int/pages/viewpage.action?pageId=173385064
ERA5 = ERA5.sel(expver = 1)
ERA5 = ERA5.drop('expver')

#select data from past two winters 
ERA5 = ERA5.sel(time = utils.getWinterDateRange(2018, 2020))
ERA5 = ERA5.assign_coords(time = utils.getWinterDateRange(2018, 2020))

#convert t2m temp to celcius 
tempCelcius = ERA5['t2m'] - 283.15
tempCelcius.attrs['units'] = 'C' #change units attribute to C (Celcius)
tempCelcius.attrs['long_name'] = '2 meter temperature'
ERA5 = ERA5.assign(t2m = tempCelcius) #add to dataset as a new data variable

#add descriptive attributes 
ERA5.attrs = {'description': 'era5 monthly averaged data on single levels from 1979 to present', 
              'website': 'https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels-monthly-means?tab=overview', 
              'contact': 'copernicus-support@ecmwf.int',
             'citation': 'Copernicus Climate Change Service (C3S) (2017): ERA5: Fifth generation of ECMWF atmospheric reanalyses of the global climate . Copernicus Climate Change Service Climate Data Store (CDS), July 2020. https://cds.climate.copernicus.eu/cdsapp#!/home'}

#restrict ERA5 data to the Arctic 
ERA5 = ERA5.where(ERA5.latitude > 50)

### PIOMAS sea ice thickness data 

piomasData = utils.getPIOMASData(PIOMAS_path, startYear = 1978, endYear = 2020)

### NSIDC sea ice drift data 

drifts = utils.getDriftData(drift_path)

Restrict data to winter months

drifts = drifts.sel(time = winters)

## Interpolate missing ICESat-2 data 
Interpolate missing ICESat-2 data using the [scipy.griddata.interpolate](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.griddata.html) function and add as data variables to the dataset. Because ICESat-2 doesn't provide full monthly coverage, interpolating fills missing grid cells with a best guess based on surrounding data. This helps avoid sampling biases when performing time series analyses, with the cavaet that this interpolation method is subjective. 

#list of variables to interpolate
IS2VarList = ['ice_type','ice_thickness','snow_depth','freeboard','ice_thickness_unc','snow_density','ice_density']

#go through variables in list and add as new data variables to ICESat-2 dataset
for varStr in IS2VarList:
    
    #empty list to store monthly interpolated data 
    varFilled = []
    
    for month in range(len(is2.time)): 
        #current month of data 
        monthlyVar = is2[varStr].values[month]
        
        #additional condition for interpolating ice thickness
        if varStr == 'ice_thickness': 
            #if var is ice_thickness_int, set ice_thickness to zero if ice_thickness is NaN and sea ice concentration < 15%
            monthlyVar[seaice_conc_monthly_cdr.values[month] <= 0.15] = 0
        
        #conditions for cells to interpolate
        monthlyVar = ma.masked_where((np.isnan(monthlyVar)) & (regionMask != 20) & (regionMask != 14) & (seaice_conc_monthly_cdr.values[month] > 0.15), monthlyVar)
        
        #append interpolated data to list 
        varFilled.append(scipy.interpolate.griddata((is2Lons[~monthlyVar.mask], is2Lats[~monthlyVar.mask]), 
                    monthlyVar[~monthlyVar.mask].flatten(),(is2Lons, is2Lats), method = 'nearest'))
    
    #convert varFilled to a DataArray object 
    varFilledDataArray = xr.DataArray(data = varFilled, dims = ['time', 'x', 'y'], attrs = is2[varStr].attrs)
    varFilledDataArray.attrs['note'] = 'interpolated from original data'
    
    #add as new data variable to ICESat-2 dataset
    is2[varStr + '_filled'] = varFilledDataArray

### Add descriptive attributes & coordinates to all ICESat-2 variables

#assign ICESat-2 dataset attributes to all variables 
for var in is2.data_vars:
    is2[var] = is2[var].assign_attrs(is2.attrs)

#drop lat and lon as data variables and add as coordinate values 
is2 = is2.assign_coords(coords = {'latitude': (('x','y'), is2Lats), 'longitude': (('x','y'), is2Lons)})

## Regrid additional datasets to ICESat-2 grid 
In order to merge ERA5 and PIOMAS data to the same dataset as ICESat-2, it needs to be on the same grid. 

### Define regridding function 
This function will grid data to the ICESat-2 grid using the scipy.interpolate.griddata function

def regridToICESat2(dataArrayNEW, xptsNEW, yptsNEW, xptsIS2, yptsIS2):  
    """ Regrid new data to ICESat-2 grid 
    
    Args: 
        dataArrayNEW (xarray DataArray): DataArray to be gridded to ICESat-2 grid 
        xptsNEW (numpy array): x-values of dataArrayNEW projected to ICESat-2 map projection 
        yptsNEW (numpy array): y-values of dataArrayNEW projected to ICESat-2 map projection 
        xptsIS2 (numpy array): ICESat-2 longitude projected to ICESat-2 map projection
        yptsIS2 (numpy array): ICESat-2 latitude projected to ICESat-2 map projection
    
    Returns: 
        gridded (numpy array): data regridded to ICESat-2 map projection
    
    """
    gridded = []
    for i in range(len(dataArrayNEW.values)): 
        monthlyGridded = scipy.interpolate.griddata((xptsNEW.flatten(),yptsNEW.flatten()), dataArrayNEW.values[i].flatten(), (xptsIS2, yptsIS2), method = 'nearest')
        gridded.append(monthlyGridded)
        utils.progressBar(i, len(dataArrayNEW.values))
    return np.array(gridded)

### Regrid ERA5 data

#### Choose data variables of interest 
ERA5 provides climate reananalysis data for many different variables. Here, choose data variables to maintain in the final gridded data product. 

ERA5Vars = ['t2m','msdwlwrf']
print('chosen variables: ' + '%s' % ', '.join(map(str, [ERA5[var].attrs['long_name'] for var in ERA5Vars])))

#### Regrid ERA5 data & add to ICESat-2 dataset

#map projection from ICESat-2 data (can be viewed in is2.projection.attrs['srid'])
IS2_proj = 'EPSG:3411'

#initialize map projection and project data to it
mapProj = pyproj.Proj("+init=" + IS2_proj)
xptsERA, yptsERA = mapProj(*np.meshgrid(ERA5.longitude.values, ERA5.latitude.values))
xptsIS2, yptsIS2 = mapProj(is2Lons, is2Lats)

#grid data
for var in ERA5Vars: 
    #regrid data by calling function
    ERA5gridded = regridToICESat2(ERA5[var], xptsERA, yptsERA, xptsIS2, yptsIS2)
    
    #create xarray DataArray object with descriptive coordinates 
    ERAArray = xr.DataArray(data = ERA5gridded, dims = ['time', 'x', 'y'], coords = {'latitude': (('x','y'), is2Lats), 'longitude': (('x','y'), is2Lons)})
    ERAArray.attrs = ERA5[var].attrs
    ERAArray = ERAArray.assign_attrs(ERA5.attrs)

    #add to ICESat-2 dataset
    is2[var] = ERAArray

### Regrid PIOMAS data 

#project data to ICESat-2 map projection
xptsPIO, yptsPIO = mapProj(piomasData.longitude.values, piomasData.latitude.values)

#regrid data by calling function
PIOgridded = regridToICESat2(piomasData, xptsPIO, yptsPIO, xptsIS2, yptsIS2)

#create xarray DataArray object with descriptive coordinates 
PIOArray = xr.DataArray(data = PIOgridded, dims = ['time', 'x', 'y'], coords = {'latitude': (('x','y'), is2Lats), 'longitude': (('x','y'), is2Lons)})
PIOArray = PIOArray.assign_coords(time = piomasData.time.values)
PIOArray = PIOArray.assign_attrs(piomasData.attrs)

### Regrid NSIDC sea ice drift data

#project data to ICESat-2 map projection
xptsDRIFTS, yptsDRIFTS = mapProj(drifts.longitude.values[0], drifts.latitude.values[0])

for var in ['drifts_uT', 'drifts_vT']: 
    #regrid data by calling function
    driftsGridded = regridToICESat2(drifts[var], xptsDRIFTS, yptsDRIFTS, xptsIS2, yptsIS2)
    
    #create xarray DataArray object with descriptive coordinates 
    driftsArray = xr.DataArray(data = driftsGridded, dims = ['time', 'x', 'y'], coords = {'latitude': (('x','y'), is2Lats), 'longitude': (('x','y'), is2Lons)})
    driftsArray.attrs = drifts[var].attrs
    driftsArray = driftsArray.assign_attrs(drifts.attrs)

    #add to ICESat-2 dataset
    is2[var] = driftsArray

### Save regridded PIOMAS file to local directory
Add region mask as descriptive coordinates to the PIOMAS regridded DataArray and save file to local directory

#add region mask as coordinate to dataset
piomas_to_save = PIOArray.assign_coords(coords = regionMaskCoords)

#add descriptive attributes 
piomas_to_save.region_mask.attrs = regionMaskAttrs

#create a dataset
piomas_to_save = xr.Dataset(data_vars = {'PIOMAS_ice_thickness': piomas_to_save})

#save to local directory as NETCDF4 file 
filename = 'piomas-regridded-data.nc'
piomas_to_save.to_netcdf(path = localDirectory + filename, format = 'NETCDF4', mode = 'w')
print('File ' + '"%s"' % filename + ' saved to directory ' + '"%s"' % localDirectory)

### Add winter regridded PIOMAS data to ICESat-2 dataset

#restrict data to same time period as ICESat-2
PIOArray = PIOArray.sel(time = winters)

#add to ICESat-2 dataset
is2['PIOMAS_ice_thickness'] = PIOArray

## Compile datasets into a single Dataset 

#add region mask as coordinate to dataset
is2 = is2.assign_coords(coords = regionMaskCoords)

#add descriptive attributes 
is2.region_mask.attrs = regionMaskAttrs
is2.longitude.attrs = is2LonsAttrs
is2.latitude.attrs = is2LatsAttrs
is2.attrs = {'description':'data used in nicolejkeeney ICESat-2 jupyter book', 'note': 'see individual data variables for references', 'creation date': str(date.today())}

print(is2)

## Save dataset to your local machine 
We will use this dataset in other notebooks to plot and analyze the data. 

filename = 'icesat2-book-winter-data.nc'
is2.to_netcdf(path = localDirectory + filename, format = 'NETCDF4', mode = 'w')
print('File ' + '"%s"' % filename + ' saved to directory ' + '"%s"' % localDirectory)
is2.close()