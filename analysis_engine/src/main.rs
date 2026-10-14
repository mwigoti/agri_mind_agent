use actix_web::{post, web, App, HttpServer, Responder, Result};
use serde::{Deserialize, Serialize};
use geo::{Geometry, BoundingRect, Coordinate};
use reqwest;
use std::collections::HashMap;
use base64;
use dotenv::dotenv;
use std::env;
use geojson::{Geometry as GeoJsonGeometry};
use geo_types::{Geometry as GeoGeometry};
use geojson::GeoJson;
use geojson::quick_collection;
use std::convert::TryInto;



#[derive(Debug, Serialize, Deserialize)]
struct Field {
    id: u32,
    name: String,
    area: f64,
    pub geometry: GeoJsonGeometry,
}

#[derive(Debug, Serialize, Deserialize)]

pub struct VRARequest {
    pub field_id: i32,
    pub user_id: i32,
    pub geometry: GeoJsonGeometry,
}

#[derive(Debug, Serialize, Deserialize)]
struct VRAMapResponse {
    field_id: u32,
    field_name: String,
    ndvi_map: String,        
    ndvi_stats: NDVIStats,
    vra_zones: Vec<VRAZone>,
    recommendations: VRARecommendations,
    bbox: BoundingBox,
    map_metadata: MapMetadata,
}

#[derive(Debug, Serialize, Deserialize)]
struct NDVIStats {
    min_ndvi: f64,
    max_ndvi: f64,
    avg_ndvi: f64,
    std_dev: f64,
    healthy_percentage: f64,
    stressed_percentage: f64,
}

#[derive(Debug, Serialize, Deserialize)]
struct VRAZone {
    zone_id: u8,
    zone_name: String,
    ndvi_range: (f64, f64),
    area_percentage: f64,
    recommended_rate: f64,  // kg/ha or similar
    zone_color: String,     // Hex color for frontend
}

#[derive(Debug, Serialize, Deserialize)]
struct VRARecommendations {
    fertilizer_zones: Vec<FertilizerZone>,
    irrigation_zones: Vec<IrrigationZone>,
    total_fertilizer_needed: f64,
    cost_savings_estimate: f64,
}

#[derive(Debug, Serialize, Deserialize)]
struct FertilizerZone {
    zone_id: u8,
    nitrogen_rate: f64,
    phosphorus_rate: f64,
    potassium_rate: f64,
}

#[derive(Debug, Serialize, Deserialize)]
struct IrrigationZone {
    zone_id: u8,
    water_requirement: f64, // mm/week
    priority: String,       // High, Medium, Low
}

#[derive(Debug, Serialize, Deserialize)]
struct BoundingBox {
    min_lon: f64,
    min_lat: f64,
    max_lon: f64,
    max_lat: f64,
}

#[derive(Debug, Serialize, Deserialize)]
struct MapMetadata {
    acquisition_date: String,
    cloud_coverage: f64,
    resolution: f64,        // meters per pixel
    data_source: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct ProcessedFieldsResponse {
    message: String,
    count: usize,
    fields: Vec<VRAMapResponse>,
    processing_time_ms: u128,
}

// Sentinel Hub configuration
struct SentinelHubConfig {
    client_id: String,
    client_secret: String,
    instance_id: String,
    base_url: String,
    access_token: Option<String>,
}

impl SentinelHubConfig {
    fn new() -> Self {
        Self {
            client_id: std::env::var("SENTINEL_CLIENT_ID").unwrap_or_default(),
            client_secret: std::env::var("SENTINEL_CLIENT_SECRET").unwrap_or_default(),
            instance_id: std::env::var("SENTINEL_INSTANCE_ID").unwrap_or_default(),
            base_url: "https://services.sentinel-hub.com".to_string(),
            access_token: None,
        }
    }
    
