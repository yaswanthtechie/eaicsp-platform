from fastapi import FastAPI
from app.routes.shipment import router

app=FastAPI()
app.include_router(router)
@app.get("/")
def home():
    return{
        "message":"Logistics Service is running"
    }