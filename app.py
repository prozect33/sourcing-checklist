
import streamlit as st

st.set_page_config(page_title="5분할 레이아웃 테스트", layout="wide")

st.markdown("""
<div style='display: grid; grid-template-columns: 0.1fr 1fr 1fr 1fr 0.3fr 0.3fr; background: #e8f5e9; padding: 12px 18px; border-radius: 10px; text-align: center; align-items: center; gap: 8px;'>
    <div></div>
    <div><div style='font-weight:bold; font-size:15px;'>💰 마진</div><div style='font-size:15px;'>7,324원</div></div>
    <div><div style='font-weight:bold; font-size:15px;'>📈 마진율</div><div style='font-size:15px;'>40.28%</div></div>
    <div><div style='font-weight:bold; font-size:15px;'>💹 투자수익률</div><div style='font-size:15px;'>104.63%</div></div>
    <div></div>
    <div></div>
</div>
""", unsafe_allow_html=True)
