
import h5py
import json

def patch_h5_config(filepath):
    print(f"Patching {filepath}...")
    with h5py.File(filepath, 'r+') as f:
        if 'model_config' not in f.attrs:
            print("No model_config found in attributes.")
            return
            
        config_str = f.attrs['model_config']
        if isinstance(config_str, bytes):
            config_str = config_str.decode('utf-8')
            
        config = json.loads(config_str)
        
        # Traverse layers and remove time_major
        modified = False
        if 'config' in config and 'layers' in config['config']:
            for layer in config['config']['layers']:
                if 'config' in layer and 'time_major' in layer['config']:
                    print(f"Removing 'time_major' from layer: {layer.get('class_name')}")
                    del layer['config']['time_major']
                    modified = True
                    
        if modified:
            f.attrs['model_config'] = json.dumps(config).encode('utf-8')
            print("Successfully patched model_config.")
        else:
            print("No 'time_major' argument found to remove.")

if __name__ == "__main__":
    patch_h5_config("lstm_model.h5")