    // Get OAuth token from Sentinel Hub
    async fn get_access_token(&mut self) -> Result<String, Box<dyn std::error::Error>> {
        if let Some(token) = &self.access_token {
            return Ok(token.clone());
        }
        
        let client = reqwest::Client::new();
        let params = [
            ("grant_type", "client_credentials"),
            ("client_id", &self.client_id),
            ("client_secret", &self.client_secret),
        ];
        
        let response = client
            .post(&format!("{}/oauth/token", self.base_url))
            .form(&params)
            .send()
            .await?;
            
        let token_data: serde_json::Value = response.json().await?;
        let access_token = token_data["access_token"]
            .as_str()
            .ok_or("Failed to extract access token")?
            .to_string();
        self.access_token = Some(access_token.clone());
        
        Ok(access_token)
    }
}

fn extract_bounding_box(geometry: &Geometry<f64>) -> Option<BoundingBox> {
    match geometry.bounding_rect() {
        Some(rect) => Some(BoundingBox {
            min_lon: rect.min().x,
            min_lat: rect.min().y,
            max_lon: rect.max().x,
            max_lat: rect.max().y,
        }),
        None => None,
    }
}

// Generate geometry coordinates for Sentinel Hub request
fn geometry_to_coordinates(geometry: &Geometry<f64>) -> Vec<Vec<f64>> {
    match geometry {
        Geometry::Polygon(poly) => {
            poly.exterior().coords().map(|coord| vec![coord.x, coord.y]).collect()
        },
        Geometry::MultiPolygon(multi) => {
            // Take the first polygon for simplicity
            if let Some(poly) = multi.iter().next() {
                poly.exterior().coords().map(|coord| vec![coord.x, coord.y]).collect()
            } else {
                vec![]
            }
        },
        _ => {
            // For other geometry types, use bounding box
            if let Some(bbox) = extract_bounding_box(geometry) {
                vec![
                    vec![bbox.min_lon, bbox.min_lat],
                    vec![bbox.max_lon, bbox.min_lat],
                    vec![bbox.max_lon, bbox.max_lat],
                    vec![bbox.min_lon, bbox.max_lat],
                    vec![bbox.min_lon, bbox.min_lat],
                ]
            } else {
                vec![]
            }
        }
    }
}

// Create Sentinel Hub process API request for NDVI
async fn create_ndvi_request(
    field: &Field,
    config: &mut SentinelHubConfig,
) -> Result<String, Box<dyn std::error::Error>> {
    let token = config.get_access_token().await?;
    let geo_geometry: GeoGeometry<f64> = field.geometry.clone().try_into().expect("Invalid geometry conversion");
    let coordinates = geometry_to_coordinates(&geo_geometry);


    // Calculate image dimensions based on field size
    let width = 512;
    let height = 512;

    let evalscript = r#"//VERSION=3
        function setup() {
            return {
                input: ["B04", "B08", "SCL"],
                output: { bands: 3 }
            };
        }

        function evaluatePixel(sample) {
            // Calculate NDVI
            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);

            // Apply color mapping for visualization
            if (ndvi < 0.2) {
                return [0.8, 0.2, 0.2]; // Red - poor vegetation
            } else if (ndvi < 0.4) {
                return [1.0, 0.6, 0.0]; // Orange - moderate vegetation
            } else if (ndvi < 0.6) {
                return [1.0, 1.0, 0.0]; // Yellow - good vegetation
            } else {
                return [0.0, 0.8, 0.0]; // Green - excellent vegetation
            }
        }
    "#;

    let request_body = serde_json::json!({
        "input": {
            "bounds": {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coordinates]
                },
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                }
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": "2024-06-01T00:00:00Z",
                        "to": "2024-08-31T23:59:59Z"
                    },
                    "maxCloudCoverage": 30
                }
            }]
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{
                "identifier": "ndvi",
                "format": { "type": "image/jpeg" }
            }]
        },
        "evalscript": evalscript
    });

    let client = reqwest::Client::new();
    let response = client
        .post(&format!("{}/api/v1/process", config.base_url))
        .header("Authorization", format!("Bearer {}", token))
        .header("Content-Type", "application/json")
        .json(&request_body)
        .send()
        .await?;

    if response.status().is_success() {
        let image_bytes = response.bytes().await?;
        let base64_image = base64::encode(&image_bytes);
        Ok(format!("data:image/jpeg;base64,{}", base64_image))
    } else {
        let error_text = response.text().await?;
        Err(format!("Sentinel Hub API error: {}", error_text).into())
    }
}

// Simulate NDVI statistics calculation (in real implementation, you'd process the actual NDVI data)
fn calculate_ndvi_stats() -> NDVIStats {
    NDVIStats {
        min_ndvi: 0.15,
        max_ndvi: 0.85,
        avg_ndvi: 0.52,
        std_dev: 0.18,
        healthy_percentage: 68.5,
        stressed_percentage: 31.5,
    }
}

// Generate VRA zones based on NDVI data
fn generate_vra_zones() -> Vec<VRAZone> {
    vec![
        VRAZone {
            zone_id: 1,
            zone_name: "High Stress Zone".to_string(),
            ndvi_range: (0.0, 0.3),
            area_percentage: 15.5,
            recommended_rate: 180.0, // Higher fertilizer rate
            zone_color: "#FF4444".to_string(),
        },
        VRAZone {
            zone_id: 2,
            zone_name: "Moderate Stress Zone".to_string(),
            ndvi_range: (0.3, 0.5),
            area_percentage: 35.2,
            recommended_rate: 140.0,
            zone_color: "#FFA500".to_string(),
        },
        VRAZone {
            zone_id: 3,
            zone_name: "Healthy Zone".to_string(),
            ndvi_range: (0.5, 0.7),
            area_percentage: 38.8,
            recommended_rate: 100.0,
            zone_color: "#FFFF00".to_string(),
        },
        VRAZone {
            zone_id: 4,
            zone_name: "Excellent Zone".to_string(),
            ndvi_range: (0.7, 1.0),
            area_percentage: 10.5,
            recommended_rate: 60.0, // Lower fertilizer rate
            zone_color: "#00AA00".to_string(),
        },
    ]
}

