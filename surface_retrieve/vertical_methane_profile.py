

def read_grib_file(grib_file_path):
    """
    Read and display information about a GRIB file.
    
    Parameters:
    grib_file_path (str): Path to the GRIB file
    """
    if not os.path.exists(grib_file_path):
        print(f"Error: File '{grib_file_path}' not found!")
        return
    
    try:
        # Open the GRIB file
        print(f"Opening GRIB file: {grib_file_path}")
        grbs = pygrib.open(grib_file_path)
        
        # Get the number of messages (fields) in the file
        message_count = len(grbs)
        print(f"Number of messages/fields in file: {message_count}")
        
        # Print information about all messages
        print("\n--- GRIB File Structure ---")
        print("Index | Parameter | Level | Date/Time | Grid Info")
        print("-" * 70)
        
        # Loop through all messages
        for i, grb in enumerate(grbs):
            # Get basic information about each message
            param_name = grb.shortName if hasattr(grb, 'shortName') else 'N/A'
            level_type = grb.levelType if hasattr(grb, 'levelType') else 'N/A'
            level_val = grb.level if hasattr(grb, 'level') else 'N/A'
            level_info = f"{level_type} {level_val}" if level_type != 'N/A' else 'N/A'
            
            date_time = f"{grb.dataDate} / {grb.dataTime}" if hasattr(grb, 'dataDate') else 'N/A'
            
            # Grid info
            if hasattr(grb, 'Ni') and hasattr(grb, 'Nj'):
                grid_info = f"{grb.Ni}x{grb.Nj}"
            else:
                grid_info = 'N/A'
            
            print(f"{i+1:3d} | {param_name:10s} | {level_info:15s} | {date_time:15s} | {grid_info}")
        
        # Rewind the iterator
        grbs.rewind()
        
        # Get and display detailed information about the first message
        if message_count > 0:
            print("\n--- Detailed Information for First Message ---")
            first_message = grbs[1]  # GRIB indexing starts at 1
            
            # Display all available keys
            print("\nAvailable keys in the first message:")
            for key in first_message.keys():
                try:
                    value = first_message[key]
                    print(f"{key}: {value}")
                except:
                    print(f"{key}: <Unable to display value>")
            
            # Get data array and basic statistics
            data, lats, lons = first_message.data()
            print("\nData array shape:", data.shape)
            print(f"Data range: {data.min()} to {data.max()}")
            print(f"Data mean: {data.mean()}")
            print(f"Data standard deviation: {data.std()}")
            
            # Plot the first field
            plot_grib_field(first_message, data, lats, lons)
        
        # Close the file
        grbs.close()
        
    except Exception as e:
        print(f"Error reading GRIB file: {str(e)}")

def plot_grib_field(grb, data, lats, lons):
    """
    Create a simple plot of a GRIB field.
    
    Parameters:
    grb (pygrib.message): GRIB message
    data (numpy.ndarray): Data array
    lats (numpy.ndarray): Latitudes
    lons (numpy.ndarray): Longitudes
    """
    try:
        param_name = grb.shortName if hasattr(grb, 'shortName') else 'Unknown'
        param_units = grb.units if hasattr(grb, 'units') else ''
        level_info = f"{grb.levelType} {grb.level}" if hasattr(grb, 'levelType') else ''
        title = f"{param_name} ({param_units}) at {level_info}"
        
        # Create figure
        plt.figure(figsize=(12, 8))
        
        # Create a Basemap instance for geographic plotting
        m = Basemap(projection='cyl', llcrnrlat=np.min(lats), urcrnrlat=np.max(lats),
                    llcrnrlon=np.min(lons), urcrnrlon=np.max(lons), resolution='l')
        
        # Draw coastlines, countries, and states
        m.drawcoastlines()
        m.drawcountries()
        
        # Convert lat/lon to map coordinates
        x, y = m(*np.meshgrid(lons, lats))
        
        # Plot the data
        cs = m.pcolormesh(x, y, data, shading='auto', cmap='viridis')
        
        # Add colorbar and title
        cbar = m.colorbar(cs, location='bottom', pad="10%")
        cbar.set_label(param_units)
        plt.title(title)
        
        # Save the plot
        output_filename = 'grib_field_plot.png'
        plt.savefig(output_filename)
        print(f"\nPlot saved as: {output_filename}")
        plt.close()
        
    except Exception as e:
        print(f"Error creating plot: {str(e)}")

if __name__ == "__main__":
    # Check if file path is provided as command line argument
    if len(sys.argv) > 1:
        grib_file_path = sys.argv[1]
    else:
        # If no file path provided, ask for it
        grib_file_path = input("Enter the path to the GRIB file: ")
    
    read_grib_file(grib_file_path)