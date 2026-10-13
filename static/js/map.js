document.addEventListener("DOMContentLoaded", function() {
    // Initialize the map using Esri ArcGIS API
    require([
        "esri/map", 
        "esri/layers/ArcGISTiledMapServiceLayer",
        "esri/graphic",
        "esri/geometry/Polygon",
        "esri/geometry/Point",
        "esri/symbols/SimpleMarkerSymbol",
        "esri/symbols/SimpleFillSymbol",
        "esri/Color",
        "dojo/domReady!"
    ], function(Map, ArcGISTiledMapServiceLayer, Graphic, Polygon, Point, SimpleMarkerSymbol, SimpleFillSymbol, Color) {
        
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
        var layerSelect = document.getElementById("layerSelect");
        layerSelect.addEventListener("change", function(e) {
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

        // Setup info panel toggle functionality
        setupInfoPanelToggle();

        // Setup polygon drawing functionality with markers
        setupPolygonDrawing(map, Graphic, Polygon, Point, SimpleMarkerSymbol, SimpleFillSymbol, Color);
    });
});

// Toggle Info Panel functionality
function setupInfoPanelToggle() {
    const infoPanel = document.querySelector(".info-panel");
    const toggleButton = document.querySelector(".menu ul li:first-child");

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

// Function to enable marker-based polygon drawing
function setupPolygonDrawing(map, Graphic, Polygon, Point, SimpleMarkerSymbol, SimpleFillSymbol, Color) {
    let isDrawingMode = false;
    let markerCoordinates = [];
    const markers = []; // Array to store marker graphics

    // Function to handle map click and add markers
    function handleMapClick(event) {
        if (!isDrawingMode) return;

        // Add a red marker at the clicked location
        const point = new Point(event.mapPoint.x, event.mapPoint.y, map.spatialReference);
        const markerSymbol = new SimpleMarkerSymbol().setColor(new Color([255, 0, 0])).setSize(10);
        const markerGraphic = new Graphic(point, markerSymbol);
        map.graphics.add(markerGraphic);
        
        // Store marker coordinates and add marker to the array
        markerCoordinates.push([point.x, point.y]);
        markers.push(markerGraphic);

        // Draw polygon if there are at least 3 points
        if (markerCoordinates.length >= 3) {
            drawPolygon(markerCoordinates, map, Polygon, SimpleFillSymbol, Color);
        }

        console.log("Marker added at:", [point.x, point.y]);
    }

    // Function to draw a polygon based on stored marker coordinates
    function drawPolygon(coords, map, Polygon, SimpleFillSymbol, Color) {
        map.graphics.clear(); // Clear previous graphics

        const polygon = new Polygon(map.spatialReference);
        polygon.addRing(coords);

        const fillSymbol = new SimpleFillSymbol().setColor(new Color([0, 255, 0, 0.25]));
        const polygonGraphic = new Graphic(polygon, fillSymbol);
        map.graphics.add(polygonGraphic);
    }

    // Toggle drawing mode with the "Add Field" button
    const addFieldButton = document.querySelector(".add-field-button");
    addFieldButton.addEventListener("click", function() {
        isDrawingMode = !isDrawingMode;

        if (isDrawingMode) {
            addFieldButton.textContent = "Finish Field";
            addFieldButton.style.backgroundColor = "#ff4444";
            map.on("click", handleMapClick);
        } else {
            addFieldButton.textContent = "+ Add Field";
            addFieldButton.style.backgroundColor = "";

            // Complete drawing mode, validate coordinates
            map.off("click", handleMapClick);
            if (markerCoordinates.length < 3) {
                alert("At least three points are required to create a polygon.");
                resetDrawing(map, markers);
            } else {
                console.log("Polygon created with coordinates:", markerCoordinates);
            }

            // Reset coordinates and markers for the next field
            markerCoordinates = [];
            resetDrawing(map, markers);
        }
    });
}

// Helper function to reset drawing by clearing markers and coordinates
function resetDrawing(map, markers) {
    markers.forEach(marker => map.graphics.remove(marker));
    markers.length = 0;
}
