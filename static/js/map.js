// Initialize the map and set the view to a specific location and zoom level
var map = L.map('map').setView([0, 0], 2); // Adjust as necessary

// Base layers
var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

var terrainLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    maxZoom: 17,
    attribution: '© OpenTopoMap contributors'
});

// Layer switcher
document.getElementById('layerSelect').addEventListener('change', function(e) {
    if (e.target.value === 'osm') {
        map.removeLayer(terrainLayer);
        map.addLayer(osmLayer);
    } else if (e.target.value === 'terrain') {
        map.removeLayer(osmLayer);
        map.addLayer(terrainLayer);
    }
});

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
