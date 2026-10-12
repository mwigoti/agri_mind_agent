// Wait for DOM to be fully loaded before running any code
document.addEventListener('DOMContentLoaded', function() {
    // Initialize map-related functionality
    initializeMap();
});

// Function to initialize and render the map in the 'map' div
function initializeMap() {
    // Check if map container exists
    const mapContainer = document.getElementById('map');
    if (!mapContainer) {
        console.error('Map container not found');
        return;
    }

    try {
        // Initialize the map with error handling
        const map = new L.Map(mapContainer, {
            center: [0, 0],
            zoom: 2,
            zoomControl: true
        });

        // Define base layers
        const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 19,
            attribution: 'Tiles © Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
        });

        // Create layer control object
        const baseLayers = {
            "OpenStreetMap": osmLayer,
            "Satellite": satelliteLayer
        };

        // Add built-in layer control
        L.control.layers(baseLayers, null, {
            position: 'topright',
            collapsed: false
        }).addTo(map);

        // Add a feature group to hold drawn items
        const drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // Configure draw control
        const drawControl = new L.Control.Draw({
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
            const layer = event.layer;
            const coordinates = layer.getLatLngs()[0].map(function(latlng) {
                return [latlng.lat, latlng.lng];
            });
            
            // Add the new layer to the feature group
            drawnItems.addLayer(layer);
            
            // Calculate area (in hectares)
            const area = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
            const areaHectares = (area / 10000).toFixed(2); // Convert square meters to hectares
            
            // Update the area display if it exists
            const areaDisplay = document.querySelector('.info-header p');
            if (areaDisplay) {
                areaDisplay.textContent = `${areaHectares} ha`;
            }
            
            // Log the polygon data
            console.log({
                type: "Polygon",
                coordinates: coordinates,
                areaHectares: areaHectares
            });
        });

        // Handle polygon modification
        map.on(L.Draw.Event.EDITED, function(event) {
            const layers = event.layers;
            let totalArea = 0;
            
            layers.eachLayer(function(layer) {
                const coordinates = layer.getLatLngs()[0].map(function(latlng) {
                    return [latlng.lat, latlng.lng];
                });
                
                // Calculate new area
                const area = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
                const areaHectares = (area / 10000);
                totalArea += areaHectares;
                
                // Log the updated polygon data
                console.log({
                    type: "Polygon Updated",
                    coordinates: coordinates,
                    areaHectares: areaHectares.toFixed(2)
                });
            });

            // Update the area display if it exists
            const areaDisplay = document.querySelector('.info-header p');
            if (areaDisplay) {
                areaDisplay.textContent = `${totalArea.toFixed(2)} ha`;
            }
        });

        // Handle polygon deletion
        map.on(L.Draw.Event.DELETED, function(event) {
            // Update the area display to 0 when polygons are deleted
            const areaDisplay = document.querySelector('.info-header p');
            if (areaDisplay) {
                areaDisplay.textContent = '0 ha';
            }
            
            console.log("Polygon deleted");
        });

        // Add scale control
        L.control.scale({
            imperial: false,
            position: 'bottomleft'
        }).addTo(map);

        // Set up layer switcher functionality (if element exists)
        const layerSelect = document.getElementById('layerSelect');
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


    } catch (error) {
        console.error('Error initializing map:', error);
    }
}