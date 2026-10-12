// Function to initialize and render the map in the 'map' div
function initializeMap() {
    // Access the div with id 'map' and initialize the map
    var map = L.map('map').setView([0, 0], 2); // Adjust as necessary

    // Define base layers
    var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Esri World Imagery Layer
    var satelliteLayer = L.esri.basemapLayer('Imagery');

    // Esri World Boundaries and Places Reference Layer
    var boundariesLayer = L.esri.basemapLayer('ImageryLabels');

    // Layer switcher functionality
    var layerSelect = document.getElementById('layerSelect');
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
    var drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    // Add draw control to the map for polygon drawing
    var drawControl = new L.Control.Draw({
        edit: {
            featureGroup: drawnItems
        },
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
        var layer = event.layer;
        var coordinates = layer.getLatLngs()[0].map(function(latlng) {
            return [latlng.lat, latlng.lng];
        });
        console.log("Polygon coordinates:", coordinates); // Replace with integration to soil analysis algorithm

        drawnItems.addLayer(layer);
    });
}

// Wait until DOM is fully loaded before initializing the map
document.addEventListener("DOMContentLoaded", initializeMap);

document.addEventListener("DOMContentLoaded", function() {
    const infoPanel = document.querySelector(".info-panel");
    const hideInfoPanelButton = document.querySelector(".menu ul li:first-child");

    // Ensure the panel is visible by default
    infoPanel.style.display = "block";

    // Toggle visibility on button click
    hideInfoPanelButton.addEventListener("click", function() {
        if (infoPanel.style.display === "block") {
            infoPanel.style.display = "none";
            hideInfoPanelButton.textContent = "Show Info Panel";
        } else {
            infoPanel.style.display = "block";
            hideInfoPanelButton.textContent = "Hide Info Panel";
        }
    });
});

