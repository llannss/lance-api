const API_URL = "https://lance-api-murex.vercel.app";

const catalogView = document.getElementById("catalogView");
const detailsView = document.getElementById("detailsView");
const gpuList = document.getElementById("gpuList");
const gpuCount = document.getElementById("gpuCount");
const searchForm = document.getElementById("searchForm");
const searchInput = document.getElementById("searchInput");
const showAllButton = document.getElementById("showAllButton");
const backButton = document.getElementById("backButton");
const brandHome = document.getElementById("brandHome");


// GPU image

function getImageFile(gpu) {
    const shortModel = gpu.model
        .replace(/^GeForce\s+/i, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");

    return `images/${shortModel}.png`;
}


// GPU series

function getSeries(gpu) {
    const model = gpu.model.toUpperCase();

    // RTX

    if (model.includes("RTX 50")) {
        return "GeForce RTX 50 Series";
    }

    if (model.includes("RTX 40")) {
        return "GeForce RTX 40 Series";
    }

    if (model.includes("RTX 30")) {
        return "GeForce RTX 30 Series";
    }

    if (model.includes("RTX 20")) {
        return "GeForce RTX 20 Series";
    }

    // GTX

    if (model.includes("GTX 16")) {
        return "GeForce GTX 16 Series";
    }

    if (
        model.includes("GTX 1080") ||
        model.includes("GTX 1070") ||
        model.includes("GTX 1060") ||
        model.includes("GTX 1050")
    ) {
        return "GeForce GTX 10 Series";
    }

    if (
        model.includes("GTX 980") ||
        model.includes("GTX 970") ||
        model.includes("GTX 960")
    ) {
        return "GeForce GTX 900 Series";
    }

    if (
        model.includes("GTX 780") ||
        model.includes("GTX 770") ||
        model.includes("GTX 760")
    ) {
        return "GeForce GTX 700 Series";
    }

    // GT

    if (
        model.includes("GT 1030") ||
        model.includes("GT 1010")
    ) {
        return "GeForce GT 10 Series";
    }

    if (
        model.includes("GT 740") ||
        model.includes("GT 730") ||
        model.includes("GT 720") ||
        model.includes("GT 710")
    ) {
        return "GeForce GT 700 Series";
    }

    if (
        model.includes("GT 640") ||
        model.includes("GT 630") ||
        model.includes("GT 620") ||
        model.includes("GT 610")
    ) {
        return "GeForce GT 600 Series";
    }

    if (model.includes("GT 520")) {
        return "GeForce GT 500 Series";
    }

    if (model.includes("GT 430")) {
        return "GeForce GT 400 Series";
    }

    return "NVIDIA GeForce";
}


// Format numbers

function formatNumber(value) {
    return Number(value).toLocaleString();
}


// GPU overview

function buildOverview(gpu) {
    return `
        ${gpu.description}
        It is based on NVIDIA's ${gpu.architecture} architecture
        and includes ${formatNumber(gpu.cuda_cores)} CUDA cores,
        ${gpu.vram} of video memory, and a
        ${gpu.memory_bus} memory interface.
    `;
}


// Load GPUs

async function loadGPUs() {
    setLoadingState();

    try {
        const response = await fetch(`${API_URL}/gpus`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        displayGPUs(data.gpus);
    }

    catch (error) {
        console.error(error);

        showError(
            "Unable to connect to the GPU API. Make sure your FastAPI deployment is online."
        );
    }
}


// Loading state

function setLoadingState() {
    gpuCount.textContent = "Loading...";

    gpuList.innerHTML = `
        <div class="loading-state">

            <div class="loading-bar"></div>

            <p>
                Loading NVIDIA GPUs...
            </p>

        </div>
    `;
}


// Error state

function showError(message) {
    gpuCount.textContent = "Unavailable";

    gpuList.innerHTML = `
        <div class="error-state">

            <strong>
                Could not load GPUs
            </strong>

            <p>
                ${message}
            </p>

        </div>
    `;
}


// Create GPU card

function createGpuCard(gpu) {
    const card = document.createElement("article");

    card.className = "gpu-card";

    const imagePath = getImageFile(gpu);
    const series = getSeries(gpu);

    card.innerHTML = `

        <div class="gpu-media">

            <div class="gpu-photo-placeholder">

                <span></span>


            </div>

            <img
                class="gpu-photo"
                src="${imagePath}"
                alt="${gpu.model}"
                loading="lazy"
            >

        </div>


        <div class="gpu-card-content">

            <span class="gpu-series">
                ${series}
            </span>


            <h3>
                ${gpu.model}
            </h3>


            <p class="gpu-architecture">
                ${gpu.architecture} Architecture
            </p>


            <div class="gpu-specs">

                <div>
                    <span>VRAM</span>

                    <strong>
                        ${gpu.vram}
                    </strong>
                </div>


                <div>
                    <span>CUDA</span>

                    <strong>
                        ${formatNumber(gpu.cuda_cores)}
                    </strong>
                </div>


                <div>
                    <span>Bus</span>

                    <strong>
                        ${gpu.memory_bus}
                    </strong>
                </div>

            </div>


            <p class="gpu-description">
                ${gpu.description}
            </p>


            <button
                type="button"
                class="details-button"
                data-gpu-id="${gpu.id}"
            >
                View Details
            </button>

        </div>
    `;


    const cardImage =
        card.querySelector(".gpu-photo");


    cardImage.addEventListener("error", () => {
        cardImage.remove();
    });


    return card;
}


// Display GPUs

function displayGPUs(gpus, isSearch = false) {
    gpuList.innerHTML = "";

    gpuCount.textContent =
        `${gpus.length} GPU${gpus.length === 1 ? "" : "s"} found`;


    // No results

    if (gpus.length === 0) {
        gpuList.innerHTML = `
            <div class="empty-state">

                <strong>
                    No matching GPU found.
                </strong>

                <p>
                    Try RTX 4070, GTX 1080,
                    GT 1030, Blackwell, or 16GB.
                </p>

            </div>
        `;

        return;
    }

    // Search results

if (isSearch) {

    const searchGrid =
        document.createElement("div");

    searchGrid.className =
        "gpu-search-grid";


    gpus.forEach((gpu) => {

        const card =
            createGpuCard(gpu);

        searchGrid.appendChild(card);

    });


    gpuList.appendChild(searchGrid);


    if (window.animateGpuCards) {
        window.animateGpuCards();
    }

    if (window.setupGpuImageHover) {
        window.setupGpuImageHover();
    }


    return;
}
    // GPU groups

    const groups = {
        RTX: [],
        GTX: [],
        GT: []
    };


    gpus.forEach((gpu) => {
        const model = gpu.model.toUpperCase();

        if (model.includes("RTX")) {
            groups.RTX.push(gpu);
        }

        else if (model.includes("GTX")) {
            groups.GTX.push(gpu);
        }

        else if (model.includes("GT")) {
            groups.GT.push(gpu);
        }
    });


    // Create sections

    Object.entries(groups).forEach(
        ([category, categoryGPUs]) => {

            if (categoryGPUs.length === 0) {
                return;
            }


            const section =
                document.createElement("section");


            section.className =
                "gpu-category";


            section.innerHTML = `
    <div class="gpu-category-header">

        <div>
            <p class="eyebrow green">GEFORCE</p>
            <h2>${category}</h2>
        </div>

        <div class="gpu-slider-controls">

            <span class="gpu-category-count">
                ${categoryGPUs.length}
                GPU${categoryGPUs.length === 1 ? "" : "s"}
            </span>

            <button
                type="button"
                class="slider-button slider-prev"
                aria-label="Previous GPUs"
            >
                ←
            </button>

            <button
                type="button"
                class="slider-button slider-next"
                aria-label="Next GPUs"
            >
                →
            </button>

        </div>

    </div>

    <div class="gpu-slider">
        <div class="gpu-slider-track"></div>
    </div>
`;


            const track =
    section.querySelector(".gpu-slider-track");

            const slider =
                section.querySelector(".gpu-slider");

            const prevButton =
                section.querySelector(".slider-prev");

            const nextButton =
                section.querySelector(".slider-next");

            let currentIndex = 0;


            function goToCard(index) {

                const cards =
                    track.querySelectorAll(".gpu-card");

                if (!cards.length) return;


                currentIndex = Math.max(
                    0,
                    Math.min(index, cards.length - 1)
                );


                const card = cards[currentIndex];


                slider.scrollTo({
                    left: card.offsetLeft,
                    behavior: "smooth"
                });
            }


// Previous

prevButton.addEventListener("click", () => {

    goToCard(currentIndex - 1);

});


// Next

nextButton.addEventListener("click", () => {

    goToCard(currentIndex + 1);

});


// Create GPU cards

categoryGPUs.forEach((gpu) => {

    const card =
        createGpuCard(gpu);

    track.appendChild(card);

});


gpuList.appendChild(section);

            }
        );


    // Animations

    if (window.animateGpuCategories) {
        window.animateGpuCategories();
    }

    if (window.animateGpuCards) {
        window.animateGpuCards();
    }

    if (window.setupGpuImageHover) {
        window.setupGpuImageHover();
    }

    if (window.setupSliderButtonAnimations) {
        window.setupSliderButtonAnimations();
    }
}


// Get GPU

async function viewGPU(id) {
    try {
        const response =
            await fetch(`${API_URL}/gpus/${id}`);


        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }


        const gpu =
            await response.json();


        renderDetails(gpu);


        catalogView.hidden = true;

        detailsView.hidden = false;


        if (window.animateGpuDetails) {
        window.animateGpuDetails(gpu);
        }


        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
    }

    catch (error) {
        console.error(error);

        showError(
            "Unable to retrieve the selected GPU."
        );
    }
}


// Render details

function renderDetails(gpu) {
    const series =
        getSeries(gpu);

    const imagePath =
        getImageFile(gpu);


    document.getElementById(
        "detailsSeries"
    ).textContent =
        series;


    document.getElementById(
        "detailsModel"
    ).textContent =
        gpu.model;


    document.getElementById(
        "detailsArchitecture"
    ).textContent =
        `${gpu.architecture} Architecture`;


    document.getElementById(
        "detailsDescription"
    ).textContent =
        gpu.description;


    document.getElementById(
        "detailsVram"
    ).textContent =
        gpu.vram;


    document.getElementById(
        "detailsCuda"
    ).textContent =
        formatNumber(gpu.cuda_cores);


    document.getElementById(
        "detailsPlaceholderModel"
    ).textContent =
        gpu.model;


    document.getElementById(
        "detailsImageHint"
    ).textContent =
        `Add ${imagePath}`;


    // Specifications

    document.getElementById(
        "specModel"
    ).textContent =
        `${gpu.brand} ${gpu.model}`;


    document.getElementById(
        "specArchitecture"
    ).textContent =
        gpu.architecture;


    document.getElementById(
        "specVram"
    ).textContent =
        gpu.vram;


    document.getElementById(
        "specCuda"
    ).textContent =
        formatNumber(gpu.cuda_cores);


    document.getElementById(
        "specBus"
    ).textContent =
        gpu.memory_bus;


    document.getElementById(
        "specSeries"
    ).textContent =
        series;


    document.getElementById(
        "specPower"
    ).textContent =
        gpu.power ?? "—";


    document.getElementById(
        "specBaseClock"
    ).textContent =
        gpu.base_clock ?? "—";


    document.getElementById(
        "specBoostClock"
    ).textContent =
        gpu.boost_clock ?? "—";


    document.getElementById(
        "specPsu"
    ).textContent =
        gpu.recommended_psu ?? "—";


    document.getElementById(
        "specReleaseDate"
    ).textContent =
        gpu.release_date ?? "—";


    document.getElementById(
        "detailsOverview"
    ).textContent =
        buildOverview(gpu);


    // GPU image

    const detailsImage =
        document.getElementById(
            "detailsImage"
        );


    const placeholder =
        document.getElementById(
            "detailsPhotoPlaceholder"
        );


    detailsImage.hidden = true;

    placeholder.hidden = false;

    detailsImage.alt =
        gpu.model;


    detailsImage.onload = () => {
        detailsImage.hidden = false;
        placeholder.hidden = true;
    };


    detailsImage.onerror = () => {
        detailsImage.hidden = true;
        placeholder.hidden = false;
    };


    detailsImage.src =
        imagePath;


    document.title =
        `${gpu.model} | NVIDIA GPU Finder`;
}


// Back to catalog

function showCatalog() {
    detailsView.hidden = true;

    catalogView.hidden = false;


    document.title =
        "NVIDIA GPU Finder";


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// Search GPUs

async function searchGPUs(query) {
    const cleanQuery =
        query.trim();


    if (!cleanQuery) {
        await loadGPUs();
        return;
    }




    try {
        const response =
            await fetch(
                `${API_URL}/gpus/search?q=${encodeURIComponent(cleanQuery)}`
            );


        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        if (window.animateSearchOut) {
            await window.animateSearchOut();
        }


        displayGPUs(
            data.results,
            true
        );


        if (window.animateSearchIn) {
            window.animateSearchIn();
        }


        document
            .getElementById("catalogSection")
            .scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
    }

    catch (error) {
        console.error(error);

        showError(
            "GPU search failed. Please try again."
        );
    }
}


// View details button

gpuList.addEventListener(
    "click",
    (event) => {

        const button =
            event.target.closest(
                "[data-gpu-id]"
            );


        if (!button) {
            return;
        }


        viewGPU(
            button.dataset.gpuId
        );

    }
);


// Search form

searchForm.addEventListener(
    "submit",
    (event) => {

        event.preventDefault();

        searchGPUs(
            searchInput.value
        );

    }
);


// Show all

showAllButton.addEventListener(
    "click",
    () => {

        searchInput.value = "";

        loadGPUs();

    }
);


// Back button

backButton.addEventListener(
    "click",
    showCatalog
);


// NVIDIA logo

brandHome.addEventListener(
    "click",
    (event) => {

        event.preventDefault();

        showCatalog();

    }
);


// Initial load

loadGPUs();
