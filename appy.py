import streamlit as st
import requests
import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import google.generativeai as genai

# --- PAGE SETUP ---
st.set_page_config(page_title="Project Delivery Dashboard", layout="wide")
st.title("🚀 Project Delivery Dashboard")

# --- SECRETS & SETUP ---
# In Streamlit Cloud, you will store these securely in the settings.
# For now, Streamlit looks for them in st.secrets
LINEAR_API_KEY = st.secrets.get("LINEAR_API_KEY", "your_linear_key_here")
SLACK_TOKEN = st.secrets.get("SLACK_BOT_TOKEN", "your_slack_token_here")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "your_gemini_key_here")
SLACK_CHANNEL_ID = st.secrets.get("SLACK_CHANNEL_ID", "your_channel_id")

# --- FUNCTIONS ---

def get_linear_projects():
    """Fetches active projects and their progress from Linear."""
    url = "https://api.linear.app/graphql"
    headers = {"Authorization": LINEAR_API_KEY, "Content-Type": "application/json"}
    # GraphQL query to get project names, progress, and target dates
    query = """
    query {
      projects {
        nodes {
          name
          progress
          targetDate
          state
        }
      }
    }
    """
    response = requests.post(url, headers=headers, json={"query": query})
    if response.status_code == 200:
        return response.json().get("data", {}).get("projects", {}).get("nodes", [])
    else:
        st.error(f"Failed to fetch Linear data: {response.text}")
        return []

def get_latest_slack_thread(channel_id):
    """Fetches the latest messages from a Slack channel."""
    client = WebClient(token=SLACK_TOKEN)
    try:
        # Get the history of the channel (latest 5 messages to find a thread)
        result = client.conversations_history(channel=channel_id, limit=5)
        messages = result["messages"]
        if not messages:
            return "No messages found."
        
        # Combine the latest messages into a single text block
        chat_text = "\n".join([f"- {msg.get('text', '')}" for msg in messages if 'text' in msg])
        return chat_text
    except SlackApiError as e:
        return f"Error fetching Slack data: {e.response['error']}"

def calculate_rag(progress, target_date, velocity):
    """Calculates Red/Amber/Green status based on your formula."""
    if not target_date:
        return "⚪ Unknown (No Target Date)", "gray"
    
    # Calculate time until due date (in weeks)
    due_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
    today = datetime.date.today()
    days_until_due = (due_date - today).days
    weeks_until_due = max(days_until_due / 7.0, 0.1) # Avoid division by zero
    
    # Formula: Work Remaining (1.0 = 100%) / Velocity
    work_remaining = 1.0 - progress
    weeks_needed = work_remaining / velocity if velocity > 0 else 999
    
    if weeks_needed > weeks_until_due:
        return "🔴 RED (Off Track)", "red"
    elif weeks_needed > (weeks_until_due * 0.8):
        return "🟡 AMBER (At Risk)", "orange"
    else:
        return "🟢 GREEN (On Track)", "green"

def generate_ai_summary(project_data, slack_data):
    """Uses Gemini AI to write a summary of the dashboard."""
    if GEMINI_API_KEY == "your_gemini_key_here":
        return "Please add your Gemini API Key to generate an AI summary."
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are a Project Manager assistant. Summarize the current project statuses based on this data:
    Project Data: {project_data}
    Recent Slack Updates: {slack_data}
    
    Keep it strictly to 3 bullet points. Highlight the biggest risk.
    """
    response = model.generate_content(prompt)
    return response.text

# --- DASHBOARD UI ---

st.header("📊 Active Projects")

# Allow the user to adjust assumed weekly velocity for the hackathon MVP
team_velocity = st.sidebar.slider("Assumed Team Velocity (% per week)", min_value=1, max_value=50, value=10) / 100.0

linear_data = get_linear_projects()
slack_data = get_latest_slack_thread(SLACK_CHANNEL_ID)

if linear_data:
    for proj in linear_data:
        # Filter for active projects
        if proj.get('state') in ['canceled', 'completed']:
            continue
            
        name = proj.get("name", "Unnamed")
        progress = proj.get("progress", 0.0) # Linear returns 0.0 to 1.0
        target = proj.get("targetDate")
        
        # Calculate RAG
        rag_text, rag_color = calculate_rag(progress, target, team_velocity)
        
        with st.container():
            st.subheader(f"{name}")
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                # Progress bar (Multiply by 100 for display, simulated 14-day delta)
                st.progress(progress)
                st.caption(f"Current Progress: {int(progress * 100)}% (Simulated 14-day delta: +5%)")
            
            with col2:
                st.markdown(f"**Target:** {target if target else 'TBD'}")
            
            with col3:
                st.markdown(f"**Status:** :{rag_color}[{rag_text}]")
            st.divider()

st.header("💬 Latest Slack Updates")
with st.expander("View Recent Channel Activity"):
    st.write(slack_data)

st.header("✨ AI Executive Summary")
if st.button("Generate Summary"):
    with st.spinner("Analyzing projects and Slack chatter..."):
        summary = generate_ai_summary(linear_data, slack_data)
        st.info(summary)