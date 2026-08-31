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


// GPU IMAGE FILE

function getImageFile(gpu) {
    const shortModel = gpu.model
        .replace(/^GeForce\s+/i, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");

    return `images/${shortModel}.png`;
}


// GPU SERIES

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


// FORMAT NUMBER

function formatNumber(value) {
    return Number(value).toLocaleString();
}


// GPU OVERVIEW

function buildOverview(gpu) {
    return `
        ${gpu.description}
        It is based on NVIDIA's ${gpu.architecture} architecture
        and includes ${formatNumber(gpu.cuda_cores)} CUDA cores,
        ${gpu.vram} of video memory, and a
        ${gpu.memory_bus} memory interface.
    `;
}


// LOAD ALL GPUS

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


// LOADING STATE

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


// ERROR STATE

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


// DISPLAY GPU CARDS

function displayGPUs(gpus) {
    gpuList.innerHTML = "";

    gpuCount.textContent =
        `${gpus.length} GPU${gpus.length === 1 ? "" : "s"} found`;


    // NO RESULTS

    if (gpus.length === 0) {

        gpuList.innerHTML = `
            <div class="empty-state">

                <strong>
                    No matching GPU found.
                </strong>

                <p>
                    Try a model like RTX 4070,
                    an architecture like Blackwell,
                    or a VRAM value like 16GB.
                </p>

            </div>
        `;

        return;
    }


    // CREATE EACH GPU CARD

    gpus.forEach((gpu) => {

        const card = document.createElement("article");

        card.className = "gpu-card";


        const imagePath = getImageFile(gpu);

        const series = getSeries(gpu);


        card.innerHTML = `

            <!-- GPU IMAGE -->

            <div class="gpu-media">

                <div class="gpu-photo-placeholder">

                    <span>
                    </span>

                    <strong>
                    </strong>

                    <small>
                    </small>

                </div>


                <img
                    class="gpu-photo"
                    src="${imagePath}"
                    alt="${gpu.model}"
                    loading="lazy"
                >

            </div>


            <!-- GPU INFORMATION -->

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


                <!-- QUICK SPECS -->

                <div class="gpu-specs">

                    <div>

                        <span>
                            VRAM
                        </span>

                        <strong>
                            ${gpu.vram}
                        </strong>

                    </div>


                    <div>

                        <span>
                            CUDA
                        </span>

                        <strong>
                            ${formatNumber(gpu.cuda_cores)}
                        </strong>

                    </div>


                    <div>

                        <span>
                            Bus
                        </span>

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


        // IF IMAGE DOES NOT EXIST,
        // KEEP THE PLACEHOLDER

        const cardImage =
            card.querySelector(".gpu-photo");


        cardImage.addEventListener("error", () => {

            cardImage.remove();

        });


        gpuList.appendChild(card);

    });
}

if (window.animateGpuCards) {
    window.animateGpuCards();
}

if (window.setupGpuImageHover) {
    window.setupGpuImageHover();
}


// GET ONE GPU

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


        // HIDE CATALOG

        catalogView.hidden = true;


        // SHOW FULL DETAILS PAGE

        detailsView.hidden = false;

        if (window.animateGpuDetails) {
        window.animateGpuDetails();
        }


        // SCROLL TO TOP

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


// RENDER FULL GPU DETAILS PAGE

function renderDetails(gpu) {

    const series =
        getSeries(gpu);


    const imagePath =
        getImageFile(gpu);


    // HERO INFORMATION

    document.getElementById(
        "detailsSeries"
    ).textContent = series;


    document.getElementById(
        "detailsModel"
    ).textContent = gpu.model;


    document.getElementById(
        "detailsArchitecture"
    ).textContent =
        `${gpu.architecture} Architecture`;


    document.getElementById(
        "detailsDescription"
    ).textContent =
        gpu.description;


    // HERO QUICK SPECS

    document.getElementById(
        "detailsVram"
    ).textContent =
        gpu.vram;


    document.getElementById(
        "detailsCuda"
    ).textContent =
        formatNumber(gpu.cuda_cores);


    // IMAGE PLACEHOLDER TEXT

    document.getElementById(
        "detailsPlaceholderModel"
    ).textContent =
        gpu.model;


    document.getElementById(
        "detailsImageHint"
    ).textContent =
        `Add ${imagePath}`;


    // FULL SPECIFICATION TABLE

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


    // OVERVIEW

    document.getElementById(
        "detailsOverview"
    ).textContent =
        buildOverview(gpu);


    // GPU IMAGE

    const detailsImage =
        document.getElementById(
            "detailsImage"
        );


    const placeholder =
        document.getElementById(
            "detailsPhotoPlaceholder"
        );


    // DEFAULT TO PLACEHOLDER

    detailsImage.hidden = true;

    placeholder.hidden = false;


    detailsImage.alt =
        gpu.model;


    // IMAGE SUCCESSFULLY LOADED

    detailsImage.onload = () => {

        detailsImage.hidden = false;

        placeholder.hidden = true;

    };


    // IMAGE DOES NOT EXIST

    detailsImage.onerror = () => {

        detailsImage.hidden = true;

        placeholder.hidden = false;

    };


    detailsImage.src =
        imagePath;


    // CHANGE PAGE TITLE

    document.title =
        `${gpu.model} | NVIDIA GPU Finder`;
}


// BACK TO GPU CATALOG

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


// SEARCH GPUS

async function searchGPUs(query) {

    const cleanQuery =
        query.trim();


    // EMPTY SEARCH = SHOW ALL

    if (!cleanQuery) {

        await loadGPUs();

        return;

    }


    setLoadingState();


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


        displayGPUs(
            data.results
        );


        // SCROLL TO GPU RESULTS

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


// VIEW DETAILS BUTTON

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


// SEARCH FORM

searchForm.addEventListener(
    "submit",
    (event) => {

        event.preventDefault();


        searchGPUs(
            searchInput.value
        );

    }
);


// SHOW ALL BUTTON

showAllButton.addEventListener(
    "click",
    () => {

        searchInput.value = "";

        loadGPUs();

    }
);


// BACK BUTTON

backButton.addEventListener(
    "click",
    showCatalog
);


// NVIDIA LOGO / HOME BUTTON

brandHome.addEventListener(
    "click",
    (event) => {

        event.preventDefault();

        showCatalog();

    }
);



// INITIAL LOAD

loadGPUs();
