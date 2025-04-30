# Backend code goes here
import sys
import os
from pathlib import Path
from fastapi import FastAPI

# --- Node Discovery Setup ---
# Calculate the project root directory (one level up from backend)
backend_dir = Path(__file__).parent
project_root = backend_dir.parent

# Add project root and core directory to sys.path
# This allows importing 'core' and 'nodes' packages
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "core")) # Needed if registry uses relative imports within core

# Check if 'nodes' directory exists
nodes_dir_path = project_root / "nodes"
if not nodes_dir_path.is_dir():
    print(f"Warning: Nodes directory not found at {nodes_dir_path}. Node discovery might fail.")
    # Optionally raise an error or log more prominently

# Attempt to import NodeRegistry only after setting up sys.path
try:
    from core.node.registry import NodeRegistry
    # Discover nodes immediately when the module is loaded
    # Note: This assumes 'nodes' is the correct package name/directory
    # Adjust the path relative to project_root if needed
    print(f"Starting node discovery from: {nodes_dir_path}")
    NodeRegistry.discover_nodes(nodes_package_dir=str(nodes_dir_path))
    print(f"Node discovery finished. Registered nodes: {NodeRegistry.list_node_types()}")
except ImportError as e:
    print(f"Error importing NodeRegistry or discovering nodes: {e}")
    # Handle the error appropriately, maybe raise it or define a fallback
    NodeRegistry = None # Indicate failure
except Exception as e:
    print(f"An unexpected error occurred during node discovery setup: {e}")
    NodeRegistry = None

# --- FastAPI App ---
app = FastAPI()

# Placeholder for available node types
@app.get("/api/nodes/available")
async def get_available_nodes():
    if NodeRegistry is None:
        return {"error": "Node discovery failed during server startup."}

    available_nodes_metadata = NodeRegistry.list_available_nodes()
    node_list = []
    for node_type, metadata in available_nodes_metadata.items():
        # Use node_type (class name) for label, and lowercase for id
        # Set category to 'default' for now
        node_list.append({
            "id": node_type.lower(), # Simple ID generation
            "type": "default", # TODO: Enhance type detection later
            "label": node_type # Use ClassName as label
        })
    return node_list

# Placeholder root endpoint
@app.get("/")
async def read_root():
    return {"message": "TSAP Backend is running"} 