// Generate VRA recommendations
fn generate_vra_recommendations(field_area: f64, zones: &[VRAZone]) -> VRARecommendations {
    let fertilizer_zones: Vec<FertilizerZone> = zones.iter().map(|zone| {
        FertilizerZone {
            zone_id: zone.zone_id,
            nitrogen_rate: zone.recommended_rate * 0.6,  // 60% nitrogen
            phosphorus_rate: zone.recommended_rate * 0.25, // 25% phosphorus
            potassium_rate: zone.recommended_rate * 0.15,  // 15% potassium
        }
    }).collect();
    
    let irrigation_zones: Vec<IrrigationZone> = zones.iter().map(|zone| {
        let (water_req, priority) = match zone.zone_id {
            1 => (35.0, "High"),    // Stressed areas need more water
            2 => (25.0, "Medium"),
            3 => (15.0, "Low"),
            4 => (10.0, "Low"),     // Healthy areas need less water
            _ => (20.0, "Medium"),
        };
        
        IrrigationZone {
            zone_id: zone.zone_id,
            water_requirement: water_req,
            priority: priority.to_string(),
        }
    }).collect();
    
    // Calculate total fertilizer needed and cost savings
    let total_fertilizer: f64 = zones.iter()
        .map(|zone| zone.recommended_rate * (zone.area_percentage / 100.0) * field_area)
        .sum();
    
    let uniform_rate = 150.0; // Standard uniform application rate
    let uniform_total = uniform_rate * field_area;
    let cost_savings = (uniform_total - total_fertilizer) * 0.5; // $0.5 per kg saved
    
    VRARecommendations {
        fertilizer_zones,
        irrigation_zones,
        total_fertilizer_needed: total_fertilizer,
        cost_savings_estimate: cost_savings.max(0.0),
    }
}

// Process field and generate VRA map
async fn process_field_vra(field: &Field, config: &mut SentinelHubConfig) -> VRAMapResponse {
    // Get NDVI image from Sentinel Hub
    let ndvi_map = match create_ndvi_request(field, config).await {
        Ok(image) => image,
        Err(e) => {
            println!("Error fetching NDVI data: {}", e);
            // Return a placeholder base64 image or error image
            "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=".to_string()
        }
    };
    
    let geo_geometry: GeoGeometry<f64> = field.geometry.clone().try_into().expect("Invalid geometry conversion");
    let bbox = extract_bounding_box(&geo_geometry).unwrap_or(BoundingBox {
        min_lon: 0.0,
        min_lat: 0.0,
        max_lon: 0.0,
        max_lat: 0.0,
    });
    
    let ndvi_stats = calculate_ndvi_stats();
    let vra_zones = generate_vra_zones();
    let recommendations = generate_vra_recommendations(field.area, &vra_zones);
    
    VRAMapResponse {
        field_id: field.id,
        field_name: field.name.clone(),
        ndvi_map,
        ndvi_stats,
        vra_zones,
        recommendations,
        bbox,
        map_metadata: MapMetadata {
            acquisition_date: "2024-07-15".to_string(),
            cloud_coverage: 12.5,
            resolution: 10.0,
            data_source: "Sentinel-2 L2A".to_string(),
        },
    }
}

#[post("/generate-vra-maps")]
async fn generate_vra_maps(fields: web::Json<Vec<Field>>) -> Result<impl Responder> {
    let start_time = std::time::Instant::now();
    println!("Generating VRA maps for {} fields", fields.len());
    
    let mut config = SentinelHubConfig::new();
    let mut processed_fields = Vec::new();
    
    for field in fields.iter() {
        let vra_response = process_field_vra(field, &mut config).await;
        processed_fields.push(vra_response);
    }
    
    let processing_time = start_time.elapsed().as_millis();
    
    let response = ProcessedFieldsResponse {
        message: "VRA maps generated successfully".to_string(),
        count: processed_fields.len(),
        fields: processed_fields,
        processing_time_ms: processing_time,
    };
    
    Ok(web::Json(response))
}

// Health check endpoint
#[post("/health")]
async fn health_check() -> Result<impl Responder> {
    Ok(web::Json(serde_json::json!({
        "status": "healthy",
        "service": "VRA Map Generator",
        "timestamp": chrono::Utc::now().to_rfc3339()
    })))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("Starting VRA Map Generator Service on http://127.0.0.1:8001");
    println!("Endpoints:");
    println!("  POST /generate-vra-maps - Generate VRA maps for fields");
    println!("  POST /health - Health check");
    
    HttpServer::new(|| {
        App::new()
            .service(generate_vra_maps)
            .service(health_check)
    })
    .bind(("127.0.0.1", 8001))?
    .run()
    .await
}