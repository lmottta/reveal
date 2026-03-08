import os
from PIL import Image

def generate_favicon():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "..", "backend")
    img_dir = os.path.join(backend_dir, "static", "img")
    static_dir = os.path.join(backend_dir, "static")
    
    source_path = os.path.join(img_dir, "background.png")
    dest_path = os.path.join(static_dir, "favicon.ico")
    
    if not os.path.exists(source_path):
        print(f"Error: Source image not found at {source_path}")
        return

    try:
        img = Image.open(source_path)
        # Convert to RGBA if not already
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # Create favicon with multiple sizes
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
        img.save(dest_path, format='ICO', sizes=icon_sizes)
        print(f"Favicon generated successfully at {dest_path}")
        
    except ImportError:
        print("Error: Pillow library not found. Please install it with: pip install Pillow")
    except Exception as e:
        print(f"Error generating favicon: {str(e)}")

if __name__ == "__main__":
    generate_favicon()
