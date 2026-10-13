use actix_web::{post, web, App, HttpServer, Responder};
use serde::Deserialize;
use geo::Geometry;
#[derive(Debug, Deserialize)]


struct Field {
    id: u32,
    name: String,
    area: f64,
    geometry: Geometry<f64>,
}


#[post("/receive-data")]
async fn receive_data(fields: web::Json<Vec<Field>>) -> impl Responder {
    println!("Received data from Django: {:?}", fields);
    web::Json(serde_json::json!({
        "message": "Rust engine processed data successfully",
        "count": fields.len()
    }))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .service(receive_data)
    })
    .bind(("127.0.0.1", 8001))?
    .run()
    .await
}
