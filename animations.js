import { animate, stagger, splitText } from 'https://esm.sh/animejs';


// HERO ENTRANCE

const heroElements = document.querySelectorAll(
    '.hero .eyebrow, .hero h1, .hero-copy, .hero-search'
);

animate(heroElements, {
    opacity: [0, 1],
    y: [30, 0],

    delay: stagger(180),

    duration: 1000,
    ease: 'outExpo'
});


// NVIDIA GPU LETTER ANIMATION

const { chars } = splitText('.gpu-bounce', {
    words: false,
    chars: true
});

const bounceHeight =
    window.innerWidth <= 720 ? '-1rem' : '-2.75rem';

animate(chars, {
    y: [
        {
            to: bounceHeight,
            ease: 'outExpo',
            duration: 600
        },
        {
            to: 0,
            ease: 'outBounce',
            duration: 800,
            delay: 100
        }
    ],

    rotate: {
        from: '-1turn',
        delay: 0
    },

    // Wait until hero entrance mostly finishes
    delay: stagger(50, {
        start: 900
    }),

    ease: 'inOutCirc',

    loopDelay: 1000,
    loop: true
});

// GPU cards stagger in

window.animateGpuCards = function () {

    const searchCards =
        document.querySelectorAll('.gpu-search-grid .gpu-card');


    if (searchCards.length) {

        animate(searchCards, {
            opacity: [0, 1],
            y: [40, 0],
            scale: [0.96, 1],
            delay: stagger(80),
            duration: 700,
            ease: 'outExpo'
        });

        return;
    }


    const categories =
        document.querySelectorAll('.gpu-category');


    categories.forEach((category) => {

        const cards =
            category.querySelectorAll('.gpu-card');

        animate(cards, {
            opacity: [0, 1],
            y: [40, 0],
            scale: [0.96, 1],
            delay: stagger(80),
            duration: 700,
            ease: 'outExpo'
        });

    });

};


// GPU IMAGE HOVER


window.setupGpuImageHover = function () {

    const cards = document.querySelectorAll('.gpu-card');

    cards.forEach((card) => {

        const image = card.querySelector('.gpu-photo');

        if (!image) return;

        card.addEventListener('mouseenter', () => {

            animate(image, {
                scale: 1.08,
                y: -5,
                duration: 450,
                ease: 'outExpo'
            });

        });


        card.addEventListener('mouseleave', () => {

            animate(image, {
                scale: 1,
                y: 0,
                duration: 450,
                ease: 'outExpo'
            });

        });

    });

};

// GPU details page entrance

window.animateGpuDetails = function (gpu) {

    animate('.details-copy', {
        opacity: [0, 1],
        x: [-60, 0],
        duration: 900,
        ease: 'outExpo'
    });


    animate('.details-media', {
        opacity: [0, 1],
        x: [80, 0],
        scale: [0.94, 1],
        duration: 1000,
        ease: 'outExpo'
    });


    animate('.spec-row', {
        opacity: [0, 1],
        y: [25, 0],
        delay: stagger(70, {
            start: 250
        }),
        duration: 600,
        ease: 'outExpo'
    });


    animate('.about-card', {
        opacity: [0, 1],
        y: [35, 0],
        delay: 500,
        duration: 800,
        ease: 'outExpo'
    });


    // CUDA core counter

    const cudaValue =
        Number(gpu.cuda_cores) || 0;

    const counter = {
        value: 0
    };

    const cudaElements = [
        document.getElementById('detailsCuda'),
        document.getElementById('specCuda')
    ].filter(Boolean);


    cudaElements.forEach((element) => {
        element.textContent = "0";
    });


    animate(counter, {
        value: cudaValue,
        duration: 1400,
        delay: 250,
        ease: 'outExpo',

        onUpdate: () => {
            const value =
                Math.round(counter.value)
                    .toLocaleString();

            cudaElements.forEach((element) => {
                element.textContent = value;
            });
        }
    });

};

// Category header reveal

window.animateGpuCategories = function () {
    const headers =
        document.querySelectorAll('.gpu-category-header');

    if (!headers.length) return;

    animate(headers, {
        opacity: [0, 1],
        y: [20, 0],
        delay: stagger(120),
        duration: 700,
        ease: 'outExpo'
    });
};


// Slider button animation

window.setupSliderButtonAnimations = function () {
    const buttons =
        document.querySelectorAll('.slider-button');

    buttons.forEach((button) => {
        button.addEventListener('click', () => {
            animate(button, {
                scale: [
                    { to: 0.88, duration: 100 },
                    { to: 1, duration: 300 }
                ],
                ease: 'outBack'
            });
        });
    });
};


// Search results fade out

window.animateSearchOut = function () {
    return new Promise((resolve) => {
        animate('#gpuList', {
            opacity: [1, 0],
            y: [0, 12],
            duration: 250,
            ease: 'inQuad',
            onComplete: resolve
        });
    });
};


// Search results fade in

window.animateSearchIn = function () {
    animate('#gpuList', {
        opacity: [0, 1],
        y: [12, 0],
        duration: 500,
        ease: 'outExpo'
    });
};