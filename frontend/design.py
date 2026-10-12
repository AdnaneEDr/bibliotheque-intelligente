"""Composants de présentation ; les valeurs affichées sont échappées."""
from html import escape
import streamlit as st

def theme():
    st.markdown('''<style>
    .stApp {background:#f6f8fc;color:#16243a}
    [data-testid="stSidebar"] {background:#10243b}
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] label {color:#edf4ff!important}
    [data-testid="stSidebar"] button {background:#233e5d;border-color:#3d5571}
    .block-container {max-width:1300px;padding-top:2rem;padding-bottom:3rem}
    h1,h2,h3 {color:#142c49;letter-spacing:-.025em}
    [data-testid="stMetric"] {background:white;border:1px solid #e3e9f1;border-radius:16px;padding:18px}
    [data-testid="stVerticalBlockBorderWrapper"] {background:white;border-radius:16px}
    .hero {background:linear-gradient(120deg,#122b49,#265c73);padding:32px;border-radius:22px;margin:8px 0 25px;color:white}
    .hero h2 {color:white;margin:0 0 10px;font-size:30px}
    .hero p {color:#d5e7ef;max-width:760px;font-size:16px;margin-bottom:0}
    .eyebrow {font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#68d8ca;margin-bottom:8px}
    .badge {display:inline-block;background:#e9f5f0;color:#176149;padding:4px 9px;border-radius:8px;font-size:12px;font-weight:600}
    .resource-title {font-size:19px;font-weight:700;line-height:1.35;color:#173650;margin:10px 0 8px}
    .resource-description {font-size:14px;color:#58677a;line-height:1.6;margin:8px 0 12px}
    .resource-meta {font-size:12px;color:#758396;margin-top:6px}
    div.stButton>button {border-radius:10px;min-height:40px;font-weight:600}
    [data-testid="stChatMessage"] {border:1px solid #e1e8ef;border-radius:14px;background:white}
    </style>''',unsafe_allow_html=True)

def hero(title,description,eyebrow='Votre bibliothèque, augmentée'):
    st.markdown(f'<div class="hero"><div class="eyebrow">{escape(eyebrow)}</div><h2>{escape(title)}</h2><p>{escape(description)}</p></div>',unsafe_allow_html=True)

def resource(title,category,description='',meta=''):
    st.markdown(f'<span class="badge">{escape(category)}</span><div class="resource-title">{escape(title)}</div><div class="resource-description">{escape(description)}</div><div class="resource-meta">{escape(meta)}</div>',unsafe_allow_html=True)

def navigate(page):
    st.session_state['navigation']=page

