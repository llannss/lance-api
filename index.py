from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Simple NVIDIA GPU API",
    description="A beginner-friendly REST API containing information about cars.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GPU DATA
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

# HOME
@app.get("/")
def home():
    return {
        "message": "Welcome to the NVIDIA GPU API!",
        "endpoints": [
            "/gpus",
            "/gpus/{id}",
            "/gpus/search"
        ]
    }

# GET ALL GPUS
@app.get("/gpus")
def get_gpus():
    return {
        "count": len(gpus),
        "gpus": gpus
    }

# SEARCH GPUS
@app.get("/gpus/search")
def search_gpus(q: str = Query(..., min_length=1)):
    q = q.lower()

    results = []

    for gpu in gpus:
        searchable_text = (
            f"{gpu['brand']} "
            f"{gpu['model']} "
            f"{gpu['architecture']} "
            f"{gpu['vram']}"
        ).lower()

        if q in searchable_text:
            results.append(gpu)

    return {
        "query": q,
        "count": len(results),
        "results": results
    }

# GET ONE GPU
@app.get("/gpus/{gpu_id}")
def get_gpu(gpu_id: int):

    for gpu in gpus:
        if gpu["id"] == gpu_id:
            return gpu

    raise HTTPException(
        status_code=404,
        detail="GPU not found."
    )


