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

    // Return the map object to use in other functions
    return map;
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

// Function to enable marker-based polygon creation
function setupPolygonDrawing(map) {
    // Create an array to store marker coordinates
    const markerCoordinates = [];
    const markers = new L.FeatureGroup();
    const drawnItems = new L.FeatureGroup();
    map.addLayer(markers);
    map.addLayer(drawnItems);

    // Add click event to add markers on map
    map.on('click', function(e) {
        // Get the clicked location coordinates
        const { lat, lng } = e.latlng;

        // Add marker to the map
        const marker = L.marker([lat, lng]).addTo(map);
        markers.addLayer(marker);

        // Store the coordinates of the marker
        markerCoordinates.push([lat, lng]);

        // Log marker coordinates
        console.log("Marker added at:", [lat, lng]);
    });

    // Event listener for the "Add Field" button to create polygon from markers
    const addFieldButton = document.querySelector(".add-field-button");
    addFieldButton.addEventListener("click", function() {
        if (markerCoordinates.length < 3) {
            alert("At least three points are required to draw a polygon.");
            return;
        }

        // Create a polygon from the marker coordinates
        const polygon = L.polygon(markerCoordinates, { color: 'blue' });
        drawnItems.addLayer(polygon);

        // Clear markers after creating the polygon
        markers.clearLayers();

        // Log all marker coordinates as polygon vertices
        console.log("Polygon created with vertices:", markerCoordinates);

        // Clear the stored coordinates
        markerCoordinates.length = 0;
    });
}

// Initialize map, setup toggle and polygon drawing when DOM is fully loaded
document.addEventListener("DOMContentLoaded", function() {
    const map = initializeMap();
    setupInfoPanelToggle();
    setupPolygonDrawing(map);
});
