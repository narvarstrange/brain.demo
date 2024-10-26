from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yfinance as yf
from groq import Groq, GroqError
import os
import logging
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import json  # Add json for pretty printing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize Groq client with API key from environment variable
api_key = os.getenv("GROQ_API_KEY", "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")
if not api_key:
    raise ValueError("The GROQ_API_KEY environment variable is not set.")

client = Groq(api_key=api_key)

# Define Pydantic models for request and response
class InsightsRequest(BaseModel):
    ticker: str
    value_proposition: str

class FinancialData(BaseModel):
    balance_sheet: dict
    income_statement: dict
    cash_flow: dict

class GraphData(BaseModel):
    query: str
    result: list
    answer: dict

class InsightsResponse(BaseModel):
    financial_data: FinancialData
    insights: dict
    graphs: dict

# Function to get financial data and validate the ticker
def get_financial_data(ticker: str):
    stock = yf.Ticker(ticker)
    try:
        balance_sheet = stock.balance_sheet
        income_statement = stock.financials
        cash_flow = stock.cashflow
        
        # Check if the financial data is not empty
        if balance_sheet.empty or income_statement.empty or cash_flow.empty:
            raise ValueError("Invalid ticker symbol or no data available.")
        
        return balance_sheet, income_statement, cash_flow
    except Exception as e:
        logger.error(f"Error fetching financial data: {e}")
        raise HTTPException(status_code=400, detail=f"Error fetching financial data: {e}")

# Function to generate insights using Groq API
def generate_insights_from_groq(prompt_text: str) -> str:
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt_text}],
            model="llama3-8b-8192",
        )
        return chat_completion.choices[0].message.content
    except GroqError as e:
        logger.error(f"Error generating insights: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating insights: {e}")

# Function to generate graph data from financial data
def generate_graph_data(financial_data: dict) -> dict:
    graphs = {}
    
    for date, data in financial_data['balance_sheet'].items():
        graph_data = {
            'query': f"Plot a bar chart for the balance sheet data on {date}",
            'result': [(key, value) for key, value in data.items() if isinstance(value, (int, float))],
            'answer': {
                'message': 'The bar chart has been plotted successfully',
                'type': 'Bar Chart',
                'data': [{'label': key, 'value': value, 'valueColor': 'hsl(120, 70%, 50%)'} for key, value in data.items() if isinstance(value, (int, float))]
            }
        }
        graphs[date] = graph_data
    
    return graphs

@app.post("/generate_insights", response_model=InsightsResponse)
def generate_insights(request: InsightsRequest):
    ticker = request.ticker
    value_proposition = request.value_proposition
    
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker value cannot be empty.")
    if not value_proposition:
        raise HTTPException(status_code=400, detail="Value proposition cannot be empty.")
    
    # Fetch financial data
    balance_sheet, income_statement, cash_flow = get_financial_data(ticker)
    
    # Convert financial data to dictionary for JSON response
    financial_data = {
        "balance_sheet": balance_sheet.to_dict(),
        "income_statement": income_statement.to_dict(),
        "cash_flow": cash_flow.to_dict()
    }
    
    # Generate insights
    sections = [
        "Earnings Data Analysis", 
        "Financial Data Analysis", 
        "Brainstorm Values", 
        "Financial Prediction",
        "Key Competitors",
        value_proposition
    ]

    insights = {}
    for section in sections:
        prompt = f"""
        Section: {section}
        Company: {ticker}
        Value Proposition: {value_proposition}
        
        Analyze the information and provide detailed insights.
        """
        if section == "Key Competitors":
            prompt = f"""
            Section: {section}
            Company: {ticker}   
            Value Proposition: {value_proposition}
            
            Identify and analyze key competitors of the company.
            """
        response_text = generate_insights_from_groq(prompt)
        insights[section] = response_text
    
    # Generate graph data
    graphs = generate_graph_data(financial_data)
    
    # Combine financial data, insights, and graphs into a single dictionary
    result = {
        "financial_data": financial_data,
        "insights": insights,
        "graphs": graphs
    }

    # Log and print the result here
    logger.info("Generated Insights Data: %s", json.dumps(result, indent=4))
    
    return result

# For CORS support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "API is running"}

handler = Mangum(app)

# Uncomment for local testing
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
