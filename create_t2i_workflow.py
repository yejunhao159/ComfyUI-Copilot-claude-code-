#!/usr/bin/env python3
"""
Create a simple text-to-image workflow using update_workflow tool.
"""

import asyncio
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.agentx.mcp_tools.comfyui_tools import execute_comfyui_tool, _ensure_tools_registered

# Simple text-to-image workflow in ComfyUI API format
TEXT_TO_IMAGE_WORKFLOW = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "v1-5-pruned-emaonly.safetensors"
        }
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "beautiful landscape, mountains, sunset, high quality, detailed",
            "clip": ["1", 1]  # Link to CheckpointLoaderSimple CLIP output (index 1)
        }
    },
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "ugly, blurry, low quality, distorted",
            "clip": ["1", 1]  # Link to CheckpointLoaderSimple CLIP output (index 1)
        }
    },
    "4": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 512,
            "height": 512,
            "batch_size": 1
        }
    },
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 20,
            "cfg": 7.5,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["1", 0],      # Link to CheckpointLoaderSimple MODEL output (index 0)
            "positive": ["2", 0],   # Link to positive CLIPTextEncode output
            "negative": ["3", 0],   # Link to negative CLIPTextEncode output
            "latent_image": ["4", 0] # Link to EmptyLatentImage output
        }
    },
    "6": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["5", 0],   # Link to KSampler output
            "vae": ["1", 2]        # Link to CheckpointLoaderSimple VAE output (index 2)
        }
    },
    "7": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "ComfyUI",
            "images": ["6", 0]     # Link to VAEDecode output
        }
    }
}


async def main():
    """Create the text-to-image workflow."""
    print("Creating text-to-image workflow...")
    print(f"Workflow has {len(TEXT_TO_IMAGE_WORKFLOW)} nodes:")
    for node_id, node_data in TEXT_TO_IMAGE_WORKFLOW.items():
        print(f"  Node {node_id}: {node_data['class_type']}")

    print("\nCalling update_workflow tool...")

    # Ensure tools are registered
    _ensure_tools_registered()

    # Execute the update_workflow tool
    result = await execute_comfyui_tool("update_workflow", {
        "workflow_data": TEXT_TO_IMAGE_WORKFLOW
    })

    print("\nResult:")
    print(f"  Success: {result.get('success')}")
    print(f"  Node count: {result.get('node_count')}")
    print(f"  Message: {result.get('message')}")

    if result.get('nodes'):
        print("\nNodes in workflow:")
        for node in result.get('nodes', []):
            print(f"  - {node}")

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    print("\n=== Workflow created successfully! ===")
