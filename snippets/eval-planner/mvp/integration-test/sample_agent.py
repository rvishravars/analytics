from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Sample Agent")

class JobRequest(BaseModel):
    input_data: dict

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/execute")
def execute_job(job: JobRequest):
    # Mock execution logic
    print(f"Executing job with input: {job.input_data}")
    return {"status": "completed", "result": "mock_result"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
