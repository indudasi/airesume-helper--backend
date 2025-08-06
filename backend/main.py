from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import fitz
import docx
from openai import OpenAI
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fpdf import FPDF
import os

# FastAPI app
app = FastAPI()

# Serve templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
client = OpenAI(api_key="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")


# Database
Base = declarative_base()
engine = create_engine("sqlite:///feedback.db")
Session = sessionmaker(bind=engine)
session = Session()

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True)
    suggestion = Column(Text)
    decision = Column(String)

Base.metadata.create_all(engine)

# PDF/DOCX extract helpers
def extract_text_from_pdf(path):
    pdf = fitz.open(path)
    return "".join([page.get_text() for page in pdf])

def extract_text_from_docx(path):
    doc = docx.Document(path)
    return "\n".join([p.text for p in doc.paragraphs])

# Summarize function
def summarize_resume(resume_text):
    prompt = f"Summarize this resume into professional bullet points:\n{resume_text}"
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content

# API Endpoints
@app.post("/summarize_resume/")
async def summarize(file: UploadFile = File(...)):
    path = f"temp_{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())

    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(path)
    elif file.filename.endswith(".docx"):
        text = extract_text_from_docx(path)
    else:
        return {"error": "Unsupported format"}

    return {"summary": summarize_resume(text)}

@app.post("/match_resume/")
async def match(file: UploadFile = File(...), job_desc: str = Form(...)):
    path = f"temp_{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())

    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(path)
    elif file.filename.endswith(".docx"):
        text = extract_text_from_docx(path)
    else:
        return {"error": "Unsupported format"}

    prompt = f"""
    Compare the resume with this job description.
    Give:
    1. ATS match score (%)
    2. Missing keywords
    3. Improvement suggestions

    Resume:
    {text}

    Job Description:
    {job_desc}
    """
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return {"match_result": res.choices[0].message.content}

@app.post("/feedback/")
async def feedback(suggestion: str = Form(...), decision: str = Form(...)):
    fb = Feedback(suggestion=suggestion, decision=decision)
    session.add(fb)
    session.commit()
    return {"status": "saved"}

@app.post("/export_resume/")
async def export(bullets: str = Form(...)):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in bullets.split("\n"):
        pdf.multi_cell(0, 10, f"• {line}")
    pdf.output("resume.pdf")
    return {"status": "exported"}
