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
        "power": "575W",
        "base_clock": "2.01 GHz",
        "boost_clock": "2.41 GHz",
        "recommended_psu": "1000W",
        "release_date": "January 30, 2025",
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
        "power": "360W",
        "base_clock": "2.30 GHz",
        "boost_clock": "2.62 GHz",
        "recommended_psu": "850W",
        "release_date": "January 30, 2025",
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
        "power": "300W",
        "base_clock": "2.30 GHz",
        "boost_clock": "2.45 GHz",
        "recommended_psu": "750W",
        "release_date": "February 20, 2025",
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
        "power": "450W",
        "base_clock": "2.23 GHz",
        "boost_clock": "2.52 GHz",
        "recommended_psu": "850W",
        "release_date": "October 12, 2022",
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
        "power": "320W",
        "base_clock": "2.29 GHz",
        "boost_clock": "2.55 GHz",
        "recommended_psu": "750W",
        "release_date": "January 31, 2024",
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
        "power": "250W",
        "base_clock": "2.33 GHz",
        "boost_clock": "2.51 GHz",
        "recommended_psu": "650W",
        "release_date": "March 5, 2025",
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
        "power": "180W",
        "base_clock": "2.41 GHz",
        "boost_clock": "2.57 GHz",
        "recommended_psu": "600W",
        "release_date": "April 16, 2025",
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
        "power": "145W",
        "base_clock": "2.28 GHz",
        "boost_clock": "2.50 GHz",
        "recommended_psu": "550W",
        "release_date": "May 19, 2025",
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
        "power": "285W",
        "base_clock": "2.34 GHz",
        "boost_clock": "2.61 GHz",
        "recommended_psu": "700W",
        "release_date": "January 24, 2024",
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
        "power": "220W",
        "base_clock": "1.98 GHz",
        "boost_clock": "2.48 GHz",
        "recommended_psu": "650W",
        "release_date": "January 17, 2024",
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
        "power": "200W",
        "base_clock": "1.92 GHz",
        "boost_clock": "2.48 GHz",
        "recommended_psu": "650W",
        "release_date": "April 13, 2023",
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
        "power": "165W",
        "base_clock": "2.31 GHz",
        "boost_clock": "2.54 GHz",
        "recommended_psu": "550W",
        "release_date": "July 18, 2023",
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
        "power": "115W",
        "base_clock": "1.83 GHz",
        "boost_clock": "2.46 GHz",
        "recommended_psu": "550W",
        "release_date": "June 29, 2023",
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
        "power": "450W",
        "base_clock": "1.56 GHz",
        "boost_clock": "1.86 GHz",
        "recommended_psu": "850W",
        "release_date": "March 29, 2022",
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
        "power": "350W",
        "base_clock": "1.40 GHz",
        "boost_clock": "1.70 GHz",
        "recommended_psu": "750W",
        "release_date": "September 24, 2020",
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
        "power": "350W",
        "base_clock": "1.37 GHz",
        "boost_clock": "1.67 GHz",
        "recommended_psu": "750W",
        "release_date": "June 3, 2021",
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
        "power": "320W",
        "base_clock": "1.44 GHz",
        "boost_clock": "1.71 GHz",
        "recommended_psu": "750W",
        "release_date": "September 17, 2020",
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
        "power": "120W",
        "base_clock": "1.50 GHz",
        "boost_clock": "1.77 GHz",
        "recommended_psu": "450W",
        "release_date": "February 22, 2019",
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
        "power": "125W",
        "base_clock": "1.53 GHz",
        "boost_clock": "1.785 GHz",
        "recommended_psu": "450W",
        "release_date": "October 29, 2019",
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
        "power": "100W",
        "base_clock": "1.53 GHz",
        "boost_clock": "1.725 GHz",
        "recommended_psu": "350W",
        "release_date": "November 22, 2019",
        "description": "An entry-level Turing GPU designed for affordable 1080p gaming."
    },
        {
        "id": 21,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1650",
        "architecture": "Turing",
        "vram": "4GB GDDR5",
        "cuda_cores": 896,
        "memory_bus": "128-bit",
        "power": "75W",
        "base_clock": "1.485 GHz",
        "boost_clock": "1.665 GHz",
        "recommended_psu": "300W",
        "release_date": "April 23, 2019",
        "description": "An entry-level Turing GPU designed for efficient 1080p gaming."
    },
    {
        "id": 22,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1080 Ti",
        "architecture": "Pascal",
        "vram": "11GB GDDR5X",
        "cuda_cores": 3584,
        "memory_bus": "352-bit",
        "power": "250W",
        "base_clock": "1.480 GHz",
        "boost_clock": "1.582 GHz",
        "recommended_psu": "600W",
        "release_date": "March 10, 2017",
        "description": "The flagship GTX 10-series gaming GPU based on NVIDIA's Pascal architecture."
    },
    {
        "id": 23,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1080",
        "architecture": "Pascal",
        "vram": "8GB GDDR5X",
        "cuda_cores": 2560,
        "memory_bus": "256-bit",
        "power": "180W",
        "base_clock": "1.607 GHz",
        "boost_clock": "1.733 GHz",
        "recommended_psu": "500W",
        "release_date": "May 27, 2016",
        "description": "A high-end Pascal GPU designed for high-performance 1440p and 4K gaming."
    },
    {
        "id": 24,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1070 Ti",
        "architecture": "Pascal",
        "vram": "8GB GDDR5",
        "cuda_cores": 2432,
        "memory_bus": "256-bit",
        "power": "180W",
        "base_clock": "1.607 GHz",
        "boost_clock": "1.683 GHz",
        "recommended_psu": "500W",
        "release_date": "November 2, 2017",
        "description": "A high-performance Pascal GPU positioned between the GTX 1070 and GTX 1080."
    },
    {
        "id": 25,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1070",
        "architecture": "Pascal",
        "vram": "8GB GDDR5",
        "cuda_cores": 1920,
        "memory_bus": "256-bit",
        "power": "150W",
        "base_clock": "1.506 GHz",
        "boost_clock": "1.683 GHz",
        "recommended_psu": "500W",
        "release_date": "June 10, 2016",
        "description": "A Pascal GPU designed for strong 1440p gaming performance."
    },
    {
        "id": 26,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1060",
        "architecture": "Pascal",
        "vram": "6GB GDDR5",
        "cuda_cores": 1280,
        "memory_bus": "192-bit",
        "power": "120W",
        "base_clock": "1.506 GHz",
        "boost_clock": "1.708 GHz",
        "recommended_psu": "400W",
        "release_date": "July 19, 2016",
        "description": "A popular mid-range Pascal GPU designed for high-quality 1080p gaming."
    },
    {
        "id": 27,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1050 Ti",
        "architecture": "Pascal",
        "vram": "4GB GDDR5",
        "cuda_cores": 768,
        "memory_bus": "128-bit",
        "power": "75W",
        "base_clock": "1.290 GHz",
        "boost_clock": "1.392 GHz",
        "recommended_psu": "300W",
        "release_date": "October 25, 2016",
        "description": "An efficient entry-level Pascal GPU designed for affordable 1080p gaming."
    },
    {
        "id": 28,
        "brand": "NVIDIA",
        "model": "GeForce GTX 1050",
        "architecture": "Pascal",
        "vram": "2GB GDDR5",
        "cuda_cores": 640,
        "memory_bus": "128-bit",
        "power": "75W",
        "base_clock": "1.354 GHz",
        "boost_clock": "1.455 GHz",
        "recommended_psu": "300W",
        "release_date": "October 25, 2016",
        "description": "An entry-level Pascal graphics card designed for low-power 1080p gaming."
    },
    {
        "id": 29,
        "brand": "NVIDIA",
        "model": "GeForce GTX 980 Ti",
        "architecture": "Maxwell",
        "vram": "6GB GDDR5",
        "cuda_cores": 2816,
        "memory_bus": "384-bit",
        "power": "250W",
        "base_clock": "1.000 GHz",
        "boost_clock": "1.075 GHz",
        "recommended_psu": "600W",
        "release_date": "June 2, 2015",
        "description": "A flagship-class Maxwell GPU designed for enthusiast gaming."
    },
    {
        "id": 30,
        "brand": "NVIDIA",
        "model": "GeForce GTX 980",
        "architecture": "Maxwell",
        "vram": "4GB GDDR5",
        "cuda_cores": 2048,
        "memory_bus": "256-bit",
        "power": "165W",
        "base_clock": "1.126 GHz",
        "boost_clock": "1.216 GHz",
        "recommended_psu": "500W",
        "release_date": "September 18, 2014",
        "description": "A high-end Maxwell graphics card designed for enthusiast gaming."
    },
    {
        "id": 31,
        "brand": "NVIDIA",
        "model": "GeForce GTX 970",
        "architecture": "Maxwell",
        "vram": "4GB GDDR5",
        "cuda_cores": 1664,
        "memory_bus": "256-bit",
        "power": "145W",
        "base_clock": "1.050 GHz",
        "boost_clock": "1.178 GHz",
        "recommended_psu": "500W",
        "release_date": "September 18, 2014",
        "description": "A popular Maxwell GPU that offered strong gaming performance and power efficiency."
    },
    {
        "id": 32,
        "brand": "NVIDIA",
        "model": "GeForce GTX 960",
        "architecture": "Maxwell",
        "vram": "2GB GDDR5",
        "cuda_cores": 1024,
        "memory_bus": "128-bit",
        "power": "120W",
        "base_clock": "1.127 GHz",
        "boost_clock": "1.178 GHz",
        "recommended_psu": "400W",
        "release_date": "January 22, 2015",
        "description": "A mainstream Maxwell GPU designed primarily for 1080p gaming."
    },
    {
        "id": 33,
        "brand": "NVIDIA",
        "model": "GeForce GTX 780 Ti",
        "architecture": "Kepler",
        "vram": "3GB GDDR5",
        "cuda_cores": 2880,
        "memory_bus": "384-bit",
        "power": "250W",
        "base_clock": "0.875 GHz",
        "boost_clock": "0.928 GHz",
        "recommended_psu": "600W",
        "release_date": "November 7, 2013",
        "description": "The flagship GTX 700-series Kepler GPU designed for enthusiast gaming."
    },
    {
        "id": 34,
        "brand": "NVIDIA",
        "model": "GeForce GTX 780",
        "architecture": "Kepler",
        "vram": "3GB GDDR5",
        "cuda_cores": 2304,
        "memory_bus": "384-bit",
        "power": "250W",
        "base_clock": "0.863 GHz",
        "boost_clock": "0.900 GHz",
        "recommended_psu": "600W",
        "release_date": "May 23, 2013",
        "description": "A high-end Kepler graphics card designed for enthusiast gaming."
    },

        {
        "id": 35,
        "brand": "NVIDIA",
        "model": "GeForce GT 1030",
        "architecture": "Pascal",
        "vram": "2GB GDDR5",
        "cuda_cores": 384,
        "memory_bus": "64-bit",
        "power": "30W",
        "base_clock": "1.227 GHz",
        "boost_clock": "1.468 GHz",
        "recommended_psu": "300W",
        "release_date": "May 17, 2017",
        "description": "An entry-level Pascal GPU designed for multimedia, esports, and light gaming."
    },
    {
        "id": 36,
        "brand": "NVIDIA",
        "model": "GeForce GT 1010",
        "architecture": "Pascal",
        "vram": "2GB GDDR5",
        "cuda_cores": 256,
        "memory_bus": "64-bit",
        "power": "30W",
        "base_clock": "1.228 GHz",
        "boost_clock": "1.468 GHz",
        "recommended_psu": "200W",
        "release_date": "January 13, 2021",
        "description": "A low-power OEM Pascal GPU intended for basic graphics and multimedia workloads."
    },
    {
        "id": 37,
        "brand": "NVIDIA",
        "model": "GeForce GT 740",
        "architecture": "Kepler",
        "vram": "1GB GDDR5",
        "cuda_cores": 384,
        "memory_bus": "128-bit",
        "power": "64W",
        "base_clock": "0.993 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "400W",
        "release_date": "May 29, 2014",
        "description": "An entry-level Kepler GPU offering improved multimedia and light gaming performance."
    },
    {
        "id": 38,
        "brand": "NVIDIA",
        "model": "GeForce GT 730",
        "architecture": "Kepler",
        "vram": "1GB GDDR5",
        "cuda_cores": 384,
        "memory_bus": "64-bit",
        "power": "38W",
        "base_clock": "0.902 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "June 18, 2014",
        "description": "A low-power Kepler graphics card designed for multimedia, productivity, and light gaming."
    },
    {
        "id": 39,
        "brand": "NVIDIA",
        "model": "GeForce GT 720",
        "architecture": "Kepler",
        "vram": "1GB DDR3",
        "cuda_cores": 192,
        "memory_bus": "64-bit",
        "power": "19W",
        "base_clock": "0.797 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "September 29, 2014",
        "description": "A low-power Kepler GPU intended for basic desktop graphics and multimedia."
    },
    {
        "id": 40,
        "brand": "NVIDIA",
        "model": "GeForce GT 710",
        "architecture": "Kepler",
        "vram": "2GB DDR3",
        "cuda_cores": 192,
        "memory_bus": "64-bit",
        "power": "19W",
        "base_clock": "0.954 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "January 26, 2016",
        "description": "An ultra-low-power Kepler GPU designed for basic display output and multimedia workloads."
    },
    {
        "id": 41,
        "brand": "NVIDIA",
        "model": "GeForce GT 640",
        "architecture": "Kepler",
        "vram": "2GB DDR3",
        "cuda_cores": 384,
        "memory_bus": "128-bit",
        "power": "65W",
        "base_clock": "0.900 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "350W",
        "release_date": "June 5, 2012",
        "description": "A Kepler-based mainstream GPU designed for multimedia and entry-level gaming."
    },
    {
        "id": 42,
        "brand": "NVIDIA",
        "model": "GeForce GT 630",
        "architecture": "Fermi",
        "vram": "1GB GDDR5",
        "cuda_cores": 96,
        "memory_bus": "128-bit",
        "power": "65W",
        "base_clock": "0.810 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "May 15, 2012",
        "description": "An entry-level Fermi graphics card designed for multimedia and light gaming workloads."
    },
    {
        "id": 43,
        "brand": "NVIDIA",
        "model": "GeForce GT 620",
        "architecture": "Fermi",
        "vram": "1GB DDR3",
        "cuda_cores": 96,
        "memory_bus": "64-bit",
        "power": "49W",
        "base_clock": "0.700 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "May 15, 2012",
        "description": "A budget Fermi GPU intended for general desktop graphics and multimedia use."
    },
    {
        "id": 44,
        "brand": "NVIDIA",
        "model": "GeForce GT 610",
        "architecture": "Fermi",
        "vram": "1GB DDR3",
        "cuda_cores": 48,
        "memory_bus": "64-bit",
        "power": "29W",
        "base_clock": "0.810 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "April 2, 2012",
        "description": "A low-power Fermi graphics card designed for basic desktop and multimedia applications."
    },
    {
        "id": 45,
        "brand": "NVIDIA",
        "model": "GeForce GT 520",
        "architecture": "Fermi",
        "vram": "1GB DDR3",
        "cuda_cores": 48,
        "memory_bus": "64-bit",
        "power": "29W",
        "base_clock": "0.810 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "April 12, 2011",
        "description": "An entry-level Fermi GPU designed primarily for HD video, multimedia, and basic graphics workloads."
    },
    {
        "id": 46,
        "brand": "NVIDIA",
        "model": "GeForce GT 430",
        "architecture": "Fermi",
        "vram": "1GB DDR3",
        "cuda_cores": 96,
        "memory_bus": "128-bit",
        "power": "49W",
        "base_clock": "0.700 GHz",
        "boost_clock": "N/A",
        "recommended_psu": "300W",
        "release_date": "October 11, 2010",
        "description": "An entry-level Fermi GPU designed for HD multimedia and basic gaming workloads."
    },
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


