import uvicorn

uvicorn.run("layer_2.api:app", host="127.0.0.1", port=8000, reload=False)
