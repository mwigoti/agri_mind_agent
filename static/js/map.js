// Function to initialize and render the map in the 'map' div
function initializeMap() {
    // Access the div with id 'map' and initialize the map
    var map = L.map('map').setView([0, 0], 2); // Adjust as necessary

    // Define base layers
    var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Esri Satellite Layer
    var satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: 'Tiles © Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    });

    // Layer switcher functionality
    var layerSelect = document.getElementById('layerSelect');
    if (layerSelect) {
        layerSelect.addEventListener('change', function(e) {
            if (e.target.value === 'osm') {
                if (map.hasLayer(satelliteLayer)) map.removeLayer(satelliteLayer);
                if (!map.hasLayer(osmLayer)) map.addLayer(osmLayer);
            } else if (e.target.value === 'satellite') {
                if (map.hasLayer(osmLayer)) map.removeLayer(osmLayer);
                if (!map.hasLayer(satelliteLayer)) map.addLayer(satelliteLayer);
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
