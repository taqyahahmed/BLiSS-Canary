from fastapi import FastAPI

app = FastAPI(title="CANARY API")


@app.get("/")
def home():
    return {"message": "CANARY API is running!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}