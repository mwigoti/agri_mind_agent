// Function to initialize and render the map in the 'map' div
require([
    "esri/map", 
    "esri/layers/ArcGISTiledMapServiceLayer",
    "dojo/domReady!"
], function(Map, ArcGISTiledMapServiceLayer) {

    // Initialize the map with a hybrid (satellite + labels) basemap
    var map = new Map("map", {
        basemap: "hybrid",
        center: [-98.5795, 39.8283],
        zoom: 4
    });

    // URL for World Boundaries and Places
    var boundariesURL = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer";
    var boundariesLayer = new ArcGISTiledMapServiceLayer(boundariesURL);

    // Layer switching functionality
    document.getElementById("layerSelect").addEventListener("change", function(e) {
        map.removeAllLayers();

        if (e.target.value === "osm") {
            map.setBasemap("streets");
        } else if (e.target.value === "satellite") {
            map.setBasemap("hybrid"); // Satellite with labels
        } else if (e.target.value === "satelliteBoundaries") {
            map.setBasemap("hybrid"); // Base map for satellite
            map.addLayer(boundariesLayer); // Add boundaries and places
        }
    });
});
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
        if (isDrawingMode) return;

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



setupInfoPanelToggle();
setupPolygonDrawing(map);
