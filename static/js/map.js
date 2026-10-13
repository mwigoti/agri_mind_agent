// Function to initialize and render the map in the 'map' div
function initializeMap() {
    const map = L.map('map').setView([0, 0], 2);

    // Define base layers
    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    const satelliteLayer = L.esri.basemapLayer('Imagery');
    const boundariesLayer = L.esri.basemapLayer('ImageryLabels');

    // Layer switcher functionality
    const layerSelect = document.getElementById('layerSelect');
    if (layerSelect) {
        layerSelect.addEventListener('change', function(e) {
            map.eachLayer(function(layer) {
                if (!layer._isDrawingLayer) {  // Preserve drawing layers
                    map.removeLayer(layer);
                }
            });

            if (e.target.value === 'osm') {
                map.addLayer(osmLayer);
            } else if (e.target.value === 'satellite') {
                map.addLayer(satelliteLayer);
            } else if (e.target.value === 'satelliteBoundaries') {
                map.addLayer(satelliteLayer);
                map.addLayer(boundariesLayer);
            }
        });
    }

    return map;
}

function setupInfoPanelToggle() {
    const infoPanel = document.querySelector(".info-panel");
    const toggleButton = document.querySelector(".menu ul nav li:first-child");

    if (!infoPanel || !toggleButton) {
        console.error("Required elements not found.");
        return;
    }

    infoPanel.style.display = "block";
    toggleButton.addEventListener("click", function() {
        const isVisible = infoPanel.style.display === "block";
        infoPanel.style.display = isVisible ? "none" : "block";
        toggleButton.textContent = isVisible ? "Show Info Panel" : "Hide Info Panel";
    });
}

function setupPolygonDrawing(map) {
    let isDrawingMode = true;
    let markerCoordinates = [];
    let markers = new L.FeatureGroup();
    let polygons = new L.FeatureGroup();
    
    // Add layers to map and mark them as drawing layers
    markers._isDrawingLayer = true;
    polygons._isDrawingLayer = true;
    map.addLayer(markers);
    map.addLayer(polygons);

    // Map click handler
    function handleMapClick(e) {
        if (!isDrawingMode) return;

        const { lat, lng } = e.latlng;
        
        // Add marker
        const marker = L.marker([lat, lng]).addTo(markers);
        markerCoordinates.push([lat, lng]);
        
        // If we have 3 or more points, draw/update the polygon
        if (markerCoordinates.length >= 3) {
            // Remove existing temporary polygon if it exists
            polygons.clearLayers();
            
            // Create new polygon
            const polygon = L.polygon(markerCoordinates, {
                color: 'green',
                fillColor: 'green',
                fillOpacity: 0.3
            });
            polygons.addLayer(polygon);
        }

        console.log("Marker added at:", [lat, lng]);
    }

    // Add Field button handler
    const addFieldButton = document.querySelector(".add-field-button");
    addFieldButton.addEventListener("click", function() {
        if (!isDrawingMode) {
            // Start drawing mode
            isDrawingMode = true;
            addFieldButton.textContent = "FINISH FIELD";
            addFieldButton.style.backgroundColor = "#ff4444";
            map.on('click', handleMapClick);
        } else {
            // End drawing mode
            isDrawingMode = false;
            addFieldButton.textContent = "+ ADD FIELD";
            addFieldButton.style.backgroundColor = "";
            map.off('click', handleMapClick);

            if (markerCoordinates.length < 3) {
                alert("At least three points are required to create a field.");
                markers.clearLayers();
                markerCoordinates = [];
                return;
            }

            // Log final polygon coordinates
            console.log("Field created with coordinates:", markerCoordinates);
            
            // Reset for next field
            markers.clearLayers();
            markerCoordinates = [];
        }
    });
}

// Initialize everything when DOM is loaded
document.addEventListener("DOMContentLoaded", function() {
    const map = initializeMap();
    setupInfoPanelToggle();
    setupPolygonDrawing(map);
});