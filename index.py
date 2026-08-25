from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import re


app = FastAPI(
    title="Simple NVIDIA GPU API",
    description="A beginner-friendly REST API containing information about NVIDIA GPUs.",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# GPU DATA
# =========================================================

gpus = [
    {
        "id": 1,
        "brand": "NVIDIA",
        "model": "GeForce RTX 5090",
        "architecture": "Blackwell",
        "vram": "32GB GDDR7",
        "cuda_cores": 21760,
        "memory_bus": "512-bit",
        "description": "NVIDIA's flagship GeForce graphics card."
    },
    {
        "id": 2,
        "brand": "NVIDIA",
        "model": "GeForce RTX 5080",
        "architecture": "Blackwell",
        "vram": "16GB GDDR7",
        "cuda_cores": 10752,
        "memory_bus": "256-bit",
        "description": "A high-end Blackwell GPU designed for gaming and AI workloads."
    },
    {
        "id": 3,
        "brand": "NVIDIA",
        "model": "GeForce RTX 5070 Ti",
        "architecture": "Blackwell",
        "vram": "16GB GDDR7",
        "cuda_cores": 8960,
        "memory_bus": "256-bit",
        "description": "A high-performance GPU for gaming and creative workloads."
    },
    {
        "id": 4,
        "brand": "NVIDIA",
        "model": "GeForce RTX 4090",
        "architecture": "Ada Lovelace",
        "vram": "24GB GDDR6X",
        "cuda_cores": 16384,
        "memory_bus": "384-bit",
        "description": "A previous-generation flagship GeForce GPU."
    },
    {
        "id": 5,
        "brand": "NVIDIA",
        "model": "GeForce RTX 4080 SUPER",
        "architecture": "Ada Lovelace",
        "vram": "16GB GDDR6X",
        "cuda_cores": 10240,
        "memory_bus": "256-bit",
        "description": "A high-end Ada Lovelace GPU."
    }
]


# =========================================================
# SEARCH HELPER
# =========================================================

def normalize_text(text: str):
    """
    Converts:
        RTX 5090
        rtx-5090
        RTX5090

    into:
        rtx5090
    """
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def perform_search(query: str):
    query = query.strip()

    if not query:
        return []

    normalized_query = normalize_text(query)
    results = []

    for gpu in gpus:

        searchable_text = " ".join([
            str(gpu["id"]),
            gpu["brand"],
            gpu["model"],
            gpu["architecture"],
            gpu["vram"],
            str(gpu["cuda_cores"]),
            gpu["memory_bus"],
            gpu["description"]
        ])

        normalized_gpu = normalize_text(searchable_text)

        # Full normalized search
        if normalized_query in normalized_gpu:
            results.append(gpu)
            continue

        # Word-by-word search
        words = query.lower().split()

        if all(
            normalize_text(word) in normalized_gpu
            for word in words
        ):
            results.append(gpu)

    return results


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return {
        "message": "Welcome to the NVIDIA GPU API!",
        "version": "1.0.0",
        "endpoints": {
            "all_gpus": "/gpus",
            "search_query": "/gpus/search?q=rtx%205090",
            "search_path": "/gpus/search/rtx%205090",
            "gpu_by_id": "/gpus/1",
            "docs": "/docs"
        }
    }


# =========================================================
# GET ALL GPUS
# =========================================================

@app.get("/gpus")
def get_gpus():
    return {
        "count": len(gpus),
        "gpus": gpus
    }


# =========================================================
# SEARCH USING QUERY PARAMETER
#
# /gpus/search?q=rtx 5090
# =========================================================

@app.get("/gpus/search")
def search_gpus(
    q: str = Query(
        ...,
        min_length=1,
        description="Example: RTX 5090"
    )
):
    results = perform_search(q)

    return {
        "query": q,
        "count": len(results),
        "results": results
    }


# =========================================================
# SEARCH USING URL PATH
#
# /gpus/search/rtx 5090
# =========================================================

@app.get("/gpus/search/{query}")
def search_gpus_path(query: str):

    results = perform_search(query)

    return {
        "query": query,
        "count": len(results),
        "results": results
    }


# =========================================================
# GET GPU BY ID
#
# IMPORTANT:
# KEEP THIS BELOW THE SEARCH ROUTES
# =========================================================

@app.get("/gpus/{gpu_id}")
def get_gpu(gpu_id: int):

    for gpu in gpus:
        if gpu["id"] == gpu_id:
            return gpu

    raise HTTPException(
        status_code=404,
        detail=f"GPU with ID {gpu_id} not found."
    )
