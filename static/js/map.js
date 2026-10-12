document.addEventListener('DOMContentLoaded', function() {
    initMap();
    setupEventListeners();
});

let map;

function initMap() {
    map = L.map('map').setView([0, 0], 2);  // Set initial view to the center of the world with zoom level 2

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    console.log("Map initialized");
}

function setupEventListeners() {
    // Menu item click
    document.querySelectorAll('.menu nav ul li').forEach(item => {
        item.addEventListener('click', function() {
            document.querySelector('.menu nav ul li.active')?.classList.remove('active');
            this.classList.add('active');
        });
    });

    // Zoom controls
    document.querySelector('.zoom-in').addEventListener('click', function() {
        map.zoomIn();
    });

    document.querySelector('.zoom-out').addEventListener('click', function() {
        map.zoomOut();
    });

    // Layer controls
    document.querySelector('.layer-controls select').addEventListener('change', function() {
        // Update the map layer based on the selected value
        console.log("Layer changed to: " + this.value);
    });
}
document.addEventListener('DOMContentLoaded', (event) => {
    const infoPanel = document.querySelector('.info-panel');
    const toggleButton = document.getElementById('toggleButton');
    
    toggleButton.addEventListener('click', () => {
        if (infoPanel.style.display === 'none') {
            infoPanel.style.display = 'block';
            toggleButton.textContent = 'Hide Info Panel';
        } else {
            infoPanel.style.display = 'none';
            toggleButton.textContent = 'Show Info Panel';
        }
    });
});