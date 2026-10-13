document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
});

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

        // Add satellite layer
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

        // Handle polygon creation, modification, and deletion (same as previous code)
        // ...

        // Add scale control
        L.control.scale({
            imperial: false,
            position: 'bottomleft'
        }).addTo(map);

        // Set up layer switcher functionality (if element exists)
        const layerSelect = document.getElementById('layerSelect');
        if (layerSelect) {
            layerSelect.addEventListener('change', function(e) {
                const selectedLayer = e.target.value;
                map.eachLayer(function(layer) {
                    if (layer instanceof L.TileLayer) {
                        if (selectedLayer === 'osm') {
                            if (layer !== osmLayer) {
                                map.removeLayer(layer);
                            }
                            if (!map.hasLayer(osmLayer)) {
                                map.addLayer(osmLayer);
                            }
                        } else if (selectedLayer === 'satellite') {
                            if (layer !== satelliteLayer) {
                                map.removeLayer(layer);
                            }
                            if (!map.hasLayer(satelliteLayer)) {
                                map.addLayer(satelliteLayer);
                            }
                        }
                    }
                });
            });
        }

        // Set up info panel toggle (if elements exist)
        const toggleButton = document.getElementById('toggleButton');
        const infoPanel = document.querySelector('.info-panel');
        
        if (toggleButton && infoPanel) {
            toggleButton.addEventListener('click', function() {
                infoPanel.classList.toggle('hidden');
                toggleButton.textContent = infoPanel.classList.contains('hidden') ? 
                    'Show Info Panel' : 'Hide Info Panel';
            });
        }

    } catch (error) {
        console.error('Error initializing map:', error);
    }
}