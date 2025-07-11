import os
import json
import streamlit as st

DEFAULT_CONFIG_FILE = "default_config.json"
default_config = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "INOUT_COST": 3000,
    "PICKUP_COST": 1500,
    "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 2.0,
    "EXCHANGE_RATE": 350,
    "PACKAGING_COST": 500,
    "GIFT_COST": 0
}

def save_config(cfg):
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(cfg, f)

@st.cache_data
def load_config(file_mtime):
    """
    file_mtime 을 캐시 키로 사용해 설정을 메모리에 저장.
    파일이 바뀌면 자동으로 다시 읽어옵니다.
    """
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                data = json.load(f)
                return {k: v for k, v in data.items()}
        except:
            return default_config.copy()
    else:
        return default_config.copy()
