const API_URL = "https://YOUR-API.vercel.app";


// GET ALL GPUS
async function loadGPUs() {
    try {
        const response = await fetch(`${API_URL}/gpus`);
        const data = await response.json();

        displayGPUs(data.gpus);
    }

    catch (error) {
        console.error(error);

        document.getElementById("gpuList").innerHTML =
            "Unable to connect to the API.";
    }
}


// DISPLAY GPUS
function displayGPUs(gpus) {

    const gpuList =
        document.getElementById("gpuList");

    gpuList.innerHTML = "";

    gpus.forEach(gpu => {

        const card = document.createElement("div");

        card.className = "gpu-card";

        card.innerHTML = `
            <div class="gpu-vram">${gpu.vram}</div>

            <h3>${gpu.brand} ${gpu.model}</h3>

            <p class="gpu-architecture">
                ${gpu.architecture}
            </p>

            <p>
                CUDA Cores: ${gpu.cuda_cores}
            </p>

            <p>
                Memory Bus: ${gpu.memory_bus}
            </p>

            <p>
                ${gpu.description}
            </p>

            <button onclick="viewGPU(${gpu.id})">
                View Details
            </button>
        `;

        gpuList.appendChild(card);
    });
}


// GET ONE GPU
async function viewGPU(id) {

    try {

        const response =
            await fetch(`${API_URL}/gpus/${id}`);

        const gpu = await response.json();

        alert(`
            ${gpu.brand} ${gpu.model}

            Architecture:
            ${gpu.architecture}

            VRAM:
            ${gpu.vram}

            CUDA Cores:
            ${gpu.cuda_cores}

            Memory Bus:
            ${gpu.memory_bus}

            Description:
            ${gpu.description}
        `);
    }

    catch (error) {

        console.error(error);

        alert("Unable to retrieve GPU.");
    }
}


// SEARCH GPUS
async function searchGPUs() {

    const query =
        document.getElementById("searchInput").value;

    if (!query) {
        loadGPUs();
        return;
    }

    try {

        const response =
            await fetch(
                `${API_URL}/gpus/search?q=${encodeURIComponent(query)}`
            );

        const data = await response.json();

        displayGPUs(data.results);
    }

    catch (error) {

        console.error(error);

        alert("GPU search failed.");
    }
}


// LOAD GPUS WHEN PAGE OPENS
loadGPUs();