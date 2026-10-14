import os

import uvicorn

port = int(os.getenv("PORT", "8001"))
uvicorn.run("agentic_layer_2.api:app", host="127.0.0.1", port=port, reload=False)
