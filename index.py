from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Simple NVIDIA GPU API",
    description="A beginner-friendly REST API containing NVIDIA GPU information.",
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
    },

    {
        "id": 6,
        "brand": "NVIDIA",
        "model": "GeForce RTX 5070",
        "architecture": "Blackwell",
        "vram": "12GB GDDR7",
        "cuda_cores": 6144,
        "memory_bus": "192-bit",
        "description": "A Blackwell GPU aimed at high-performance 1440p gaming."
    },
    {
        "id": 7,
        "brand": "NVIDIA",
        "model": "GeForce RTX 5060 Ti",
        "architecture": "Blackwell",
        "vram": "16GB GDDR7",
        "cuda_cores": 4608,
        "memory_bus": "128-bit",
        "description": "A mid-range Blackwell GPU available with high-capacity GDDR7 memory."
    },
    {
        "id": 8,
        "brand": "NVIDIA",
        "model": "GeForce RTX 5060",
        "architecture": "Blackwell",
        "vram": "8GB GDDR7",
        "cuda_cores": 3840,
        "memory_bus": "128-bit",
        "description": "A mainstream Blackwell GPU designed for modern 1080p gaming."
    },

    {
        "id": 9,
        "brand": "NVIDIA",
        "model": "GeForce RTX 4070 Ti SUPER",
        "architecture": "Ada Lovelace",
        "vram": "16GB GDDR6X",
        "cuda_cores": 8448,
        "memory_bus": "256-bit",
        "description": "A powerful Ada Lovelace GPU suitable for 1440p and 4K gaming."
    },
    {
        "id": 10,
        "brand": "NVIDIA",
        "model": "GeForce RTX 4070 SUPER",
        "architecture": "Ada Lovelace",
        "vram": "12GB GDDR6X",
        "cuda_cores": 7168,
        "memory_bus": "192-bit",
        "description": "An upgraded RTX 4070-class GPU focused on high-refresh-rate 1440p gaming."
    },
    {
        "id": 11,
        "brand": "NVIDIA",
        "model": "GeForce RTX 4070",
        "architecture": "Ada Lovelace",
        "vram": "12GB GDDR6X",
        "cuda_cores": 5888,
        "memory_bus": "192-bit",
        "description": "An efficient Ada Lovelace GPU designed primarily for 1440p gaming."
    },
    {
        "id": 12,
        "brand": "NVIDIA",
        "model": "GeForce RTX 4060 Ti",
        "architecture": "Ada Lovelace",
        "vram": "16GB GDDR6",
        "cuda_cores": 4352,
        "memory_bus": "128-bit",
        "description": "A mid-range Ada Lovelace GPU aimed at high-performance 1080p gaming."
    },
    {
        "id": 13,
        "brand": "NVIDIA",
        "model": "GeForce RTX 4060",
        "architecture": "Ada Lovelace",
        "vram": "8GB GDDR6",
        "cuda_cores": 3072,
        "memory_bus": "128-bit",
        "description": "A mainstream Ada Lovelace graphics card designed for efficient 1080p gaming."
    },

    {
        "id": 14,
        "brand": "NVIDIA",
        "model": "GeForce RTX 3090 Ti",
        "architecture": "Ampere",
        "vram": "24GB GDDR6X",
        "cuda_cores": 10752,
        "memory_bus": "384-bit",
        "description": "The flagship RTX 30-series GPU with 24GB of GDDR6X memory."
    },
    {
        "id": 15,
        "brand": "NVIDIA",
        "model": "GeForce RTX 3090",
        "architecture": "Ampere",
        "vram": "24GB GDDR6X",
        "cuda_cores": 10496,
        "memory_bus": "384-bit",
        "description": "A high-end Ampere GPU built for gaming, rendering, and demanding creative workloads."
    },
    {
        "id": 16,
        "brand": "NVIDIA",
        "model": "GeForce RTX 3080 Ti",
        "architecture": "Ampere",
        "vram": "12GB GDDR6X",
        "cuda_cores": 10240,
        "memory_bus": "384-bit",
        "description": "A high-end Ampere GPU designed for demanding 4K gaming."
    },
    {
        "id": 17,
        "brand": "NVIDIA",
        "model": "GeForce RTX 3080",
        "architecture": "Ampere",
        "vram": "10GB GDDR6X",
        "cuda_cores": 8704,
        "memory_bus": "320-bit",
        "description": "A popular Ampere graphics card designed for high-end gaming."
    },

    {
        "id": 18,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1660 Ti",
        "architecture": "Turing",
        "vram": "6GB GDDR6",
        "cuda_cores": 1536,
        "memory_bus": "192-bit",
        "description": "A Turing-based GTX graphics card designed for strong 1080p gaming."
    },
    {
        "id": 19,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1660 SUPER",
        "architecture": "Turing",
        "vram": "6GB GDDR6",
        "cuda_cores": 1408,
        "memory_bus": "192-bit",
        "description": "A popular GTX card offering solid performance for 1080p gaming."
    },
    {
        "id": 20,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1650 SUPER",
        "architecture": "Turing",
        "vram": "4GB GDDR6",
        "cuda_cores": 1280,
        "memory_bus": "128-bit",
        "description": "An entry-level Turing GPU designed for affordable 1080p gaming."
    }
    {
        "id": 21,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1650 SUPER",
        "architecture": "Turing",
        "vram": "4GB GDDR6",
        "cuda_cores": 1280,
        "memory_bus": "128-bit",
        "description": "An entry-level Turing GPU designed for affordable 1080p gaming."
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


