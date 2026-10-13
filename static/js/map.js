// Function to initialize and render the map in the 'map' div
function initializeMap() {
    // Initialize the map
    var map = L.map('map', {
        center: [0, 0],
        zoom: 2,
        zoomControl: true
    });

    // Define base layers
    var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    var satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: 'Tiles © Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    });

    // Create layer control object
    var baseLayers = {
        "OpenStreetMap": osmLayer,
        "Satellite": satelliteLayer
    };

    // Add built-in layer control
    L.control.layers(baseLayers, null, {
        position: 'topright',
        collapsed: false
    }).addTo(map);

    // Layer switcher functionality for custom dropdown
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

    // Configure draw control
    var drawControl = new L.Control.Draw({
        position: 'topright',
        edit: {
            featureGroup: drawnItems,
            poly: {
                allowIntersection: false
            }
        },
        draw: {
            polygon: {
                allowIntersection: false,
                showArea: true
            },
            polyline: false,
            circle: false,
            rectangle: false,
            marker: false,
            circlemarker: false
        }
    });
    map.addControl(drawControl);

    // Handle polygon creation
    map.on(L.Draw.Event.CREATED, function(event) {
        var layer = event.layer;
        var coordinates = layer.getLatLngs()[0].map(function(latlng) {
            return [latlng.lat, latlng.lng];
        });
        
        // Add the new layer to the feature group
        drawnItems.addLayer(layer);
        
        // Calculate area (in hectares)
        var area = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
        var areaHectares = (area / 10000).toFixed(2); // Convert square meters to hectares
        
        // Log the polygon data
        console.log({
            type: "Polygon",
            coordinates: coordinates,
            areaHectares: areaHectares
        });
    });

    // Handle polygon modification
    map.on(L.Draw.Event.EDITED, function(event) {
        var layers = event.layers;
        layers.eachLayer(function(layer) {
            var coordinates = layer.getLatLngs()[0].map(function(latlng) {
                return [latlng.lat, latlng.lng];
            });
            
            // Calculate new area
            var area = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
            var areaHectares = (area / 10000).toFixed(2);
            
            // Log the updated polygon data
            console.log({
                type: "Polygon Updated",
                coordinates: coordinates,
                areaHectares: areaHectares
            });
        });
    });

    // Handle polygon deletion
    map.on(L.Draw.Event.DELETED, function(event) {
        var layers = event.layers;
        layers.eachLayer(function(layer) {
            console.log("Polygon deleted");
        });
    });

    // Add scale control
    L.control.scale({
        imperial: false,
        position: 'bottomleft'
    }).addTo(map);

    // Handle info panel toggle
    var toggleButton = document.getElementById('toggleButton');
    var infoPanel = document.querySelector('.info-panel');
    
    if (toggleButton && infoPanel) {
        toggleButton.addEventListener('click', function() {
            infoPanel.classList.toggle('hidden');
            toggleButton.textContent = infoPanel.classList.contains('hidden') ? 
                'Show Info Panel' : 'Hide Info Panel';
        });
    }
}

// Initialize map when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
});