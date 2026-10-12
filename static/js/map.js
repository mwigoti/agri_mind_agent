// Function to initialize and render the map in the 'map' div
function initializeMap() {
    // Access the div with id 'map' and initialize the map
    const map = L.map('map').setView([0, 0], 2);

    // Define base layers
    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Esri World Imagery and Boundaries Layers
    const satelliteLayer = L.esri.basemapLayer('Imagery');
    const boundariesLayer = L.esri.basemapLayer('ImageryLabels');

    // Layer switcher functionality
    const layerSelect = document.getElementById('layerSelect');
    if (layerSelect) {
        layerSelect.addEventListener('change', function(e) {
            // Clear all layers before adding the selected one
            map.eachLayer(function(layer) {
                map.removeLayer(layer);
            });

            // Add the selected layer based on the dropdown choice
            if (e.target.value === 'osm') {
                map.addLayer(osmLayer);
            } else if (e.target.value === 'satellite') {
                map.addLayer(satelliteLayer);
            } else if (e.target.value === 'satelliteBoundaries') {
                map.addLayer(satelliteLayer);
                map.addLayer(boundariesLayer); // Add boundaries on top
            }
        });
    }

    // Add a feature group to hold drawn items
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    // Add draw control to the map for polygon drawing
    const drawControl = new L.Control.Draw({
        edit: { featureGroup: drawnItems },
        draw: {
            polygon: true,
            polyline: false,
            circle: false,
            rectangle: false,
            marker: false,
            circlemarker: false
        }
    });
    map.addControl(drawControl);

    // Capture polygon coordinates when a new polygon is created
    map.on(L.Draw.Event.CREATED, function(event) {
        const layer = event.layer;
        const coordinates = layer.getLatLngs()[0].map(function(latlng) {
            return [latlng.lat, latlng.lng];
        });
        console.log("Polygon coordinates:", coordinates); // Placeholder for further processing

        drawnItems.addLayer(layer);
    });
}

// Toggle Info Panel functionality
function setupInfoPanelToggle() {
    const infoPanel = document.querySelector(".info-panel");
    const toggleButton = document.querySelector(".menu ul li:first-child");

    if (!infoPanel || !toggleButton) {
        console.error("Required elements not found. Check if the 'info-panel' class and toggle button are correctly defined.");
        return;
    }

    // Ensure the panel is visible by default
    infoPanel.style.display = "block";

    // Toggle visibility on button click
    toggleButton.addEventListener("click", function() {
        const isVisible = infoPanel.style.display === "block";
        infoPanel.style.display = isVisible ? "none" : "block";
        toggleButton.textContent = isVisible ? "Show Info Panel" : "Hide Info Panel";
    });
}

// Initialize map and setup toggle when DOM is fully loaded
document.addEventListener("DOMContentLoaded", function() {
    initializeMap();
    setupInfoPanelToggle();
});
