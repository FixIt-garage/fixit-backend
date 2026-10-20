from fastapi import FastAPI

app = FastAPI(title="FixIt API")


@app.get("/")
def root():
    return {"name": "FixIt API"}